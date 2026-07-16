# Generated manually for 2FA WhatsApp

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('security', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(blank=True, help_text='Número al que se enviará el código de verificación al iniciar sesión.', max_length=20, verbose_name='Teléfono WhatsApp')),
                ('two_factor_enabled', models.BooleanField(default=False, help_text='Si está activo, tras usuario/contraseña se exige un código enviado por WhatsApp.', verbose_name='Autenticación en dos pasos (WhatsApp)')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Perfil de usuario',
                'verbose_name_plural': 'Perfiles de usuario',
            },
        ),
        migrations.CreateModel(
            name='LoginOTPCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=6)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('used', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_otp_codes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Código 2FA WhatsApp',
                'verbose_name_plural': 'Códigos 2FA WhatsApp',
                'ordering': ['-created_at'],
            },
        ),
    ]
