import functools
import logging

from django.core.exceptions import PermissionDenied
from django.contrib.auth.views import redirect_to_login

logger = logging.getLogger(__name__)


def staff_required(view_func):
    """Redirige a login si no autenticado; devuelve 403 si no es staff/superusuario."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def audit_action(action_name):
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            user = request.user if request.user.is_authenticated else 'anonymous'
            logger.info(f'AUDIT | user={user} | action={action_name} | path={request.path}')
            return response
        return wrapper
    return decorator
