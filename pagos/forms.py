from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PagoCompra


class PagoCompraForm(forms.ModelForm):
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
        input_formats=['%Y-%m-%d'],
        label='Fecha de Pago',
    )

    class Meta:
        model = PagoCompra
        fields = ('fecha', 'valor', 'observacion')
        widgets = {
            'valor': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00',
            }),
            'observacion': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3, 'placeholder': 'Observación (opcional)',
            }),
        }

    def __init__(self, *args, compra=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.compra = compra

    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        if fecha and self.compra:
            fecha_compra = timezone.localtime(self.compra.purchase_date).date()
            if fecha < fecha_compra:
                raise ValidationError(
                    f'La fecha de pago no puede ser anterior a la fecha de la compra ({fecha_compra:%d/%m/%Y}).'
                )
        return fecha

    def clean_valor(self):
        valor = self.cleaned_data.get('valor')
        if valor is None:
            return valor
        if valor <= Decimal('0'):
            raise ValidationError('El valor del pago debe ser mayor a 0.')
        saldo_disponible = self.compra.saldo
        if self.instance.pk:
            saldo_disponible += self.instance.valor
        if valor > saldo_disponible:
            raise ValidationError(f'El pago no puede ser mayor al saldo pendiente ($ {saldo_disponible}).')
        return valor
