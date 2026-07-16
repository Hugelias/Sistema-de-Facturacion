from django.contrib import admin

from .models import PagoCompra


@admin.register(PagoCompra)
class PagoCompraAdmin(admin.ModelAdmin):
    list_display = ('compra', 'fecha', 'valor', 'created_at')
    list_filter = ('fecha',)
    search_fields = ('compra__number', 'compra__supplier__name')
