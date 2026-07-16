import random
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

CODE_VALID_MINUTES = 15
LOGIN_OTP_VALID_MINUTES = 10


class UserProfile(models.Model):
    """Datos extra del usuario (teléfono para 2FA por WhatsApp)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono WhatsApp',
        help_text='Número al que se enviará el código de verificación al iniciar sesión.',
    )
    two_factor_enabled = models.BooleanField(
        default=False,
        verbose_name='Autenticación en dos pasos (WhatsApp)',
        help_text='Si está activo, tras usuario/contraseña se exige un código enviado por WhatsApp.',
    )

    class Meta:
        verbose_name = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuario'

    def __str__(self):
        return f'Perfil de {self.user.username}'

    def requiere_2fa(self):
        return self.two_factor_enabled and bool((self.phone or '').strip())

    def telefono_enmascarado(self):
        digits = ''.join(c for c in (self.phone or '') if c.isdigit())
        if len(digits) < 4:
            return '****'
        return f'***{digits[-4:]}'


class PasswordResetCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reset_codes')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Código de Restablecimiento'
        verbose_name_plural = 'Códigos de Restablecimiento'
        ordering = ['-created_at']

    def __str__(self):
        return f'Código para {self.user.username} ({timezone.localtime(self.created_at):%d/%m/%Y %H:%M})'

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=CODE_VALID_MINUTES)

    def is_valid(self):
        return not self.used and not self.is_expired()

    @classmethod
    def generar_para(cls, user):
        """Invalida los códigos anteriores del usuario y genera uno nuevo."""
        cls.objects.filter(user=user, used=False).update(used=True)
        code = f'{random.randint(0, 999999):06d}'
        return cls.objects.create(user=user, code=code)


class LoginOTPCode(models.Model):
    """Código temporal de 2FA enviado por WhatsApp al iniciar sesión."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='login_otp_codes',
    )
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Código 2FA WhatsApp'
        verbose_name_plural = 'Códigos 2FA WhatsApp'
        ordering = ['-created_at']

    def __str__(self):
        return f'OTP login {self.user.username} ({self.code})'

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=LOGIN_OTP_VALID_MINUTES)

    def is_valid(self):
        return not self.used and not self.is_expired()

    @classmethod
    def generar_para(cls, user):
        cls.objects.filter(user=user, used=False).update(used=True)
        code = f'{random.randint(0, 999999):06d}'
        return cls.objects.create(user=user, code=code)
