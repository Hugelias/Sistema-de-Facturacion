from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    # Auth
    path('accounts/select-role/', views.role_select, name='role_select'),
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/password-reset/', views.password_reset_request, name='password_reset_request'),
    path('accounts/password-reset/verificar/', views.password_reset_verify, name='password_reset_verify'),
    path('accounts/login/2fa/', views.login_2fa, name='login_2fa'),

    # Users
    path('security/users/', views.user_list, name='user_list'),
    path('security/users/create/', views.user_create, name='user_create'),
    path('security/users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('security/users/<int:pk>/toggle/', views.user_toggle, name='user_toggle'),
    path('security/users/<int:pk>/delete/', views.user_delete, name='user_delete'),

    # Groups
    path('security/groups/', views.group_list, name='group_list'),
    path('security/groups/create/', views.group_create, name='group_create'),
    path('security/groups/<int:pk>/edit/', views.group_edit, name='group_edit'),
]
