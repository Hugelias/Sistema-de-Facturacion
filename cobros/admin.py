from django.contrib import admin

from .models import CobroFactura, Notification


@admin.register(CobroFactura)
class CobroFacturaAdmin(admin.ModelAdmin):
    list_display = ('factura', 'fecha', 'valor', 'created_at')
    list_filter = ('fecha',)
    search_fields = ('factura__number', 'factura__customer__first_name', 'factura__customer__last_name')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('mensaje', 'factura', 'leida', 'created_at')
    list_filter = ('leida',)
    search_fields = ('mensaje',)
