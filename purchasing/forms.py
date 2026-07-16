from django import forms
from django.forms import inlineformset_factory
from .models import Purchase, PurchaseDetail


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ('supplier', 'document_number', 'tipo_pago')
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'document_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: FAC-001'}),
            'tipo_pago': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        data = super().clean()
        supplier = data.get('supplier')
        doc_num = data.get('document_number')
        if supplier and doc_num:
            qs = Purchase.objects.filter(supplier=supplier, document_number=doc_num)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('document_number',
                    f'Ya existe una compra con el N° "{doc_num}" para este proveedor.')
        return data


PurchaseDetailFormSet = inlineformset_factory(
    Purchase,
    PurchaseDetail,
    fields=('product', 'quantity', 'unit_cost'),
    extra=1,
    can_delete=True,
    widgets={
        'product': forms.Select(attrs={'class': 'form-select'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    }
)
