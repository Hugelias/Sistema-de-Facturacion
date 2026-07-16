from django.db import models
from decimal import Decimal
from shared.validators import validate_cedula_ec


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    description = models.TextField(blank=True, verbose_name='Descripción')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductGroup(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    description = models.TextField(blank=True, verbose_name='Descripción')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Grupo de Producto'
        verbose_name_plural = 'Grupos de Productos'
        ordering = ['name']

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=200, verbose_name='Nombre')
    ruc = models.CharField(max_length=20, blank=True, verbose_name='RUC')
    contact_name = models.CharField(max_length=200, blank=True, verbose_name='Contacto')
    email = models.EmailField(blank=True, verbose_name='Email')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    address = models.TextField(blank=True, verbose_name='Dirección')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name='Nombre')
    description = models.TextField(blank=True, verbose_name='Descripción')
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='products', verbose_name='Marca')
    group = models.ForeignKey(ProductGroup, on_delete=models.PROTECT, related_name='products', verbose_name='Grupo')
    suppliers = models.ManyToManyField(Supplier, related_name='products', blank=True, verbose_name='Proveedores')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio Unitario')
    stock = models.PositiveIntegerField(default=0, verbose_name='Stock')
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name='Foto')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['name']

    def __str__(self):
        return self.name


class Customer(models.Model):
    CONSUMIDOR_FINAL_DNI = '9999999999999'
    NEW_CUSTOMER_CREDIT_LIMIT = Decimal('400.00')
    GOOD_HISTORY_CREDIT_LIMIT = Decimal('2000.00')

    dni = models.CharField(max_length=13, unique=True, verbose_name='Cédula/RUC', validators=[validate_cedula_ec])
    first_name = models.CharField(max_length=100, verbose_name='Nombres')
    last_name = models.CharField(max_length=100, verbose_name='Apellidos')
    email = models.EmailField(blank=True, verbose_name='Email')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    city = models.CharField(max_length=100, blank=True, verbose_name='Ciudad')
    address = models.TextField(blank=True, verbose_name='Dirección')
    is_generic = models.BooleanField(default=False, verbose_name='Consumidor Final Genérico')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True, null=True, verbose_name='Registrado')

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def _credit_history_flags(self):
        """Devuelve (tiene_historial, tiene_credito_pendiente).

        Usa las anotaciones `has_credit_history`/`has_pending_credit` si el
        queryset ya las trae (ver InvoiceForm), o consulta bajo demanda.
        """
        if hasattr(self, 'has_credit_history'):
            return self.has_credit_history, getattr(self, 'has_pending_credit', False)
        credit_qs = self.invoices.filter(tipo_pago='credito', is_active=True)
        has_history = credit_qs.exists()
        has_pending = has_history and credit_qs.filter(estado='pendiente').exists()
        return has_history, has_pending

    def get_credit_limit(self):
        """$400 para clientes nuevos en crédito; $2000 si ya usaron crédito
        antes y lo pagaron por completo (sin saldo pendiente actualmente)."""
        if self.is_generic:
            return Decimal('0.00')
        has_history, has_pending = self._credit_history_flags()
        if not has_history or has_pending:
            return self.NEW_CUSTOMER_CREDIT_LIMIT
        return self.GOOD_HISTORY_CREDIT_LIMIT

    def credit_status_label(self):
        if self.is_generic:
            return 'Consumidor Final'
        has_history, has_pending = self._credit_history_flags()
        if not has_history:
            return 'Nuevo en crédito'
        if has_pending:
            return 'Crédito pendiente'
        return 'Historial de crédito bueno'


class CustomerProfile(models.Model):
    TAXPAYER = [('final', 'Final Consumer'), ('ruc', 'RUC'), ('rise', 'RISE')]
    PAYMENT = [
        ('cash', 'Cash'),
        ('credit_15', '15 days'),
        ('credit_30', '30 days'),
        ('credit_60', '60 days'),
    ]

    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='profile')
    taxpayer_type = models.CharField(max_length=10, choices=TAXPAYER, default='final')
    payment_terms = models.CharField(max_length=15, choices=PAYMENT, default='cash')
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Customer Profile'

    def __str__(self):
        return f'Profile: {self.customer}'


class Invoice(models.Model):
    TIPO_PAGO = [('contado', 'Contado'), ('credito', 'Crédito')]
    ESTADO_COBRO = [('pendiente', 'Pendiente'), ('pagada', 'Pagada')]
    AMBIENTE_SRI = [('1', 'Pruebas'), ('2', 'Producción')]
    ESTADO_SRI = [('pendiente', 'Pendiente'), ('autorizada', 'Autorizada'), ('no_autorizada', 'No autorizada')]

    number = models.PositiveIntegerField(null=True, blank=True, verbose_name='N° Factura')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices', verbose_name='Cliente')
    invoice_date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Subtotal')
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='IVA (15%)')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Total')
    tipo_pago = models.CharField(max_length=10, choices=TIPO_PAGO, default='contado', verbose_name='Tipo de Pago')
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Saldo Pendiente')
    estado = models.CharField(max_length=10, choices=ESTADO_COBRO, default='pagada', verbose_name='Estado de Cobro')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    # ── Facturación electrónica (simulación estilo SRI Ecuador) ─────────────
    establecimiento = models.CharField(max_length=3, default='001', verbose_name='Establecimiento')
    punto_emision = models.CharField(max_length=3, default='001', verbose_name='Punto de Emisión')
    ambiente = models.CharField(max_length=1, choices=AMBIENTE_SRI, default='1', verbose_name='Ambiente')
    clave_acceso = models.CharField(max_length=49, blank=True, verbose_name='Clave de Acceso')
    numero_autorizacion = models.CharField(max_length=49, blank=True, verbose_name='N° Autorización')
    fecha_autorizacion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Autorización')
    estado_sri = models.CharField(max_length=15, choices=ESTADO_SRI, default='pendiente', verbose_name='Estado SRI')
    ruc_emisor = models.CharField(max_length=13, blank=True, verbose_name='RUC Emisor')
    razon_social_emisor = models.CharField(max_length=300, blank=True, verbose_name='Razón Social Emisor')
    xml_autorizado = models.TextField(blank=True, verbose_name='XML autorizado / firmado')

    class Meta:
        verbose_name = 'Factura'
        verbose_name_plural = 'Facturas'
        ordering = ['-invoice_date']
        permissions = [('can_export', 'Puede exportar reportes a PDF/Excel')]

    def __str__(self):
        return f'Factura #{self.number or self.id} - {self.customer.full_name}'

    @property
    def numero_completo(self):
        """Formato SRI: establecimiento-puntoEmision-secuencial (001-001-000000123)."""
        return f'{self.establecimiento}-{self.punto_emision}-{(self.number or 0):09d}'

    def recalculate(self):
        self.subtotal = sum(d.subtotal for d in self.details.all())
        self.tax = (self.subtotal * Decimal('0.15')).quantize(Decimal('0.01'))
        self.total = self.subtotal + self.tax
        self.actualizar_saldo(save=False)
        self.save()

    def actualizar_saldo(self, save=True):
        """Recalcula saldo y estado a partir del total y los abonos (cobros) registrados."""
        if self.tipo_pago == 'credito':
            abonado = self.cobros.aggregate(t=models.Sum('valor'))['t'] or Decimal('0.00')
            self.saldo = max(self.total - abonado, Decimal('0.00')).quantize(Decimal('0.01'))
            self.estado = 'pagada' if self.saldo <= 0 else 'pendiente'
        else:
            self.saldo = Decimal('0.00')
            self.estado = 'pagada'
        if save:
            self.save(update_fields=['saldo', 'estado'])


class InvoiceDetail(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='details', verbose_name='Factura')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='invoice_details', verbose_name='Producto')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Cantidad')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio Unitario')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Subtotal')

    class Meta:
        verbose_name = 'Detalle de Factura'
        verbose_name_plural = 'Detalles de Factura'

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(str(self.quantity)) * self.unit_price
        super().save(*args, **kwargs)
