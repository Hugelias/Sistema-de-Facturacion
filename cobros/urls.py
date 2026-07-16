from django.urls import path

from . import views

app_name = 'cobros'

urlpatterns = [
    path('pendientes/', views.factura_pendiente_list, name='factura_pendiente_list'),
    path('facturas/<int:factura_pk>/pagos/', views.cobro_historial, name='cobro_historial'),
    path('facturas/<int:factura_pk>/pagos/nuevo/', views.cobro_create, name='cobro_create'),
    path('pagos/<int:pk>/edit/', views.cobro_update, name='cobro_update'),
    path('pagos/<int:pk>/delete/', views.cobro_delete, name='cobro_delete'),

    # PayPal — ventana emergente (approve_url) + retorno/cancelación
    path('facturas/<int:factura_pk>/paypal/crear-orden/', views.cobro_paypal_create_order, name='cobro_paypal_create_order'),
    path('facturas/<int:factura_pk>/paypal/retorno/', views.cobro_paypal_return, name='cobro_paypal_return'),
    path('facturas/<int:factura_pk>/paypal/cancelar/', views.cobro_paypal_cancel, name='cobro_paypal_cancel'),
    path('facturas/<int:factura_pk>/paypal/capturar-orden/<str:order_id>/', views.cobro_paypal_capture_order, name='cobro_paypal_capture_order'),

    # PayPal — versión pública (sin login), mismo token del PDF público de la factura
    path('facturas/ver/<str:token>/paypal/crear-orden/', views.cobro_paypal_public_create_order, name='cobro_paypal_public_create_order'),
    path('facturas/ver/<str:token>/paypal/retorno/', views.cobro_paypal_public_return, name='cobro_paypal_public_return'),
    path('facturas/ver/<str:token>/paypal/cancelar/', views.cobro_paypal_public_cancel, name='cobro_paypal_public_cancel'),
    path('facturas/ver/<str:token>/paypal/capturar-orden/<str:order_id>/', views.cobro_paypal_public_capture_order, name='cobro_paypal_public_capture_order'),

    # Notificaciones (campanita de la barra superior)
    path('notificaciones/<int:pk>/abrir/', views.notification_open, name='notification_open'),
    path('notificaciones/marcar-todas/', views.notification_mark_all_read, name='notification_mark_all_read'),
]
