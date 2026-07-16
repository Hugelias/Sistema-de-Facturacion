import json
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core import signing
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from billing.models import Invoice
from billing.tokens import verify_invoice_token
from .emails import send_cobro_email
from .forms import CobroFacturaForm
from .models import CobroFactura, Notification
from .paypal_client import PayPalServiceError, capturar_orden, crear_orden


@login_required
@permission_required('billing.view_invoice', raise_exception=True)
def factura_pendiente_list(request):
    qs = (
        Invoice.objects
        .filter(is_active=True, tipo_pago='credito', estado='pendiente')
        .select_related('customer')
        .order_by('-invoice_date')
    )
    client_q = request.GET.get('client', '').strip()
    if client_q:
        qs = qs.filter(
            Q(customer__first_name__icontains=client_q) | Q(customer__last_name__icontains=client_q)
        )
    paginator = Paginator(qs, 10)
    page = request.GET.get('page')
    try:
        facturas = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        facturas = paginator.page(1)
    p = request.GET.copy(); p.pop('page', None); qs_str = p.urlencode()
    return render(request, 'cobros/factura_pendiente_list.html', {
        'facturas': facturas,
        'paginator': paginator,
        'page_obj': facturas,
        'is_paginated': paginator.num_pages > 1,
        'filter_qs_pfx': (qs_str + '&') if qs_str else '',
        'params': request.GET,
        'elided_page_range': paginator.get_elided_page_range(facturas.number, on_each_side=2, on_ends=1),
    })


@login_required
@permission_required('cobros.view_cobrofactura', raise_exception=True)
def cobro_historial(request, factura_pk):
    factura = get_object_or_404(Invoice.objects.select_related('customer'), pk=factura_pk)
    cobros = factura.cobros.all()
    return render(request, 'cobros/cobro_historial.html', {
        'factura': factura, 'cobros': cobros, 'paypal_client_id': settings.PAYPAL_CLIENT_ID,
    })


@login_required
@permission_required('cobros.add_cobrofactura', raise_exception=True)
@transaction.atomic
def cobro_create(request, factura_pk):
    factura = get_object_or_404(Invoice, pk=factura_pk)
    if not factura.is_active:
        messages.error(request, 'No se puede registrar un pago sobre una factura anulada.')
        return redirect('cobros:factura_pendiente_list')
    if factura.estado == 'pagada':
        messages.error(request, 'Esta factura ya está totalmente pagada.')
        return redirect('cobros:cobro_historial', factura_pk=factura.pk)
    if request.method == 'POST':
        form = CobroFacturaForm(request.POST, factura=factura)
        if form.is_valid():
            cobro = form.save(commit=False)
            cobro.factura = factura
            cobro.save()
            factura.actualizar_saldo()
            messages.success(request, 'Pago registrado exitosamente.')
            if factura.customer.email:
                try:
                    send_cobro_email(cobro, request=request)
                    messages.info(request, f'Se envió un correo de confirmación a {factura.customer.email}.')
                except Exception:
                    messages.warning(request, 'El pago se registró, pero no se pudo enviar el correo de confirmación.')
            return redirect('cobros:cobro_historial', factura_pk=factura.pk)
    else:
        form = CobroFacturaForm(factura=factura, initial={'fecha': timezone.localdate()})
    return render(request, 'cobros/cobro_form.html', {
        'form': form, 'factura': factura, 'title': 'Registrar Pago',
    })


@login_required
@permission_required('cobros.change_cobrofactura', raise_exception=True)
@transaction.atomic
def cobro_update(request, pk):
    cobro = get_object_or_404(CobroFactura, pk=pk)
    factura = cobro.factura
    if request.method == 'POST':
        form = CobroFacturaForm(request.POST, instance=cobro, factura=factura)
        if form.is_valid():
            form.save()
            factura.actualizar_saldo()
            messages.success(request, 'Pago actualizado.')
            return redirect('cobros:cobro_historial', factura_pk=factura.pk)
    else:
        form = CobroFacturaForm(instance=cobro, factura=factura)
    return render(request, 'cobros/cobro_form.html', {
        'form': form, 'factura': factura, 'title': 'Editar Pago',
    })


@login_required
@permission_required('cobros.delete_cobrofactura', raise_exception=True)
@transaction.atomic
def cobro_delete(request, pk):
    cobro = get_object_or_404(CobroFactura, pk=pk)
    factura = cobro.factura
    if factura.estado == 'pagada':
        messages.error(request, 'No se puede eliminar un pago de una factura ya cancelada por completo.')
        return redirect('cobros:cobro_historial', factura_pk=factura.pk)
    if request.method == 'POST':
        cobro.delete()
        factura.actualizar_saldo()
        messages.success(request, 'Pago eliminado.')
        return redirect('cobros:cobro_historial', factura_pk=factura.pk)
    return render(request, 'cobros/cobro_confirm_delete.html', {'object': cobro, 'factura': factura})


def _parse_monto(raw):
    """Acepta montos con punto o coma decimal (locale es-ec)."""
    texto = str(raw or '').strip().replace(' ', '').replace(',', '.')
    if not texto:
        raise InvalidOperation('vacío')
    return Decimal(texto)


def _paypal_crear_orden_response(request, factura, return_url='', cancel_url=''):
    """Valida el monto y crea la orden PayPal (SDK Buttons o redirección)."""
    if not factura.is_active or factura.estado == 'pagada':
        return JsonResponse({'error': 'Esta factura no admite más pagos.'}, status=400)
    try:
        data = json.loads(request.body or '{}')
        monto = _parse_monto(data.get('amount', ''))
    except (InvalidOperation, ValueError, TypeError):
        return JsonResponse({'error': 'Monto inválido.'}, status=400)
    if monto <= 0 or monto > factura.saldo:
        return JsonResponse({
            'error': f'El monto debe estar entre $ 0.01 y $ {factura.saldo} (saldo pendiente).',
        }, status=400)
    try:
        order_id, approve_url = crear_orden(
            factura, monto,
            return_url=return_url or None,
            cancel_url=cancel_url or None,
        )
    except PayPalServiceError as e:
        return JsonResponse({'error': str(e)}, status=502)
    # El SDK Buttons solo necesita `id`. approve_url queda por si se usa redirección.
    return JsonResponse({'id': order_id, 'approve_url': approve_url})


def _paypal_registrar_cobro(request, factura, order_id, origen='interno'):
    """Captura la orden y registra el abono. Si ya se registró esa orden, no duplica."""
    existente = CobroFactura.objects.filter(paypal_order_id=order_id).first()
    if existente:
        return existente, False

    try:
        monto_str, captured_order_id = capturar_orden(order_id)
        monto = Decimal(monto_str)
    except PayPalServiceError:
        raise

    if monto > factura.saldo:
        monto = factura.saldo

    cobro = CobroFactura.objects.create(
        factura=factura,
        fecha=timezone.localdate(),
        valor=monto,
        observacion='Pago recibido vía PayPal.',
        metodo_pago='paypal',
        paypal_order_id=captured_order_id,
    )
    factura.actualizar_saldo()

    if origen == 'publico':
        Notification.objects.create(
            factura=factura,
            mensaje=(
                f'{factura.customer.full_name} realizó un abono de $ {monto} en la factura '
                f'#{factura.number or factura.id} desde el enlace de correo (PayPal).'
            ),
        )

    if factura.customer.email:
        try:
            send_cobro_email(cobro, request=request)
        except Exception:
            pass

    return cobro, True


def _paypal_capturar_orden_response(request, factura, order_id, origen='interno'):
    """Captura la orden ya aprobada y registra el abono (API JSON, legacy)."""
    try:
        cobro, _creado = _paypal_registrar_cobro(request, factura, order_id, origen=origen)
    except PayPalServiceError as e:
        return JsonResponse({'error': str(e)}, status=502)

    return JsonResponse({
        'status': 'COMPLETED',
        'valor': str(cobro.valor),
        'saldo': str(factura.saldo),
        'email_sent': bool(factura.customer.email),
    })


@login_required
@permission_required('cobros.add_cobrofactura', raise_exception=True)
@require_POST
def cobro_paypal_create_order(request, factura_pk):
    """Crea orden: flow=redirect → enlace sandbox; sin flow → SDK tarjeta."""
    factura = get_object_or_404(Invoice, pk=factura_pk)
    data = json.loads(request.body or '{}')
    return_url = cancel_url = ''
    if data.get('flow') == 'redirect':
        return_url = request.build_absolute_uri(
            reverse('cobros:cobro_paypal_return', kwargs={'factura_pk': factura.pk})
        )
        cancel_url = request.build_absolute_uri(
            reverse('cobros:cobro_historial', kwargs={'factura_pk': factura.pk})
        )
    return _paypal_crear_orden_response(request, factura, return_url, cancel_url)


@login_required
@permission_required('cobros.add_cobrofactura', raise_exception=True)
@require_GET
@transaction.atomic
def cobro_paypal_return(request, factura_pk):
    """PayPal vuelve aquí tras aprobar (ventana popup o misma pestaña)."""
    factura = get_object_or_404(Invoice, pk=factura_pk)
    order_id = request.GET.get('token') or request.GET.get('order_id')
    back = reverse('cobros:cobro_historial', kwargs={'factura_pk': factura.pk})
    popup = request.GET.get('popup') == '1'
    if not order_id:
        msg = 'PayPal no devolvió el identificador de la orden.'
        if popup:
            return render(request, 'cobros/paypal_popup_done.html', {
                'ok': False, 'message': msg, 'back_url': back,
            })
        messages.error(request, msg)
        return redirect(back)
    try:
        cobro, creado = _paypal_registrar_cobro(request, factura, order_id, origen='interno')
    except PayPalServiceError as e:
        if popup:
            return render(request, 'cobros/paypal_popup_done.html', {
                'ok': False, 'message': str(e), 'back_url': back,
            })
        messages.error(request, str(e))
        return redirect(back)
    if creado:
        msg = f'Pago PayPal de $ {cobro.valor} registrado. Saldo restante: $ {factura.saldo}.'
    else:
        msg = 'Este pago PayPal ya estaba registrado.'
    if popup:
        return render(request, 'cobros/paypal_popup_done.html', {
            'ok': True, 'message': msg, 'back_url': back,
        })
    if creado:
        messages.success(request, msg)
    else:
        messages.info(request, msg)
    return redirect(back)


@login_required
@permission_required('cobros.add_cobrofactura', raise_exception=True)
@require_GET
def cobro_paypal_cancel(request, factura_pk):
    """El comprador canceló en PayPal (ventana popup)."""
    back = reverse('cobros:cobro_historial', kwargs={'factura_pk': factura_pk})
    msg = 'Pago cancelado en PayPal.'
    if request.GET.get('popup') == '1':
        return render(request, 'cobros/paypal_popup_done.html', {
            'ok': False, 'message': msg, 'back_url': back,
        })
    messages.info(request, msg)
    return redirect(back)


@login_required
@permission_required('cobros.add_cobrofactura', raise_exception=True)
@require_POST
@transaction.atomic
def cobro_paypal_capture_order(request, factura_pk, order_id):
    """Versión interna de la captura del pago (staff, API JSON)."""
    factura = get_object_or_404(Invoice, pk=factura_pk)
    return _paypal_capturar_orden_response(request, factura, order_id)


@require_POST
def cobro_paypal_public_create_order(request, token):
    """Versión pública: flow=redirect → sandbox; sin flow → SDK tarjeta."""
    try:
        pk = verify_invoice_token(token)
    except signing.BadSignature:
        return JsonResponse({'error': 'El enlace no es válido o ya venció.'}, status=403)
    factura = get_object_or_404(Invoice, pk=pk)
    data = json.loads(request.body or '{}')
    return_url = cancel_url = ''
    if data.get('flow') == 'redirect':
        return_url = request.build_absolute_uri(
            reverse('cobros:cobro_paypal_public_return', kwargs={'token': token})
        )
        cancel_url = request.build_absolute_uri(
            reverse('billing:invoice_pdf_public', kwargs={'token': token})
        )
    return _paypal_crear_orden_response(request, factura, return_url, cancel_url)


@require_GET
@transaction.atomic
def cobro_paypal_public_return(request, token):
    """Retorno PayPal desde el enlace público de la factura."""
    try:
        pk = verify_invoice_token(token)
    except signing.BadSignature:
        messages.error(request, 'El enlace no es válido o ya venció.')
        return redirect('/')
    factura = get_object_or_404(Invoice, pk=pk)
    order_id = request.GET.get('token') or request.GET.get('order_id')
    back = reverse('billing:invoice_pdf_public', kwargs={'token': token})
    popup = request.GET.get('popup') == '1'
    if not order_id:
        msg = 'PayPal no devolvió el identificador de la orden.'
        if popup:
            return render(request, 'cobros/paypal_popup_done.html', {
                'ok': False, 'message': msg, 'back_url': back,
            })
        messages.error(request, msg)
        return redirect(back)
    try:
        cobro, creado = _paypal_registrar_cobro(request, factura, order_id, origen='publico')
    except PayPalServiceError as e:
        if popup:
            return render(request, 'cobros/paypal_popup_done.html', {
                'ok': False, 'message': str(e), 'back_url': back,
            })
        messages.error(request, str(e))
        return redirect(back)
    if creado:
        msg = f'Pago PayPal de $ {cobro.valor} registrado. Saldo restante: $ {factura.saldo}.'
    else:
        msg = 'Este pago PayPal ya estaba registrado.'
    if popup:
        return render(request, 'cobros/paypal_popup_done.html', {
            'ok': True, 'message': msg, 'back_url': back,
        })
    if creado:
        messages.success(request, msg)
    else:
        messages.info(request, msg)
    return redirect(back)


@require_GET
def cobro_paypal_public_cancel(request, token):
    """Cancelación PayPal desde el enlace público."""
    try:
        verify_invoice_token(token)
    except signing.BadSignature:
        return redirect('/')
    back = reverse('billing:invoice_pdf_public', kwargs={'token': token})
    msg = 'Pago cancelado en PayPal.'
    if request.GET.get('popup') == '1':
        return render(request, 'cobros/paypal_popup_done.html', {
            'ok': False, 'message': msg, 'back_url': back,
        })
    messages.info(request, msg)
    return redirect(back)


@require_POST
@transaction.atomic
def cobro_paypal_public_capture_order(request, token, order_id):
    """Versión pública (sin login) de la captura del pago (API JSON)."""
    try:
        pk = verify_invoice_token(token)
    except signing.BadSignature:
        return JsonResponse({'error': 'El enlace no es válido o ya venció.'}, status=403)
    factura = get_object_or_404(Invoice, pk=pk)
    return _paypal_capturar_orden_response(request, factura, order_id, origen='publico')


@login_required
@permission_required('cobros.view_cobrofactura', raise_exception=True)
def notification_open(request, pk):
    """Marca la notificación como leída y lleva al historial de la factura
    correspondiente (llamado al hacer clic en la campanita)."""
    notif = get_object_or_404(Notification, pk=pk)
    if not notif.leida:
        notif.leida = True
        notif.save(update_fields=['leida'])
    if notif.factura_id:
        return redirect('cobros:cobro_historial', factura_pk=notif.factura_id)
    return redirect('billing:home')


@login_required
@permission_required('cobros.view_cobrofactura', raise_exception=True)
@require_POST
def notification_mark_all_read(request):
    Notification.objects.filter(leida=False).update(leida=True)
    return redirect(request.META.get('HTTP_REFERER') or 'billing:home')
