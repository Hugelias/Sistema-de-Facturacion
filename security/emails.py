from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .models import CODE_VALID_MINUTES


def send_password_reset_code_email(user, reset_code):
    """Envía el código de restablecimiento de contraseña al correo del usuario."""
    subject = 'Código para restablecer tu contraseña — TecnoStock S.A.'
    context = {'user': user, 'code': reset_code.code, 'valid_minutes': CODE_VALID_MINUTES}
    html_body = render_to_string('security/emails/password_reset_code_email.html', context)
    text_body = (
        f'Hola {user.first_name or user.username},\n\n'
        f'Tu código para restablecer tu contraseña es: {reset_code.code}\n'
        f'Este código vence en {CODE_VALID_MINUTES} minutos.\n\n'
        f'Si tú no solicitaste este cambio, ignora este correo.\n\n'
        f'— TecnoStock S.A.'
    )
    email = EmailMultiAlternatives(subject, text_body, to=[user.email])
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)
