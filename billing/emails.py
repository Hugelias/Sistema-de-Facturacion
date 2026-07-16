import calendar

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .pdf import generar_factura_pdf
from .tokens import make_invoice_token


def _one_month_later(date):
    """Misma fecha, un mes después (ajustando fin de mes: 31 ene -> 28/29 feb)."""
    month = date.month + 1
    year = date.year
    if month > 12:
        month = 1
        year += 1
    day = min(date.day, calendar.monthrange(year, month)[1])
    return date.replace(year=year, month=month, day=day)


def _credit_due_date(invoice):
    """Fecha límite de pago: un mes después de la emisión de la factura."""
    return _one_month_later(timezone.localtime(invoice.invoice_date).date())


def send_invoice_email(invoice, request=None):
    """Envía la factura por correo al cliente. Devuelve True si se envió,
    False si el cliente no tiene email registrado."""
    if not invoice.customer.email:
        return False

    token = make_invoice_token(invoice)
    # Enlaza a la página pública de la factura (no directo al PDF): ahí el
    # cliente puede ver el detalle, descargar el PDF/XML y, si aplica, pagar
    # el saldo pendiente con PayPal.
    view_path = reverse('billing:invoice_pdf_public', args=[token])
    view_url = request.build_absolute_uri(view_path) if request else view_path

    context = {'invoice': invoice, 'view_url': view_url}
    if invoice.tipo_pago == 'credito':
        context['due_date'] = _credit_due_date(invoice)

    subject = f'Factura #{invoice.number} — TecnoStock S.A.'
    html_body = render_to_string('billing/emails/invoice_email.html', context)
    text_body = (
        f'Hola {invoice.customer.full_name},\n\n'
        f'Adjuntamos el detalle de tu factura #{invoice.number} por un total de $ {invoice.total}.\n'
        f'Gracias por tu compra en TecnoStock S.A.'
    )

    email = EmailMultiAlternatives(subject, text_body, to=[invoice.customer.email])
    email.attach_alternative(html_body, 'text/html')

    # Se adjunta el PDF real directamente al correo (no solo un link al
    # servidor): así el cliente puede verlo y descargarlo desde cualquier
    # computadora, sin depender de que el servidor esté encendido/accesible
    # en red en ese momento.
    pdf_bytes = generar_factura_pdf(invoice)
    email.attach(f'factura-{invoice.numero_completo}.pdf', pdf_bytes, 'application/pdf')

    email.send(fail_silently=False)
    return True
