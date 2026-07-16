from django.db import models

from billing.models import Invoice


class CobroFactura(models.Model):
    METODO_PAGO = [('manual', 'Manual'), ('paypal', 'PayPal')]

    factura = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='cobros', verbose_name='Factura')
    fecha = models.DateField(verbose_name='Fecha de Pago')
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor Abonado')
    observacion = models.TextField(blank=True, verbose_name='Observación')
    metodo_pago = models.CharField(max_length=10, choices=METODO_PAGO, default='manual', verbose_name='Método de Pago')
    paypal_order_id = models.CharField(max_length=64, blank=True, verbose_name='ID de Orden PayPal')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Registrado')

    class Meta:
        verbose_name = 'Cobro de Factura'
        verbose_name_plural = 'Cobros de Facturas'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Abono $ {self.valor} - Factura #{self.factura.number or self.factura.id}'


class Notification(models.Model):
    mensaje = models.CharField(max_length=255, verbose_name='Mensaje')
    factura = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name='notificaciones',
        null=True, blank=True, verbose_name='Factura',
    )
    leida = models.BooleanField(default=False, verbose_name='Leída')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creada')

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-created_at']

    def __str__(self):
        return self.mensaje
