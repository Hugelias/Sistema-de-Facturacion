"""Envío de notificaciones de factura por WhatsApp (vía microservicio)."""
from django.urls import reverse

from .tokens import make_invoice_token
from .whatsapp_client import WhatsAppServiceError, enviar_mensaje


def send_invoice_whatsapp(invoice, request=None) -> dict:
    """Envía al cliente un mensaje con el enlace público de la factura.

    Requiere teléfono en el cliente. Devuelve el dict del microservicio.
    Lanza WhatsAppServiceError / ValueError si no se puede enviar.
    """
    phone = (invoice.customer.phone or '').strip()
    if not phone:
        raise ValueError('Este cliente no tiene un teléfono registrado.')

    token = make_invoice_token(invoice)
    view_path = reverse('billing:invoice_pdf_public', args=[token])
    view_url = request.build_absolute_uri(view_path) if request else view_path

    nombre = invoice.customer.full_name or 'cliente'
    total = invoice.total
    numero = invoice.numero_completo

    mensaje = (
        f'*TecnoStock S.A.*\n'
        f'Hola {nombre},\n\n'
        f'Tu factura *#{numero}* por *USD {total}* está lista.\n'
        f'Puedes verla y descargar PDF/XML aquí:\n'
        f'{view_url}\n\n'
        f'Gracias por tu compra.'
    )

    return enviar_mensaje(phone, mensaje)
