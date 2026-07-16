from django.db import models

from purchasing.models import Purchase


class PagoCompra(models.Model):
    compra = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name='pagos', verbose_name='Compra')
    fecha = models.DateField(verbose_name='Fecha de Pago')
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor Pagado')
    observacion = models.TextField(blank=True, verbose_name='Observación')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Registrado')

    class Meta:
        verbose_name = 'Pago de Compra'
        verbose_name_plural = 'Pagos de Compras'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Pago $ {self.valor} - Compra #{self.compra.number or self.compra.id}'
