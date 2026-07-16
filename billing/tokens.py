from django.core import signing

_SALT = 'billing.invoice.public_pdf'
_MAX_AGE = 60 * 60 * 24 * 90  # 90 días


def make_invoice_token(invoice):
    """Token firmado (no adivinable) que identifica una factura, para dar
    acceso público de solo lectura a su PDF sin necesitar una cuenta."""
    return signing.dumps(invoice.pk, salt=_SALT)


def verify_invoice_token(token):
    """Devuelve el pk de la factura si el token es válido y no expiró.
    Lanza signing.BadSignature (incluye SignatureExpired) si no es válido."""
    return signing.loads(token, salt=_SALT, max_age=_MAX_AGE)
