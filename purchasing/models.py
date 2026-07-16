from django.db import models
from decimal import Decimal
from billing.models import Supplier, Product


class Purchase(models.Model):
    TIPO_PAGO = [('contado', 'Contado'), ('credito', 'Crédito')]
    ESTADO_PAGO = [('pendiente', 'Pendiente'), ('pagada', 'Pagada')]

    number = models.PositiveIntegerField(null=True, blank=True, verbose_name='N° Compra')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchases', verbose_name='Proveedor')
    document_number = models.CharField(max_length=20, verbose_name='N° Factura Proveedor')
    purchase_date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Subtotal')
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='IVA (15%)')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Total')
    tipo_pago = models.CharField(max_length=10, choices=TIPO_PAGO, default='contado', verbose_name='Tipo de Pago')
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Saldo Pendiente')
    estado = models.CharField(max_length=10, choices=ESTADO_PAGO, default='pagada', verbose_name='Estado de Pago')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Compra'
        verbose_name_plural = 'Compras'
        ordering = ['-purchase_date']
        unique_together = ('supplier', 'document_number')

    def __str__(self):
        return f'Compra #{self.number or self.id} - {self.supplier}'

    def recalculate(self):
        self.subtotal = sum(d.subtotal for d in self.details.all())
        self.tax = (self.subtotal * Decimal('0.15')).quantize(Decimal('0.01'))
        self.total = self.subtotal + self.tax
        self.actualizar_saldo(save=False)
        self.save()

    def actualizar_saldo(self, save=True):
        """Recalcula saldo y estado a partir del total y los pagos registrados."""
        if self.tipo_pago == 'credito':
            pagado = self.pagos.aggregate(t=models.Sum('valor'))['t'] or Decimal('0.00')
            self.saldo = max(self.total - pagado, Decimal('0.00'))
            self.estado = 'pagada' if self.saldo <= 0 else 'pendiente'
        else:
            self.saldo = Decimal('0.00')
            self.estado = 'pagada'
        if save:
            self.save(update_fields=['saldo', 'estado'])


class PurchaseDetail(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='details', verbose_name='Compra')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchase_details', verbose_name='Producto')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Cantidad')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Costo Unitario')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Subtotal')

    class Meta:
        verbose_name = 'Detalle de Compra'
        verbose_name_plural = 'Detalles de Compra'

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(str(self.quantity)) * self.unit_cost
        super().save(*args, **kwargs)


