"""Cliente HTTP hacia el microservicio de PayPal (carpeta `paypal_service/`).

Django NO habla con la API de PayPal directamente — le hace peticiones HTTP
a ese microservicio aparte, que es quien realmente conversa con PayPal. Si
el microservicio no está corriendo, esto lanza `PayPalServiceError` con un
mensaje claro (no un error genérico de conexión)."""
import json
import urllib.error
import urllib.request

from django.conf import settings


class PayPalServiceError(Exception):
    pass


def _post(path, data):
    url = f'{settings.PAYPAL_SERVICE_URL}{path}'
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        method='POST',
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
            raise PayPalServiceError(body.get('error', str(e)))
        except (ValueError, json.JSONDecodeError):
            raise PayPalServiceError(str(e))
    except urllib.error.URLError:
        raise PayPalServiceError(
            'No se pudo conectar con el microservicio de PayPal. '
            '¿Está corriendo? (paypal_service/app.py)'
        )


def crear_orden(factura, monto, return_url=None, cancel_url=None):
    """Crea la orden en PayPal (vía microservicio).

    Sin return_url/cancel_url → pensado para el SDK Buttons (popup).
    Con ambas URLs → flujo por redirección (misma pestaña).
    Devuelve (order_id, approve_url). approve_url puede ir vacío en el SDK.
    """
    payload = {
        'monto': str(monto),
        'descripcion': f'Abono factura #{factura.number or factura.id} — TecnoStock S.A.',
        'referencia': str(factura.pk),
    }
    if return_url and cancel_url:
        payload['return_url'] = return_url
        payload['cancel_url'] = cancel_url
    resultado = _post('/ordenes', payload)
    order_id = resultado.get('order_id')
    approve_url = resultado.get('approve_url') or ''
    if not order_id:
        raise PayPalServiceError('El microservicio no devolvió un id de orden válido.')
    if (return_url and cancel_url) and not approve_url:
        raise PayPalServiceError('El microservicio no devolvió un enlace de pago válido.')
    return order_id, approve_url


def capturar_orden(order_id):
    """Le pide al microservicio que capture (cobre) la orden ya aprobada por
    el comprador. Devuelve (monto_capturado: str, order_id: str)."""
    resultado = _post(f'/ordenes/{order_id}/capturar', {})
    if resultado.get('status') != 'COMPLETED':
        raise PayPalServiceError('El microservicio no confirmó la captura del pago.')
    return resultado['monto_capturado'], order_id
