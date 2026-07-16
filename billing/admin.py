from django.contrib import admin
from .models import Brand, ProductGroup, Supplier, Product, Customer, CustomerProfile, Invoice, InvoiceDetail


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_name', 'email', 'phone', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'contact_name', 'email')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'group', 'unit_price', 'stock', 'is_active')
    list_filter = ('is_active', 'brand', 'group')
    search_fields = ('name',)
    filter_horizontal = ('suppliers',)


class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    can_delete = False
    extra = 1


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'dni', 'email', 'phone', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('first_name', 'last_name', 'dni', 'email')
    inlines = [CustomerProfileInline]


class InvoiceDetailInline(admin.TabularInline):
    model = InvoiceDetail
    extra = 1
    readonly_fields = ('subtotal',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'invoice_date', 'subtotal', 'tax', 'total', 'is_active')
    list_filter = ('is_active', 'invoice_date')
    search_fields = ('customer__first_name', 'customer__last_name', 'customer__dni')
    readonly_fields = ('subtotal', 'tax', 'total', 'invoice_date')
    inlines = [InvoiceDetailInline]
