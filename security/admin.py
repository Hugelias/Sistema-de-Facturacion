from django.contrib import admin

from .models import LoginOTPCode, PasswordResetCode, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'two_factor_enabled')
    list_filter = ('two_factor_enabled',)
    search_fields = ('user__username', 'phone')


@admin.register(LoginOTPCode)
class LoginOTPCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'created_at', 'used')
    list_filter = ('used',)
    search_fields = ('user__username', 'code')
    readonly_fields = ('created_at',)


@admin.register(PasswordResetCode)
class PasswordResetCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'created_at', 'used')
    list_filter = ('used',)
