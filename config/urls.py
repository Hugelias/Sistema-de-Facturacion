from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from security.views import RoleAwareLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', RoleAwareLoginView.as_view(), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('security.urls')),
    path('', include('billing.urls')),
    path('purchasing/', include('purchasing.urls')),
    path('cobros/', include('cobros.urls')),
    path('pagos/', include('pagos.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
