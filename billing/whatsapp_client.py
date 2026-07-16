"""Cliente HTTP hacia whatsapp_service (Node + Baileys :5004).

Django no habla con Meta. El microservicio usa tu WhatsApp local (QR).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from django.conf import settings


class WhatsAppServiceError(Exception):
    pass


def _base_url() -> str:
    return getattr(settings, 'WHATSAPP_SERVICE_URL', 'http://localhost:5004').rstrip('/')


def enviar_mensaje(telefono: str, mensaje: str, codigo_pais: str | None = None) -> dict:
    """POST /mensajes/enviar → dict con ok/proveedor/detalle."""
    url = f'{_base_url()}/mensajes/enviar'
    payload: dict = {'telefono': telefono, 'mensaje': mensaje}
    if codigo_pais:
        payload['codigo_pais'] = codigo_pais

    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        method='POST',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
            data = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace') if e.fp else ''
        try:
            err = json.loads(body) if body else {}
        except json.JSONDecodeError:
            err = {}
        raise WhatsAppServiceError(
            err.get('error') or f'whatsapp_service HTTP {e.code}: {body[:300]}'
        ) from e
    except urllib.error.URLError as e:
        raise WhatsAppServiceError(
            f'No se pudo conectar con whatsapp_service en {_base_url()}. '
            f'¿Está corriendo? ({e.reason})'
        ) from e
    except json.JSONDecodeError as e:
        raise WhatsAppServiceError('Respuesta inválida del microservicio WhatsApp.') from e

    if not data.get('ok'):
        raise WhatsAppServiceError(data.get('error') or 'El microservicio no envió el mensaje.')
    return data


def health() -> dict:
    url = f'{_base_url()}/health'
    req = urllib.request.Request(url, method='GET', headers={'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8', errors='replace'))
    except Exception as e:
        raise WhatsAppServiceError(f'Servicio WhatsApp no disponible: {e}') from e
