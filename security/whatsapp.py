"""Envío de códigos 2FA por el microservicio WhatsApp (:5004)."""
from billing.whatsapp_client import WhatsAppServiceError, enviar_mensaje

from .models import LOGIN_OTP_VALID_MINUTES


def send_login_otp_whatsapp(user, otp) -> dict:
    profile = getattr(user, 'profile', None)
    phone = (profile.phone if profile else '') or ''
    if not phone.strip():
        raise WhatsAppServiceError('El usuario no tiene teléfono registrado para 2FA.')

    nombre = user.get_full_name() or user.username
    mensaje = (
        f'*TecnoStock S.A.*\n'
        f'Hola {nombre},\n\n'
        f'Tu código de acceso es: *{otp.code}*\n'
        f'Válido por {LOGIN_OTP_VALID_MINUTES} minutos.\n\n'
        f'Si no intentaste iniciar sesión, ignora este mensaje.'
    )
    return enviar_mensaje(phone.strip(), mensaje)
