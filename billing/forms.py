from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef
from django.forms import inlineformset_factory
from .models import Brand, Customer, Product, ProductGroup, Supplier, Invoice, InvoiceDetail


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ('name', 'image', 'brand', 'group', 'unit_price', 'stock', 'suppliers', 'is_active', 'description')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del producto...',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Descripción del producto...',
            }),
            'brand': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'suppliers': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': '4',
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00',
                'id': 'id_unit_price',
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'id': 'id_stock',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'id': 'id_image',
            }),
        }

    def clean_unit_price(self):
        price = self.cleaned_data.get('unit_price')
        if price is not None and price <= Decimal('0'):
            raise ValidationError('El precio debe ser mayor a 0.')
        return price


class ActiveSelect(forms.Select):
    def __init__(self, attrs=None):
        super().__init__(attrs, choices=[('True', 'Activo'), ('False', 'Inactivo')])


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ('name', 'description', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ingrese el nombre de la marca'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Ingrese una descripción (opcional)'}),
            'is_active': ActiveSelect(),
        }


class ProductGroupForm(forms.ModelForm):
    class Meta:
        model = ProductGroup
        fields = ('name', 'description', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Ingrese el nombre del grupo',
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Ingrese una descripción (opcional)',
            }),
            'is_active': ActiveSelect(),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ('name', 'ruc', 'contact_name', 'email', 'phone', 'address', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Ingrese el nombre o razón social',
            }),
            'ruc': forms.TextInput(attrs={
                'placeholder': 'Ingrese el RUC o cédula',
            }),
            'contact_name': forms.TextInput(attrs={
                'placeholder': 'Nombre del contacto principal',
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'Ingrese el correo electrónico',
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': 'Ingrese el teléfono',
            }),
            'address': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Ingrese la dirección completa',
            }),
            'is_active': ActiveSelect(),
        }


class CustomerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, customer):
        if customer.is_generic:
            return f'{customer.full_name} — Consumidor Final'
        limit = customer.get_credit_limit()
        return f'{customer.full_name} — {customer.credit_status_label()} (límite $ {limit:.0f})'


class InvoiceForm(forms.ModelForm):
    customer = CustomerChoiceField(
        queryset=Customer.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Cliente',
    )

    class Meta:
        model = Invoice
        fields = ('customer', 'tipo_pago')
        widgets = {
            'tipo_pago': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Anotamos si el cliente ya usó crédito antes y si tiene saldo pendiente,
        # excluyendo la propia factura cuando se está editando una existente.
        credit_qs = Invoice.objects.filter(customer=OuterRef('pk'), tipo_pago='credito', is_active=True)
        if self.instance.pk:
            credit_qs = credit_qs.exclude(pk=self.instance.pk)
        pending_qs = credit_qs.filter(estado='pendiente')
        self.fields['customer'].empty_label = 'Seleccione un cliente'
        self.fields['customer'].queryset = (
            Customer.objects.filter(is_active=True)
            .annotate(has_credit_history=Exists(credit_qs), has_pending_credit=Exists(pending_qs))
            .order_by('last_name', 'first_name')
        )

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get('customer')
        if customer and customer.is_generic and cleaned.get('tipo_pago') == 'credito':
            self.add_error(
                'tipo_pago',
                'No se puede vender a crédito al Consumidor Final: no se cuenta con datos suficientes del cliente.',
            )
        return cleaned


class InvoiceDetailForm(forms.ModelForm):
    class Meta:
        model = InvoiceDetail
        fields = ('product', 'quantity', 'unit_price')
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select product-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control qty-input', 'min': 1}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control price-input', 'step': '0.01', 'min': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].empty_label = 'Seleccione un producto'

    def clean(self):
        data = super().clean()
        product = data.get('product')
        quantity = data.get('quantity')
        if product and quantity is not None:
            available = product.stock
            if self.instance.pk:
                available += self.instance.quantity
            if quantity > available:
                self.add_error(
                    'quantity',
                    f'Stock insuficiente. Disponible: {available} unidad(es).',
                )
        return data


class BaseInvoiceDetailFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            cleaned = getattr(form, 'cleaned_data', None)
            if not cleaned or cleaned.get('DELETE'):
                continue
            product = cleaned.get('product')
            if product is None:
                continue
            if product.pk in seen:
                form.add_error('product', f'El producto "{product.name}" ya está en otra línea de esta factura.')
                raise ValidationError(
                    f'El producto "{product.name}" está duplicado. Combina las cantidades en una sola línea.'
                )
            seen.add(product.pk)


InvoiceDetailFormSet = inlineformset_factory(
    Invoice,
    InvoiceDetail,
    form=InvoiceDetailForm,
    formset=BaseInvoiceDetailFormSet,
    extra=1,
    can_delete=True,
)

