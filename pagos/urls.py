from django.urls import path

from . import views

app_name = 'pagos'

urlpatterns = [
    path('pendientes/', views.compra_pendiente_list, name='compra_pendiente_list'),
    path('compras/<int:compra_pk>/pagos/', views.pago_historial, name='pago_historial'),
    path('compras/<int:compra_pk>/pagos/nuevo/', views.pago_create, name='pago_create'),
    path('pagos/<int:pk>/edit/', views.pago_update, name='pago_update'),
    path('pagos/<int:pk>/delete/', views.pago_delete, name='pago_delete'),
]
