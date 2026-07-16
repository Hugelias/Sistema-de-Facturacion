"""Microservicio de pagos con PayPal — TecnoStock S.A.

Servicio independiente (Flask) que expone una API REST propia para crear y
capturar órdenes de pago en PayPal. El sistema principal (Django) NO llama a
PayPal directamente: le hace peticiones HTTP a este microservicio, que es
quien conversa con la API real de PayPal (Orders API v2).

Cómo correrlo:
    pip install -r requirements.txt
    python app.py
Por defecto queda escuchando en http://localhost:5001
"""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, jsonify, request

app = Flask(__name__)

# ── Configuración de PayPal (Sandbox) ───────────────────────────────────────
# 1. Crea una cuenta en https://developer.paypal.com/ (puedes usar tu cuenta
#    normal de PayPal, o crear una nueva).
# 2. Ve a "Apps & Credentials" (queda en modo "Sandbox" por defecto — no
#    cambies a "Live" hasta que quieras cobrar de verdad).
# 3. Crea una app nueva (o usa la "Default Application").
# 4. Copia el "Client ID" y el "Secret".
# 5. Reemplaza los valores de abajo, o mejor, define las variables de entorno
#    PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET antes de correr el servicio:
#      $env:PAYPAL_CLIENT_ID = "tu_client_id"
#      $env:PAYPAL_CLIENT_SECRET = "tu_secret"
#      python app.py
# 6. Para probar pagos reales de prueba, usa una cuenta de comprador de
#    prueba (se crean automáticamente en "Sandbox > Accounts" del panel de
#    developer.paypal.com).
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', 'AfeLi2Q6OfDSxMCvEnwwObOnuPfK4XDnWC8mLSDsSPXLuskh_5HF9TORMEefmqM5tk0KOho3xHhN8nOd')
PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET', 'EKNiXF96KM_la0vrF0IGRhSMhdYq5LutVYs2yf7GnUDA-dBLBxVXpAbrXmQjHl147SmkQq6-ZPZ2Zdf8')
PAYPAL_MODE = os.environ.get('PAYPAL_MODE', 'sandbox')  # 'sandbox' o 'live'

_API_BASE = {
    'sandbox': 'https://api-m.sandbox.paypal.com',
    'live': 'https://api-m.paypal.com',
}


class PayPalError(Exception):
    pass


def _api_base():
    return _API_BASE.get(PAYPAL_MODE, _API_BASE['sandbox'])


def _paypal_request(method, path, data=None, token=None, auth_basic=False):
    url = f'{_api_base()}{path}'
    headers = {'Content-Type': 'application/json'}
    body = None
    if auth_basic:
        credentials = f'{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}'
        headers['Authorization'] = 'Basic ' + base64.b64encode(credentials.encode()).decode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        body = urllib.parse.urlencode(data or {}).encode()
    else:
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if data is not None:
            body = json.dumps(data).encode()

    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read() or b'{}')
    except urllib.error.HTTPError as e:
        raise PayPalError(e.read().decode('utf-8', errors='replace'))
    except urllib.error.URLError as e:
        raise PayPalError(str(e.reason))


def _access_token():
    result = _paypal_request('POST', '/v1/oauth2/token', data={'grant_type': 'client_credentials'}, auth_basic=True)
    token = result.get('access_token')
    if not token:
        raise PayPalError('PayPal no devolvió un token de acceso válido.')
    return token


# ── Endpoints del microservicio ─────────────────────────────────────────────

@app.route('/salud', methods=['GET'])
def salud():
    """Endpoint simple para confirmar que el microservicio está vivo."""
    return jsonify({'status': 'ok', 'servicio': 'paypal-service', 'modo': PAYPAL_MODE})


@app.route('/ordenes', methods=['POST'])
def crear_orden():
    data = request.get_json(silent=True) or {}
    monto = data.get('monto')
    descripcion = data.get('descripcion', 'Pago — TecnoStock S.A.')
    referencia = data.get('referencia', '')
    return_url = data.get('return_url') or ''
    cancel_url = data.get('cancel_url') or ''

    if not monto:
        return jsonify({'error': 'Falta el monto a cobrar.'}), 400

    try:
        token = _access_token()
        # Flujo por redirección (1 sola ventana): el comprador va a PayPal
        # y vuelve a return_url. Evita el popup about:blank del SDK Buttons.
        app_ctx = {
            'shipping_preference': 'NO_SHIPPING',
            'user_action': 'PAY_NOW',
        }
        if return_url and cancel_url:
            app_ctx['return_url'] = return_url
            app_ctx['cancel_url'] = cancel_url
        payload = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'reference_id': str(referencia),
                'description': descripcion,
                'amount': {'currency_code': 'USD', 'value': f'{float(monto):.2f}'},
            }],
            'application_context': app_ctx,
        }
        orden = _paypal_request('POST', '/v2/checkout/orders', data=payload, token=token)
    except PayPalError as e:
        return jsonify({'error': f'No se pudo crear la orden de PayPal: {e}'}), 502
    except (TypeError, ValueError):
        return jsonify({'error': 'Monto inválido.'}), 400

    order_id = orden.get('id')
    if not order_id:
        return jsonify({'error': 'PayPal no devolvió un id de orden válido.'}), 502

    approve_url = ''
    for link in orden.get('links') or []:
        if link.get('rel') == 'approve':
            approve_url = link.get('href') or ''
            break
    if not approve_url:
        return jsonify({'error': 'PayPal no devolvió el enlace de aprobación.'}), 502

    return jsonify({'order_id': order_id, 'approve_url': approve_url})


@app.route('/ordenes/<order_id>/capturar', methods=['POST'])
def capturar_orden(order_id):
    try:
        token = _access_token()
        resultado = _paypal_request('POST', f'/v2/checkout/orders/{order_id}/capture', data={}, token=token)
    except PayPalError as e:
        return jsonify({'error': f'No se pudo capturar el pago de PayPal: {e}'}), 502

    if resultado.get('status') != 'COMPLETED':
        return jsonify({'error': f'La orden no se completó (estado: {resultado.get("status")}).'}), 502

    try:
        captura = resultado['purchase_units'][0]['payments']['captures'][0]
        monto_capturado = captura['amount']['value']
    except (KeyError, IndexError):
        return jsonify({'error': 'No se pudo leer el monto capturado de la respuesta de PayPal.'}), 502

    return jsonify({'status': 'COMPLETED', 'order_id': order_id, 'monto_capturado': monto_capturado})


if __name__ == '__main__':
    # debug=False a propósito: el recargador automático de Flask en Windows
    # a veces se cierra solo sin avisar. Si vas a editar app.py, para el
    # proceso (Ctrl+C en su terminal) y vuelve a correr `python app.py`.
    app.run(host='0.0.0.0', port=5001, debug=False)
