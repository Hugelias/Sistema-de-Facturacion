import json
import datetime

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import Purchase, PurchaseDetail
from .forms import PurchaseForm, PurchaseDetailFormSet
from billing.models import Product
from shared.decorators import audit_action
from shared.mixins import export_queryset


PURCHASE_EXPORT_FIELDS = [
    ('N° Compra',    lambda p: p.number or ''),
    ('Proveedor',    'supplier.name'),
    ('N° Documento', 'document_number'),
    ('Fecha',        lambda p: timezone.localtime(p.purchase_date).strftime('%d/%m/%Y')),
    ('Subtotal',     'subtotal'),
    ('IVA (15%)',    'tax'),
    ('Total',        'total'),
]


@login_required
@permission_required('purchasing.view_purchase', raise_exception=True)
@audit_action('purchase_list')
def purchase_list(request):
    qs = Purchase.objects.select_related('supplier').filter(is_active=True).order_by('-purchase_date')
    supplier_q = request.GET.get('supplier', '').strip()
    date_from  = request.GET.get('date_from', '')
    date_to    = request.GET.get('date_to', '')
    number_q   = request.GET.get('number', '').strip()
    total_min  = request.GET.get('total_min', '').strip()
    total_max  = request.GET.get('total_max', '').strip()
    if supplier_q:
        qs = qs.filter(supplier__name__icontains=supplier_q)
    if date_from:
        try:
            qs = qs.filter(purchase_date__date__gte=datetime.date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            qs = qs.filter(purchase_date__date__lte=datetime.date.fromisoformat(date_to))
        except ValueError:
            pass
    if number_q:
        try:
            qs = qs.filter(number=int(number_q))
        except ValueError:
            pass
    if total_min:
        try:
            qs = qs.filter(total__gte=float(total_min))
        except ValueError:
            pass
    if total_max:
        try:
            qs = qs.filter(total__lte=float(total_max))
        except ValueError:
            pass
    export_response = export_queryset(request, qs, 'Listado de Compras', PURCHASE_EXPORT_FIELDS)
    if export_response is not None:
        return export_response
    paginator = Paginator(qs, 5)
    page = request.GET.get('page')
    try:
        purchases = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        purchases = paginator.page(1)
    p = request.GET.copy(); p.pop('page', None); qs_str = p.urlencode()
    return render(request, 'purchasing/purchase_list.html', {
        'purchases': purchases,
        'paginator': paginator,
        'page_obj': purchases,
        'is_paginated': paginator.num_pages > 1,
        'filter_qs_pfx': (qs_str + '&') if qs_str else '',
        'params': request.GET,
        'elided_page_range': paginator.get_elided_page_range(purchases.number, on_each_side=2, on_ends=1),
        'export_field_labels_json': json.dumps([lbl for lbl, _ in PURCHASE_EXPORT_FIELDS], ensure_ascii=False),
    })


@login_required
@permission_required('purchasing.view_purchase', raise_exception=True)
def purchase_detail(request, pk):
    purchase = get_object_or_404(
        Purchase.objects.select_related('supplier').prefetch_related('details__product'),
        pk=pk
    )
    return render(request, 'purchasing/purchase_detail.html', {'purchase': purchase})


@login_required
@permission_required('purchasing.view_purchase', raise_exception=True)
def purchase_pdf(request, pk):
    purchase = get_object_or_404(
        Purchase.objects.select_related('supplier').prefetch_related('details__product'),
        pk=pk
    )
    return render(request, 'purchasing/purchase_pdf.html', {'purchase': purchase})


def _next_purchase_number():
    used = set(Purchase.objects.filter(number__isnull=False).values_list('number', flat=True))
    n = 1
    while n in used:
        n += 1
    return n


def _products_json():
    return json.dumps({
        str(p.pk): {'name': str(p), 'price': str(p.unit_price)}
        for p in Product.objects.filter(is_active=True).order_by('name')
    })


@login_required
@permission_required('purchasing.add_purchase', raise_exception=True)
@transaction.atomic
def purchase_create(request):
    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        formset = PurchaseDetailFormSet(request.POST)
        form_ok = form.is_valid()
        formset_ok = formset.is_valid()
        if form_ok and formset_ok:
            purchase = form.save()
            purchase.number = _next_purchase_number()
            purchase.save()
            formset.instance = purchase
            formset.save()
            purchase.recalculate()
            for detail in purchase.details.all():
                Product.objects.filter(pk=detail.product_id).update(
                    stock=F('stock') + detail.quantity
                )
            messages.success(request, f'Compra #{purchase.number} registrada exitosamente.')
            return redirect('purchasing:purchase_detail', pk=purchase.pk)
    else:
        form = PurchaseForm()
        formset = PurchaseDetailFormSet()
    return render(request, 'purchasing/purchase_form.html', {
        'form': form, 'formset': formset,
        'title': 'Nueva Compra', 'products_json': _products_json(),
    })


@login_required
@permission_required('purchasing.delete_purchase', raise_exception=True)
def purchase_delete(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == 'POST':
        num = purchase.number
        purchase.is_active = False
        purchase.number = None
        purchase.save()
        messages.success(request, f'Compra #{num} anulada.')
        return redirect('purchasing:purchase_list')
    return render(request, 'purchasing/purchase_confirm_delete.html', {'object': purchase})
