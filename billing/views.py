import json
import datetime
import re
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import F, Sum, Count, Q, ProtectedError
from django.utils import timezone

from .models import Brand, ProductGroup, Supplier, Product, Customer, CustomerProfile, Invoice, InvoiceDetail
from .forms import (BrandForm, ProductGroupForm, SupplierForm, ProductForm,
                    InvoiceForm, InvoiceDetailFormSet)
from .emails import send_invoice_email
from .whatsapp import send_invoice_whatsapp
from .whatsapp_client import WhatsAppServiceError
from .tokens import verify_invoice_token
from .electronic_invoice import autorizar_factura_electronica, generar_xml_autorizacion
from .pdf import generar_factura_pdf
from .sri_client import SriServiceError, consultar_contribuyente
from .sri_facturacion_client import SriFacturacionServiceError
from shared.mixins import PermissionMixin, ExportMixin, ProtectedDeleteMixin, export_queryset
from shared.decorators import audit_action


# ── Home ─────────────────────────────────────────────────────────────────────

@login_required
def home(request):
    from purchasing.models import Purchase

    now = timezone.now()

    # ── Alcance del dashboard según el rol ──────────────────────────────────
    user_groups = set(request.user.groups.values_list('name', flat=True))
    is_full = request.user.is_superuser or 'Administrador' in user_groups or 'Gerente' in user_groups
    if is_full:
        dash_scope = 'full'
    elif 'Ventas' in user_groups:
        dash_scope = 'ventas'
    elif 'Compras' in user_groups:
        dash_scope = 'compras'
    else:
        dash_scope = 'full'

    # ── KPI counts ──────────────────────────────────────────────────────────
    total_products  = Product.objects.filter(is_active=True).count()
    total_customers = Customer.objects.filter(is_active=True).count()
    total_invoices  = Invoice.objects.filter(is_active=True).count()
    total_purchases = Purchase.objects.filter(is_active=True).count()
    total_suppliers = Supplier.objects.filter(is_active=True).count()
    total_invoices_pending  = Invoice.objects.filter(is_active=True, tipo_pago='credito', estado='pendiente').count()
    total_purchases_pending = Purchase.objects.filter(is_active=True, tipo_pago='credito', estado='pendiente').count()

    # ── Last 6 months chart data ─────────────────────────────────────────────
    MONTHS_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

    month_list = []
    y, m = now.year, now.month
    for _ in range(6):
        month_list.insert(0, (y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1

    chart_months    = []
    chart_sales     = []
    chart_purchases = []
    for yr, mo in month_list:
        start = timezone.make_aware(datetime.datetime(yr, mo, 1))
        end   = timezone.make_aware(
            datetime.datetime(yr + 1, 1, 1) if mo == 12 else datetime.datetime(yr, mo + 1, 1)
        )
        chart_months.append(MONTHS_ES[mo - 1])
        chart_sales.append(float(
            Invoice.objects.filter(is_active=True, invoice_date__gte=start, invoice_date__lt=end)
                           .aggregate(t=Sum('total'))['t'] or 0
        ))
        chart_purchases.append(float(
            Purchase.objects.filter(is_active=True, purchase_date__gte=start, purchase_date__lt=end)
                            .aggregate(t=Sum('total'))['t'] or 0
        ))

    # ── Last 7 days chart data ───────────────────────────────────────────────
    DAY_ABBR_ES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']  # date.weekday(): Lun=0..Dom=6
    today_date = timezone.localdate()

    chart_days = []
    chart_sales_daily = []
    chart_purchases_daily = []
    for i in range(6, -1, -1):
        day = today_date - datetime.timedelta(days=i)
        start = timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))
        end   = timezone.make_aware(datetime.datetime.combine(day, datetime.time.max))
        chart_days.append(DAY_ABBR_ES[day.weekday()])
        chart_sales_daily.append(float(
            Invoice.objects.filter(is_active=True, invoice_date__range=(start, end))
                           .aggregate(t=Sum('total'))['t'] or 0
        ))
        chart_purchases_daily.append(float(
            Purchase.objects.filter(is_active=True, purchase_date__range=(start, end))
                            .aggregate(t=Sum('total'))['t'] or 0
        ))

    # ── Last 8 weeks chart data (ventanas de 7 días terminando hoy) ──────────
    chart_weeks = []
    chart_sales_weekly = []
    chart_purchases_weekly = []
    for i in range(7, -1, -1):
        week_end   = today_date - datetime.timedelta(days=7 * i)
        week_start = week_end - datetime.timedelta(days=6)
        start = timezone.make_aware(datetime.datetime.combine(week_start, datetime.time.min))
        end   = timezone.make_aware(datetime.datetime.combine(week_end, datetime.time.max))
        chart_weeks.append(f'{week_start.day} {MONTHS_ES[week_start.month - 1]}')
        chart_sales_weekly.append(float(
            Invoice.objects.filter(is_active=True, invoice_date__range=(start, end))
                           .aggregate(t=Sum('total'))['t'] or 0
        ))
        chart_purchases_weekly.append(float(
            Purchase.objects.filter(is_active=True, purchase_date__range=(start, end))
                            .aggregate(t=Sum('total'))['t'] or 0
        ))

    # ── Product distribution by group (donut) ───────────────────────────────
    groups_qs    = (ProductGroup.objects
                    .annotate(cnt=Count('products', filter=Q(products__is_active=True)))
                    .filter(cnt__gt=0).order_by('-cnt')[:6])
    group_labels = [g.name for g in groups_qs]
    group_counts = [g.cnt  for g in groups_qs]
    total_grouped = sum(group_counts)

    # ── Financial summary (current month) ───────────────────────────────────
    month_start = timezone.make_aware(datetime.datetime(now.year, now.month, 1))
    prev_mo     = now.month - 1 or 12
    prev_yr     = now.year if now.month > 1 else now.year - 1
    prev_start  = timezone.make_aware(datetime.datetime(prev_yr, prev_mo, 1))

    income_cur  = float(Invoice.objects.filter(is_active=True, invoice_date__gte=month_start)
                                       .aggregate(t=Sum('total'))['t'] or 0)
    expense_cur = float(Purchase.objects.filter(is_active=True, purchase_date__gte=month_start)
                                        .aggregate(t=Sum('total'))['t'] or 0)
    income_prev = float(Invoice.objects.filter(is_active=True,
                                               invoice_date__gte=prev_start,
                                               invoice_date__lt=month_start)
                                       .aggregate(t=Sum('total'))['t'] or 0)
    expense_prev = float(Purchase.objects.filter(is_active=True,
                                                 purchase_date__gte=prev_start,
                                                 purchase_date__lt=month_start)
                                         .aggregate(t=Sum('total'))['t'] or 0)

    def pct_change(cur, prev):
        if prev == 0:
            return 100 if cur > 0 else 0
        return round((cur - prev) / prev * 100)

    profit_cur  = income_cur  - expense_cur
    profit_prev = income_prev - expense_prev

    context = {
        'dash_scope':       dash_scope,
        'total_products':   total_products,
        'total_customers':  total_customers,
        'total_invoices':   total_invoices,
        'total_purchases':  total_purchases,
        'total_suppliers':  total_suppliers,
        'total_invoices_pending':  total_invoices_pending,
        'total_purchases_pending': total_purchases_pending,
        'recent_invoices':  Invoice.objects.select_related('customer')
                                           .filter(is_active=True)
                                           .order_by('-invoice_date')[:5],
        'recent_purchases': Purchase.objects.select_related('supplier')
                                            .filter(is_active=True)
                                            .order_by('-purchase_date')[:5],
        # charts
        'chart_months':    json.dumps(chart_months),
        'chart_sales':     json.dumps(chart_sales),
        'chart_purchases': json.dumps(chart_purchases),
        'chart_days':               json.dumps(chart_days),
        'chart_sales_daily':        json.dumps(chart_sales_daily),
        'chart_purchases_daily':    json.dumps(chart_purchases_daily),
        'chart_weeks':              json.dumps(chart_weeks),
        'chart_sales_weekly':       json.dumps(chart_sales_weekly),
        'chart_purchases_weekly':   json.dumps(chart_purchases_weekly),
        'group_labels':    json.dumps(group_labels),
        'group_counts':    json.dumps(group_counts),
        'total_grouped':   total_grouped,
        # financial
        'income_cur':      income_cur,
        'expense_cur':     expense_cur,
        'profit_cur':      profit_cur,
        'income_pct':      pct_change(income_cur,  income_prev),
        'expense_pct':     pct_change(expense_cur, expense_prev),
        'profit_pct':      pct_change(profit_cur,  profit_prev),
    }
    return render(request, 'billing/home.html', context)


# ── Brand (FBV) ───────────────────────────────────────────────────────────────

BRAND_EXPORT_FIELDS = [
    ('Nombre',      'name'),
    ('Descripción', 'description'),
    ('Estado',      lambda b: 'Activo' if b.is_active else 'Inactivo'),
]


@login_required
@permission_required('billing.view_brand', raise_exception=True)
@audit_action('brand_list')
def brand_list(request):
    qs = Brand.objects.all()
    name_q = request.GET.get('name', '').strip()
    status  = request.GET.get('status', '')
    if name_q:
        qs = qs.filter(name__icontains=name_q)
    if status == '1':
        qs = qs.filter(is_active=True)
    elif status == '0':
        qs = qs.filter(is_active=False)
    export_response = export_queryset(request, qs, 'Listado de Marcas', BRAND_EXPORT_FIELDS)
    if export_response is not None:
        return export_response
    paginator = Paginator(qs, 10)
    page = request.GET.get('page')
    try:
        brands = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        brands = paginator.page(1)
    p = request.GET.copy(); p.pop('page', None); qs_str = p.urlencode()
    return render(request, 'billing/brand_list.html', {
        'brands': brands,
        'paginator': paginator,
        'page_obj': brands,
        'is_paginated': paginator.num_pages > 1,
        'filter_qs_pfx': (qs_str + '&') if qs_str else '',
        'params': request.GET,
        'elided_page_range': paginator.get_elided_page_range(brands.number, on_each_side=2, on_ends=1),
        'export_field_labels_json': json.dumps([lbl for lbl, _ in BRAND_EXPORT_FIELDS], ensure_ascii=False),
    })


@login_required
@permission_required('billing.add_brand', raise_exception=True)
def brand_create(request):
    if request.method == 'POST':
        form = BrandForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Marca creada exitosamente.')
            return redirect('billing:brand_list')
    else:
        form = BrandForm()
    return render(request, 'billing/brand_form.html', {'form': form, 'title': 'Nueva Marca'})


@login_required
@permission_required('billing.change_brand', raise_exception=True)
def brand_update(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        form = BrandForm(request.POST, instance=brand)
        if form.is_valid():
            form.save()
            messages.success(request, 'Marca actualizada.')
            return redirect('billing:brand_list')
    else:
        form = BrandForm(instance=brand)
    return render(request, 'billing/brand_form.html', {'form': form, 'title': 'Editar Marca'})


@login_required
@permission_required('billing.delete_brand', raise_exception=True)
def brand_delete(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        try:
            brand.delete()
            messages.success(request, 'Marca eliminada.')
        except ProtectedError:
            messages.error(request, f'No se puede eliminar "{brand}" porque tiene productos asociados.')
        return redirect('billing:brand_list')
    return render(request, 'billing/brand_confirm_delete.html', {'object': brand})


# ── ProductGroup (CBV) ────────────────────────────────────────────────────────

class ProductGroupListView(PermissionMixin, ExportMixin, ListView):
    model = ProductGroup
    template_name = 'billing/productgroup_list.html'
    context_object_name = 'groups'
    paginate_by = 10
    permission_required = 'billing.view_productgroup'
    export_title = 'Listado de Grupos de Productos'
    export_fields = [
        ('Nombre',       'name'),
        ('Descripción',  'description'),
        ('Estado',       lambda g: 'Activo' if g.is_active else 'Inactivo'),
    ]

    def get_queryset(self):
        qs = ProductGroup.objects.all()
        name_q = self.request.GET.get('name', '').strip()
        status  = self.request.GET.get('status', '')
        if name_q:
            qs = qs.filter(name__icontains=name_q)
        if status == '1':
            qs = qs.filter(is_active=True)
        elif status == '0':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = self.request.GET.copy(); p.pop('page', None); qs_str = p.urlencode()
        ctx['filter_qs_pfx'] = (qs_str + '&') if qs_str else ''
        ctx['params'] = self.request.GET
        if ctx.get('is_paginated'):
            ctx['elided_page_range'] = ctx['paginator'].get_elided_page_range(
                number=ctx['page_obj'].number, on_each_side=2, on_ends=1)
        return ctx


class ProductGroupCreateView(PermissionMixin, CreateView):
    model = ProductGroup
    form_class = ProductGroupForm
    template_name = 'billing/productgroup_form.html'
    success_url = reverse_lazy('billing:productgroup_list')
    permission_required = 'billing.add_productgroup'

    def form_valid(self, form):
        messages.success(self.request, 'Grupo creado.')
        return super().form_valid(form)


class ProductGroupUpdateView(PermissionMixin, UpdateView):
    model = ProductGroup
    form_class = ProductGroupForm
    template_name = 'billing/productgroup_form.html'
    success_url = reverse_lazy('billing:productgroup_list')
    permission_required = 'billing.change_productgroup'

    def form_valid(self, form):
        messages.success(self.request, 'Grupo actualizado.')
        return super().form_valid(form)


class ProductGroupDeleteView(ProtectedDeleteMixin, PermissionMixin, DeleteView):
    model = ProductGroup
    template_name = 'billing/productgroup_confirm_delete.html'
    success_url = reverse_lazy('billing:productgroup_list')
    permission_required = 'billing.delete_productgroup'


# ── Supplier (CBV) ────────────────────────────────────────────────────────────

class SupplierListView(PermissionMixin, ExportMixin, ListView):
    model = Supplier
    template_name = 'billing/supplier_list.html'
    context_object_name = 'suppliers'
    paginate_by = 10
    permission_required = 'billing.view_supplier'
    export_title = 'Listado de Proveedores'
    export_fields = [
        ('Nombre',     'name'),
        ('RUC',        'ruc'),
        ('Contacto',   'contact_name'),
        ('Email',      'email'),
        ('Teléfono',   'phone'),
        ('Dirección',  'address'),
        ('Estado',     lambda s: 'Activo' if s.is_active else 'Inactivo'),
    ]

    def get_queryset(self):
        qs = Supplier.objects.all()
        name_q  = self.request.GET.get('name', '').strip()
        ruc_q   = self.request.GET.get('ruc', '').strip()
        phone_q = self.request.GET.get('phone', '').strip()
        status  = self.request.GET.get('status', '')
        if name_q:
            qs = qs.filter(name__icontains=name_q)
        if ruc_q:
            qs = qs.filter(ruc__icontains=ruc_q)
        if phone_q:
            qs = qs.filter(phone__icontains=phone_q)
        if status == '1':
            qs = qs.filter(is_active=True)
        elif status == '0':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = self.request.GET.copy(); p.pop('page', None); qs_str = p.urlencode()
        ctx['filter_qs_pfx'] = (qs_str + '&') if qs_str else ''
        ctx['params'] = self.request.GET
        if ctx.get('is_paginated'):
            ctx['elided_page_range'] = ctx['paginator'].get_elided_page_range(
                number=ctx['page_obj'].number, on_each_side=2, on_ends=1)
        return ctx


class SupplierCreateView(PermissionMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'billing/supplier_form.html'
    success_url = reverse_lazy('billing:supplier_list')
    permission_required = 'billing.add_supplier'

    def form_valid(self, form):
        messages.success(self.request, 'Proveedor creado.')
        return super().form_valid(form)


@login_required
@permission_required(('billing.add_supplier', 'billing.change_supplier'), raise_exception=True)
def supplier_consultar_ruc(request):
    """Consulta RUC vía microservicio SRI (JSON para autocompletar el formulario)."""
    ruc = request.GET.get('ruc', '').strip()
    try:
        data = consultar_contribuyente(ruc)
    except SriServiceError as e:
        return JsonResponse({'error': str(e)}, status=400 if '13 dígitos' in str(e) else 502)
    return JsonResponse(data)


class SupplierUpdateView(PermissionMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'billing/supplier_form.html'
    success_url = reverse_lazy('billing:supplier_list')
    permission_required = 'billing.change_supplier'

    def form_valid(self, form):
        messages.success(self.request, 'Proveedor actualizado.')
        return super().form_valid(form)


class SupplierDeleteView(ProtectedDeleteMixin, PermissionMixin, DeleteView):
    model = Supplier
    template_name = 'billing/supplier_confirm_delete.html'
    success_url = reverse_lazy('billing:supplier_list')
    permission_required = 'billing.delete_supplier'


# ── Product (CBV) ─────────────────────────────────────────────────────────────

class ProductListView(PermissionMixin, ExportMixin, ListView):
    model = Product
    template_name = 'billing/product_list.html'
    context_object_name = 'products'
    paginate_by = 4
    export_title = 'Listado de Productos'
    permission_required = 'billing.view_product'
    export_fields = [
        ('Nombre',          'name'),
        ('Descripción',     'description'),
        ('Marca',           'brand.name'),
        ('Grupo',           'group.name'),
        ('Precio Unitario', 'unit_price'),
        ('Stock',           'stock'),
        ('Estado',          lambda p: 'Activo' if p.is_active else 'Inactivo'),
    ]

    def get_queryset(self):
        qs = Product.objects.select_related('brand', 'group').prefetch_related('suppliers')
        p = self.request.GET
        if p.get('name', '').strip():
            qs = qs.filter(name__icontains=p['name'].strip())
        if p.get('description', '').strip():
            qs = qs.filter(description__icontains=p['description'].strip())
        if p.get('brand'):
            qs = qs.filter(brand_id=p['brand'])
        if p.get('group'):
            qs = qs.filter(group_id=p['group'])
        if p.get('supplier'):
            qs = qs.filter(suppliers__id=p['supplier']).distinct()
        if p.get('is_active') in ('1', '0'):
            qs = qs.filter(is_active=(p['is_active'] == '1'))
        try:
            if p.get('price_min'):
                qs = qs.filter(unit_price__gte=p['price_min'])
        except (ValueError, TypeError):
            pass
        try:
            if p.get('price_max'):
                qs = qs.filter(unit_price__lte=p['price_max'])
        except (ValueError, TypeError):
            pass
        try:
            if p.get('stock_min'):
                qs = qs.filter(stock__gte=int(p['stock_min']))
        except (ValueError, TypeError):
            pass
        try:
            if p.get('stock_max'):
                qs = qs.filter(stock__lte=int(p['stock_max']))
        except (ValueError, TypeError):
            pass
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['brands'] = Brand.objects.filter(is_active=True).order_by('name')
        ctx['groups'] = ProductGroup.objects.filter(is_active=True).order_by('name')
        ctx['suppliers'] = Supplier.objects.filter(is_active=True).order_by('name')
        ctx['params'] = self.request.GET
        q = self.request.GET.copy()
        q.pop('page', None)
        q.pop('export', None)
        qs_str = q.urlencode()
        ctx['filter_qs_pfx'] = (qs_str + '&') if qs_str else ''
        ctx['elided_page_range'] = ctx['paginator'].get_elided_page_range(
            number=ctx['page_obj'].number, on_each_side=2, on_ends=1
        )
        return ctx


class ProductDetailView(PermissionMixin, DetailView):
    model = Product
    template_name = 'billing/product_detail.html'
    permission_required = 'billing.view_product'

    def get_queryset(self):
        return Product.objects.select_related('brand', 'group').prefetch_related('suppliers')


class ProductCreateView(PermissionMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'billing/product_form.html'
    success_url = reverse_lazy('billing:product_list')
    permission_required = 'billing.add_product'

    def form_valid(self, form):
        messages.success(self.request, 'Producto creado.')
        return super().form_valid(form)


class ProductUpdateView(PermissionMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'billing/product_form.html'
    success_url = reverse_lazy('billing:product_list')
    permission_required = 'billing.change_product'

    def form_valid(self, form):
        messages.success(self.request, 'Producto actualizado.')
        return super().form_valid(form)


class ProductDeleteView(ProtectedDeleteMixin, PermissionMixin, DeleteView):
    model = Product
    template_name = 'billing/product_confirm_delete.html'
    success_url = reverse_lazy('billing:product_list')
    permission_required = 'billing.delete_product'


# ── Customer (CBV) ────────────────────────────────────────────────────────────

class CustomerListView(PermissionMixin, ExportMixin, ListView):
    model = Customer
    template_name = 'billing/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 5
    permission_required = 'billing.view_customer'
    export_title = 'Listado de Clientes'
    export_fields = [
        ('Nombre',      'full_name'),
        ('Cédula/RUC',  'dni'),
        ('Email',       'email'),
        ('Teléfono',    'phone'),
        ('Ciudad',      'city'),
        ('Estado',      lambda c: 'Activo' if c.is_active else 'Inactivo'),
    ]

    def get_queryset(self):
        qs = Customer.objects.all().order_by('-created_at', 'last_name', 'first_name')
        q      = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '')
        city   = self.request.GET.get('city', '')
        date   = self.request.GET.get('date', '')
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) |
                Q(dni__icontains=q) | Q(email__icontains=q)
            )
        if status == '1':
            qs = qs.filter(is_active=True)
        elif status == '0':
            qs = qs.filter(is_active=False)
        if city:
            qs = qs.filter(city__icontains=city)
        if date:
            try:
                d = datetime.date.fromisoformat(date)
                qs = qs.filter(created_at__date=d)
            except ValueError:
                pass
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        month_start = timezone.make_aware(datetime.datetime(now.year, now.month, 1))
        prev_mo  = now.month - 1 or 12
        prev_yr  = now.year if now.month > 1 else now.year - 1
        prev_start = timezone.make_aware(datetime.datetime(prev_yr, prev_mo, 1))

        total    = Customer.objects.count()
        active   = Customer.objects.filter(is_active=True).count()
        inactive = Customer.objects.filter(is_active=False).count()
        new_cur  = Customer.objects.filter(created_at__gte=month_start).count()
        new_prev = Customer.objects.filter(created_at__gte=prev_start, created_at__lt=month_start).count()

        def _pct(cur, prev):
            if prev == 0:
                return 100 if cur > 0 else 0
            return round((cur - prev) / prev * 100)

        ctx['kpi_total']        = total
        ctx['kpi_active']       = active
        ctx['kpi_inactive']     = inactive
        ctx['kpi_new']          = new_cur
        ctx['kpi_active_pct']   = round(active   / total * 100, 1) if total else 0.0
        ctx['kpi_inactive_pct'] = round(inactive / total * 100, 1) if total else 0.0
        ctx['kpi_new_pct']      = _pct(new_cur, new_prev)
        ctx['cities']           = (Customer.objects.values_list('city', flat=True)
                                   .exclude(city='').distinct().order_by('city'))

        p = self.request.GET.copy()
        p.pop('page', None)
        qs_str = p.urlencode()
        ctx['filter_qs_pfx'] = (qs_str + '&') if qs_str else ''
        ctx['params']        = self.request.GET

        if ctx.get('is_paginated'):
            ctx['elided_page_range'] = ctx['paginator'].get_elided_page_range(
                number=ctx['page_obj'].number, on_each_side=2, on_ends=1
            )
        return ctx


class CustomerDetailView(PermissionMixin, DetailView):
    model = Customer
    template_name = 'billing/customer_detail.html'
    permission_required = 'billing.view_customer'


class CustomerCreateView(PermissionMixin, CreateView):
    model = Customer
    fields = ('dni', 'first_name', 'last_name', 'email', 'phone', 'city', 'address', 'is_active')
    template_name = 'billing/customer_form.html'
    success_url = reverse_lazy('billing:customer_list')
    permission_required = 'billing.add_customer'

    def form_valid(self, form):
        messages.success(self.request, 'Cliente creado.')
        return super().form_valid(form)


class CustomerUpdateView(PermissionMixin, UpdateView):
    model = Customer
    fields = ('dni', 'first_name', 'last_name', 'email', 'phone', 'city', 'address', 'is_active')
    template_name = 'billing/customer_form.html'
    success_url = reverse_lazy('billing:customer_list')
    permission_required = 'billing.change_customer'

    def form_valid(self, form):
        messages.success(self.request, 'Cliente actualizado.')
        return super().form_valid(form)


class CustomerDeleteView(ProtectedDeleteMixin, PermissionMixin, DeleteView):
    model = Customer
    template_name = 'billing/customer_confirm_delete.html'
    success_url = reverse_lazy('billing:customer_list')
    permission_required = 'billing.delete_customer'


# ── Invoice (FBV with formset) ────────────────────────────────────────────────

def _next_invoice_number():
    used = set(Invoice.objects.filter(number__isnull=False).values_list('number', flat=True))
    n = 1
    while n in used:
        n += 1
    return n


def _pending_credit_debt(customer, exclude_pk=None):
    qs = Invoice.objects.filter(customer=customer, tipo_pago='credito', is_active=True, estado='pendiente')
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.aggregate(t=Sum('saldo'))['t'] or Decimal('0.00')


def _prospective_invoice_total(formset):
    subtotal = Decimal('0.00')
    for cd in formset.cleaned_data:
        if not cd or cd.get('DELETE'):
            continue
        subtotal += Decimal(str(cd['quantity'])) * cd['unit_price']
    tax = (subtotal * Decimal('0.15')).quantize(Decimal('0.01'))
    return subtotal + tax


def _check_credit_limit(form, formset, exclude_pk=None):
    """Devuelve un mensaje de error si la venta a crédito excede el límite del cliente."""
    customer = form.cleaned_data['customer']
    if form.cleaned_data['tipo_pago'] != 'credito' or customer.is_generic:
        return None
    limit = customer.get_credit_limit()
    deuda_pendiente = _pending_credit_debt(customer, exclude_pk=exclude_pk)
    prospective_total = _prospective_invoice_total(formset)
    deuda_total = deuda_pendiente + prospective_total
    if deuda_total > limit:
        return (
            f'Crédito no autorizado: el límite de {customer.full_name} es $ {limit:.2f} '
            f'({customer.credit_status_label()}). Ya tiene $ {deuda_pendiente:.2f} pendiente y esta '
            f'factura suma $ {prospective_total:.2f} (total $ {deuda_total:.2f}).'
        )
    return None


INVOICE_EXPORT_FIELDS = [
    ('N° Factura', lambda i: i.number or ''),
    ('Cliente',    lambda i: i.customer.full_name),
    ('Fecha',      lambda i: timezone.localtime(i.invoice_date).strftime('%d/%m/%Y')),
    ('Subtotal',   'subtotal'),
    ('IVA (15%)',  'tax'),
    ('Total',      'total'),
    ('Tipo de Pago', lambda i: 'Crédito' if i.tipo_pago == 'credito' else 'Contado'),
    ('Estado',     lambda i: 'Anulada' if not i.is_active else ('Pagada' if i.estado == 'pagada' else 'Pendiente')),
]


@login_required
@permission_required('billing.view_invoice', raise_exception=True)
def invoice_list(request):
    qs = Invoice.objects.select_related('customer').order_by('-invoice_date')
    client_q  = request.GET.get('client', '').strip()
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')
    status    = request.GET.get('status', '')
    number_q  = request.GET.get('number', '').strip()
    total_min = request.GET.get('total_min', '').strip()
    total_max = request.GET.get('total_max', '').strip()
    if client_q:
        qs = qs.filter(
            Q(customer__first_name__icontains=client_q) | Q(customer__last_name__icontains=client_q)
        )
    if date_from:
        try:
            qs = qs.filter(invoice_date__date__gte=datetime.date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            qs = qs.filter(invoice_date__date__lte=datetime.date.fromisoformat(date_to))
        except ValueError:
            pass
    if status == '1':
        qs = qs.filter(is_active=True)
    elif status == '0':
        qs = qs.filter(is_active=False)
    else:
        qs = qs.filter(is_active=True)
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
    export_response = export_queryset(request, qs, 'Listado de Facturas', INVOICE_EXPORT_FIELDS)
    if export_response is not None:
        return export_response
    paginator = Paginator(qs, 5)
    page = request.GET.get('page')
    try:
        invoices = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        invoices = paginator.page(1)
    p = request.GET.copy(); p.pop('page', None); qs_str = p.urlencode()
    return render(request, 'billing/invoice_list.html', {
        'invoices': invoices,
        'paginator': paginator,
        'page_obj': invoices,
        'is_paginated': paginator.num_pages > 1,
        'filter_qs_pfx': (qs_str + '&') if qs_str else '',
        'params': request.GET,
        'elided_page_range': paginator.get_elided_page_range(invoices.number, on_each_side=2, on_ends=1),
        'export_field_labels_json': json.dumps([lbl for lbl, _ in INVOICE_EXPORT_FIELDS], ensure_ascii=False),
    })


@login_required
@permission_required('billing.view_invoice', raise_exception=True)
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related('customer').prefetch_related('details__product'), pk=pk)
    return render(request, 'billing/invoice_detail.html', {'invoice': invoice})


@login_required
@permission_required('billing.view_invoice', raise_exception=True)
def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related('customer').prefetch_related('details__product'), pk=pk)
    return render(request, 'billing/invoice_pdf.html', {'invoice': invoice})


@login_required
@permission_required('billing.view_invoice', raise_exception=True)
def invoice_pdf_file(request, pk):
    """Descarga la factura como un archivo .pdf real (no la vista HTML para
    imprimir)."""
    invoice = get_object_or_404(Invoice.objects.select_related('customer').prefetch_related('details__product'), pk=pk)
    pdf_bytes = generar_factura_pdf(invoice)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="factura-{invoice.numero_completo}.pdf"'
    return response


@login_required
@permission_required('billing.change_invoice', raise_exception=True)
@require_POST
def invoice_autorizar_sri(request, pk):
    """Envía la factura a celcer (pruebas) firmando con el .p12 del modal.

    El certificado y la contraseña viajan solo en este POST; no se guardan.
    Si el cliente pide JSON (fetch del modal), responde JSON en vez de redirect.
    """
    wants_json = (
        'application/json' in (request.headers.get('Accept') or '')
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    )

    def _fail(msg, status=400):
        if wants_json:
            return JsonResponse({'ok': False, 'error': msg}, status=status)
        messages.error(request, msg)
        return redirect('billing:invoice_detail', pk=pk)

    def _ok(msg):
        if wants_json:
            return JsonResponse({
                'ok': True,
                'mensaje': msg,
                'redirect': f'/invoices/{pk}/',
            })
        messages.success(request, msg)
        return redirect('billing:invoice_detail', pk=pk)

    invoice = get_object_or_404(
        Invoice.objects.select_related('customer').prefetch_related('details__product'), pk=pk
    )
    if invoice.clave_acceso and invoice.estado_sri == 'autorizada':
        return _ok('Esta factura ya está autorizada electrónicamente.')

    cert = request.FILES.get('certificado')
    password = (request.POST.get('password') or '').strip()
    ruc_emisor = re.sub(r'\D', '', request.POST.get('ruc_emisor') or '')
    razon_social = (request.POST.get('razon_social_emisor') or '').strip()
    if not cert:
        return _fail('Selecciona tu archivo de certificado (.p12 / .pfx).')
    name = (cert.name or '').lower()
    if not (name.endswith('.p12') or name.endswith('.pfx')):
        return _fail('El certificado debe ser un archivo .p12 o .pfx.')
    if not password:
        return _fail('Ingresa la contraseña del certificado.')
    if len(ruc_emisor) != 13:
        return _fail('Ingresa el RUC del emisor (13 dígitos), el mismo del certificado.')
    if not razon_social:
        return _fail('Ingresa la razón social del emisor.')

    try:
        autorizar_factura_electronica(
            invoice,
            cert,
            password,
            cert.name,
            ruc_emisor=ruc_emisor,
            razon_social_emisor=razon_social,
        )
        return _ok(
            'Factura firmada y autorizada en el ambiente de PRUEBAS del SRI (celcer). '
            'El certificado no se almacenó en el servidor.'
        )
    except SriFacturacionServiceError as e:
        return _fail(f'No se pudo autorizar en SRI pruebas: {e}', status=502)
    except Exception as e:
        return _fail(f'Error al autorizar: {e}', status=500)


@login_required
@permission_required('billing.view_invoice', raise_exception=True)
def invoice_xml(request, pk):
    """Descarga el XML de autorización SRI como archivo .xml (no PDF / no XSLT)."""
    invoice = get_object_or_404(
        Invoice.objects.select_related('customer').prefetch_related('details__product'), pk=pk
    )
    if not invoice.clave_acceso:
        messages.error(
            request,
            'Esta factura está pendiente de autorización. Usa "Enviar al SRI (pruebas)" '
            'e indica tu certificado .p12 y contraseña.',
        )
        return redirect('billing:invoice_detail', pk=invoice.pk)

    xml_content = generar_xml_autorizacion(invoice, request)
    filename = f'factura-{invoice.numero_completo}.xml'
    response = HttpResponse(xml_content.encode('utf-8'), content_type='application/xml; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@permission_required('billing.view_invoice', raise_exception=True)
@require_POST
def invoice_send_email(request, pk):
    """Reenvía la factura electrónica por correo a pedido del usuario."""
    invoice = get_object_or_404(Invoice.objects.select_related('customer').prefetch_related('details__product'), pk=pk)
    if not invoice.customer.email:
        messages.error(request, 'Este cliente no tiene un correo registrado.')
    else:
        try:
            send_invoice_email(invoice, request)
            messages.success(request, f'Factura reenviada por correo a {invoice.customer.email}.')
        except Exception:
            messages.warning(request, 'No se pudo enviar el correo (revisa la configuración de email).')
    return redirect('billing:invoice_detail', pk=invoice.pk)


@login_required
@permission_required('billing.view_invoice', raise_exception=True)
@require_POST
def invoice_send_whatsapp(request, pk):
    """Envía al cliente el enlace de la factura por WhatsApp (microservicio :5004)."""
    invoice = get_object_or_404(
        Invoice.objects.select_related('customer').prefetch_related('details__product'),
        pk=pk,
    )
    if not (invoice.customer.phone or '').strip():
        messages.error(request, 'Este cliente no tiene un teléfono registrado.')
    else:
        try:
            result = send_invoice_whatsapp(invoice, request)
            proveedor = result.get('proveedor', 'whatsapp')
            emisor = result.get('numero_emisor')
            extra = f' desde +{emisor}' if emisor else ''
            messages.success(
                request,
                f'Factura enviada por WhatsApp{extra} a {invoice.customer.phone} '
                f'(proveedor: {proveedor}).',
            )
        except ValueError as e:
            messages.error(request, str(e))
        except WhatsAppServiceError as e:
            messages.warning(request, f'No se pudo enviar por WhatsApp: {e}')
        except Exception:
            messages.warning(
                request,
                'No se pudo enviar por WhatsApp (¿está corriendo whatsapp_service en :5004?).',
            )
    return redirect('billing:invoice_detail', pk=invoice.pk)


def invoice_pdf_public(request, token):
    """Vista pública (sin login) para que el cliente vea/descargue su factura
    desde el enlace del correo. El acceso lo protege el token firmado, no una
    sesión — por eso NO lleva @login_required/@permission_required."""
    try:
        pk = verify_invoice_token(token)
    except signing.BadSignature:
        return render(request, 'billing/invoice_pdf_invalid.html', status=403)
    invoice = get_object_or_404(
        Invoice.objects.select_related('customer').prefetch_related('details__product'), pk=pk
    )
    return render(request, 'billing/invoice_pdf.html', {
        'invoice': invoice, 'is_public': True, 'public_token': token,
        'paypal_client_id': settings.PAYPAL_CLIENT_ID,
    })


def invoice_pdf_file_public(request, token):
    """Descarga pública (sin login) de la factura como archivo .pdf real —
    es el enlace que se manda en el correo, para que al abrirlo en Gmail
    entregue directamente el PDF en vez de una página web."""
    try:
        pk = verify_invoice_token(token)
    except signing.BadSignature:
        return render(request, 'billing/invoice_pdf_invalid.html', status=403)
    invoice = get_object_or_404(
        Invoice.objects.select_related('customer').prefetch_related('details__product'), pk=pk
    )
    pdf_bytes = generar_factura_pdf(invoice)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="factura-{invoice.numero_completo}.pdf"'
    return response


def invoice_xml_public(request, token):
    """Versión pública (sin login) de la descarga del XML, para el cliente
    que llegó desde el enlace del correo/WhatsApp — misma protección por
    token firmado que invoice_pdf_public."""
    try:
        pk = verify_invoice_token(token)
    except signing.BadSignature:
        return render(request, 'billing/invoice_pdf_invalid.html', status=403)
    invoice = get_object_or_404(
        Invoice.objects.select_related('customer').prefetch_related('details__product'), pk=pk
    )
    if not invoice.clave_acceso:
        return render(request, 'billing/invoice_pdf_invalid.html', status=403)
    xml_content = generar_xml_autorizacion(invoice, request)
    filename = f'factura-{invoice.numero_completo}.xml'
    response = HttpResponse(xml_content.encode('utf-8'), content_type='application/xml; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@permission_required('billing.add_invoice', raise_exception=True)
@transaction.atomic
def invoice_create(request):
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        formset = InvoiceDetailFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            credit_error = _check_credit_limit(form, formset)
            if credit_error:
                form.add_error('tipo_pago', credit_error)
            else:
                invoice = form.save()
                invoice.number = _next_invoice_number()
                invoice.save()
                formset.instance = invoice
                details = formset.save()
                invoice.recalculate()
                for detail in details:
                    Product.objects.filter(pk=detail.product_id).update(stock=F('stock') - detail.quantity)
                messages.success(
                    request,
                    f'Factura #{invoice.number} creada. Para enviarla al SRI (pruebas), '
                    f'abre el detalle y usa "Enviar al SRI" con tu certificado .p12.',
                )
                if invoice.customer.email:
                    try:
                        send_invoice_email(invoice, request)
                        messages.info(request, f'Factura enviada por correo a {invoice.customer.email}.')
                    except Exception:
                        messages.warning(request, 'La factura se creó, pero no se pudo enviar por correo (revisa la configuración de email).')
                return redirect('billing:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm()
        formset = InvoiceDetailFormSet()
    products_json = json.dumps({
        str(p.pk): {'price': str(p.unit_price), 'stock': p.stock}
        for p in Product.objects.filter(is_active=True)
    })
    generic_customers_json = json.dumps([
        c.pk for c in Customer.objects.filter(is_active=True, is_generic=True)
    ])
    return render(request, 'billing/invoice_form.html', {
        'form': form, 'formset': formset,
        'title': 'Nueva Factura', 'products_json': products_json,
        'generic_customers_json': generic_customers_json,
    })


@login_required
@permission_required('billing.change_invoice', raise_exception=True)
@transaction.atomic
def invoice_update(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceDetailFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            credit_error = _check_credit_limit(form, formset, exclude_pk=invoice.pk)
            if credit_error:
                form.add_error('tipo_pago', credit_error)
            else:
                old_qty = {d.product_id: d.quantity for d in invoice.details.all()}
                form.save()
                formset.save()
                invoice.recalculate()
                new_qty = {}
                for d in invoice.details.all():
                    new_qty[d.product_id] = new_qty.get(d.product_id, 0) + d.quantity
                for pid in set(old_qty) | set(new_qty):
                    delta = old_qty.get(pid, 0) - new_qty.get(pid, 0)
                    if delta != 0:
                        Product.objects.filter(pk=pid).update(stock=F('stock') + delta)
                messages.success(request, 'Factura actualizada.')
                return redirect('billing:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice)
        formset = InvoiceDetailFormSet(instance=invoice)
    # Para el JS: mostrar stock disponible = stock actual + lo que ya tiene esta factura
    existing = {d.product_id: d.quantity for d in invoice.details.all()}
    products_json = json.dumps({
        str(p.pk): {
            'price': str(p.unit_price),
            'stock': p.stock + existing.get(p.pk, 0),
        }
        for p in Product.objects.filter(is_active=True)
    })
    generic_customers_json = json.dumps([
        c.pk for c in Customer.objects.filter(is_active=True, is_generic=True)
    ])
    return render(request, 'billing/invoice_form.html', {
        'form': form, 'formset': formset,
        'title': 'Editar Factura', 'products_json': products_json,
        'generic_customers_json': generic_customers_json,
    })


@login_required
@permission_required('billing.delete_invoice', raise_exception=True)
def invoice_delete(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        num = invoice.number
        invoice.is_active = False
        invoice.number = None
        invoice.save()
        messages.success(request, f'Factura #{num} anulada.')
        return redirect('billing:invoice_list')
    return render(request, 'billing/invoice_confirm_delete.html', {'object': invoice})

