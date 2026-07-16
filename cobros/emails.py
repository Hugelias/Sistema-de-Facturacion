from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from billing.tokens import make_invoice_token


def send_cobro_email(cobro, request=None):
    """Envía la confirmación de un abono al cliente. Devuelve True si se
    envió, False si el cliente no tiene email registrado."""
    factura = cobro.factura
    if not factura.customer.email:
        return False

    view_path = reverse('billing:invoice_pdf_public', args=[make_invoice_token(factura)])
    view_url = request.build_absolute_uri(view_path) if request else view_path

    subject = f'Abono registrado — Factura #{factura.number or factura.id} — TecnoStock S.A.'
    html_body = render_to_string('cobros/emails/cobro_email.html', {
        'cobro': cobro, 'factura': factura, 'view_url': view_url,
    })
    text_body = (
        f'Hola {factura.customer.full_name},\n\n'
        f'Registramos tu abono de $ {cobro.valor} sobre la factura #{factura.number or factura.id}.\n'
        f'Saldo pendiente: $ {factura.saldo}.\n\n'
        f'Gracias por tu pago. — TecnoStock S.A.'
    )

    email = EmailMultiAlternatives(subject, text_body, to=[factura.customer.email])
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)
    return True
