from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from purchasing.models import Purchase
from .forms import PagoCompraForm
from .models import PagoCompra


@login_required
@permission_required('purchasing.view_purchase', raise_exception=True)
def compra_pendiente_list(request):
    qs = (
        Purchase.objects
        .filter(is_active=True, tipo_pago='credito', estado='pendiente')
        .select_related('supplier')
        .order_by('-purchase_date')
    )
    supplier_q = request.GET.get('supplier', '').strip()
    if supplier_q:
        qs = qs.filter(Q(supplier__name__icontains=supplier_q))
    paginator = Paginator(qs, 10)
    page = request.GET.get('page')
    try:
        compras = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        compras = paginator.page(1)
    p = request.GET.copy(); p.pop('page', None); qs_str = p.urlencode()
    return render(request, 'pagos/compra_pendiente_list.html', {
        'compras': compras,
        'paginator': paginator,
        'page_obj': compras,
        'is_paginated': paginator.num_pages > 1,
        'filter_qs_pfx': (qs_str + '&') if qs_str else '',
        'params': request.GET,
        'elided_page_range': paginator.get_elided_page_range(compras.number, on_each_side=2, on_ends=1),
    })


@login_required
@permission_required('pagos.view_pagocompra', raise_exception=True)
def pago_historial(request, compra_pk):
    compra = get_object_or_404(Purchase.objects.select_related('supplier'), pk=compra_pk)
    pagos = compra.pagos.all()
    return render(request, 'pagos/pago_historial.html', {'compra': compra, 'pagos': pagos})


@login_required
@permission_required('pagos.add_pagocompra', raise_exception=True)
@transaction.atomic
def pago_create(request, compra_pk):
    compra = get_object_or_404(Purchase, pk=compra_pk)
    if not compra.is_active:
        messages.error(request, 'No se puede registrar un pago sobre una compra anulada.')
        return redirect('pagos:compra_pendiente_list')
    if compra.estado == 'pagada':
        messages.error(request, 'Esta compra ya está totalmente pagada.')
        return redirect('pagos:pago_historial', compra_pk=compra.pk)
    if request.method == 'POST':
        form = PagoCompraForm(request.POST, compra=compra)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.compra = compra
            pago.save()
            compra.actualizar_saldo()
            messages.success(request, 'Pago registrado exitosamente.')
            return redirect('pagos:pago_historial', compra_pk=compra.pk)
    else:
        form = PagoCompraForm(compra=compra, initial={'fecha': timezone.localdate()})
    return render(request, 'pagos/pago_form.html', {
        'form': form, 'compra': compra, 'title': 'Registrar Pago',
    })


@login_required
@permission_required('pagos.change_pagocompra', raise_exception=True)
@transaction.atomic
def pago_update(request, pk):
    pago = get_object_or_404(PagoCompra, pk=pk)
    compra = pago.compra
    if request.method == 'POST':
        form = PagoCompraForm(request.POST, instance=pago, compra=compra)
        if form.is_valid():
            form.save()
            compra.actualizar_saldo()
            messages.success(request, 'Pago actualizado.')
            return redirect('pagos:pago_historial', compra_pk=compra.pk)
    else:
        form = PagoCompraForm(instance=pago, compra=compra)
    return render(request, 'pagos/pago_form.html', {
        'form': form, 'compra': compra, 'title': 'Editar Pago',
    })


@login_required
@permission_required('pagos.delete_pagocompra', raise_exception=True)
@transaction.atomic
def pago_delete(request, pk):
    pago = get_object_or_404(PagoCompra, pk=pk)
    compra = pago.compra
    if compra.estado == 'pagada':
        messages.error(request, 'No se puede eliminar un pago de una compra ya cancelada por completo.')
        return redirect('pagos:pago_historial', compra_pk=compra.pk)
    if request.method == 'POST':
        pago.delete()
        compra.actualizar_saldo()
        messages.success(request, 'Pago eliminado.')
        return redirect('pagos:pago_historial', compra_pk=compra.pk)
    return render(request, 'pagos/pago_confirm_delete.html', {'object': pago, 'compra': compra})
