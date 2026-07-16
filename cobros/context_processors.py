from .models import Notification


def notifications(request):
    """Notificaciones para la campanita de la barra superior. Solo para el
    personal que puede ver cobros (quienes deben enterarse de los abonos)."""
    if not request.user.is_authenticated or not request.user.has_perm('cobros.view_cobrofactura'):
        return {}
    qs = Notification.objects.select_related('factura')
    return {
        'nav_notifications': qs[:8],
        'nav_notifications_unread': qs.filter(leida=False).count(),
    }
