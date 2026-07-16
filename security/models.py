import random
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

CODE_VALID_MINUTES = 15


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
