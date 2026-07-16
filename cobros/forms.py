from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import CobroFactura


class CobroFacturaForm(forms.ModelForm):
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
        input_formats=['%Y-%m-%d'],
        label='Fecha de Pago',
    )

    class Meta:
        model = CobroFactura
        fields = ('fecha', 'valor', 'observacion')
        widgets = {
            'valor': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00',
            }),
            'observacion': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3, 'placeholder': 'Observación (opcional)',
            }),
        }

    def __init__(self, *args, factura=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.factura = factura

    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        if fecha and self.factura:
            fecha_factura = timezone.localtime(self.factura.invoice_date).date()
            if fecha < fecha_factura:
                raise ValidationError(
                    f'La fecha de pago no puede ser anterior a la fecha de la factura ({fecha_factura:%d/%m/%Y}).'
                )
        return fecha

    def clean_valor(self):
        valor = self.cleaned_data.get('valor')
        if valor is None:
            return valor
        if valor <= Decimal('0'):
            raise ValidationError('El valor del abono debe ser mayor a 0.')
        saldo_disponible = self.factura.saldo
        if self.instance.pk:
            saldo_disponible += self.instance.valor
        if valor > saldo_disponible:
            raise ValidationError(f'El abono no puede ser mayor al saldo pendiente ($ {saldo_disponible}).')
        return valor
