"""Cliente HTTP hacia sri_facturacion_service (Flask :5003).

Solo PRUEBAS (celcer). El .p12 se envía en cada emisión y no se guarda.
"""
from __future__ import annotations

import json
import mimetypes
import uuid
import urllib.error
import urllib.request
from typing import BinaryIO

from django.conf import settings


class SriFacturacionServiceError(Exception):
    pass


def _base_url() -> str:
    return getattr(settings, 'SRI_FACTURACION_SERVICE_URL', 'http://localhost:5003').rstrip('/')


def _post_json(path: str, data: dict, timeout: int = 90) -> dict:
    url = f'{_base_url()}{path}'
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        method='POST',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    )
    return _read_response(req, timeout)


def _post_multipart(
    path: str,
    payload: dict,
    cert_file: BinaryIO,
    cert_filename: str,
    password: str,
    timeout: int = 120,
) -> dict:
    """Envía payload JSON + .p12 + password. El microservicio no persiste el cert."""
    boundary = f'----TecnoStockSri{uuid.uuid4().hex}'
    body = bytearray()

    def add_field(name: str, value: str) -> None:
        body.extend(f'--{boundary}\r\n'.encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode('utf-8'))
        body.extend(b'\r\n')

    add_field('payload', json.dumps(payload, ensure_ascii=False))
    add_field('password', password)

    cert_bytes = cert_file.read()
    if hasattr(cert_file, 'seek'):
        try:
            cert_file.seek(0)
        except Exception:
            pass
    ctype = mimetypes.guess_type(cert_filename)[0] or 'application/x-pkcs12'
    body.extend(f'--{boundary}\r\n'.encode())
    body.extend(
        (
            f'Content-Disposition: form-data; name="certificado"; '
            f'filename="{cert_filename}"\r\n'
            f'Content-Type: {ctype}\r\n\r\n'
        ).encode()
    )
    body.extend(cert_bytes)
    body.extend(b'\r\n')
    body.extend(f'--{boundary}--\r\n'.encode())

    url = f'{_base_url()}{path}'
    req = urllib.request.Request(
        url,
        data=bytes(body),
        method='POST',
        headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Accept': 'application/json',
        },
    )
    return _read_response(req, timeout)


def _read_response(req: urllib.request.Request, timeout: int) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            body = json.loads(raw)
            err = body.get('error') or str(e)
            recepcion = body.get('recepcion') or {}
            autorizacion = body.get('autorizacion') or {}
            detalle = recepcion.get('detalle') or autorizacion.get('detalle')
            if detalle and detalle not in err:
                err = f'{err} | {detalle}'
            raise SriFacturacionServiceError(err)
        except SriFacturacionServiceError:
            raise
        except (ValueError, json.JSONDecodeError):
            raise SriFacturacionServiceError(raw.decode('utf-8', errors='replace') or str(e))
    except urllib.error.URLError:
        raise SriFacturacionServiceError(
            'No se pudo conectar con sri_facturacion_service (:5003). '
            'Corre: python sri_facturacion_service\\app.py'
        )


def emitir_pruebas(payload: dict, cert_file: BinaryIO, cert_filename: str, password: str) -> dict:
    """Emisión completa: firma (Node) + recepción + autorización celcer. Sin guardar .p12."""
    return _post_multipart(
        '/comprobantes/emitir',
        payload,
        cert_file,
        cert_filename or 'certificado.p12',
        password,
        timeout=120,
    )


def emitir_local_pruebas(payload: dict) -> dict:
    """Fallback académico (sin .p12 / sin celcer)."""
    return _post_json('/comprobantes/emitir-local', payload)


def consultar_autorizacion_pruebas(clave_acceso: str) -> dict:
    return _post_json('/comprobantes/autorizar', {'clave_acceso': clave_acceso})


def sincronizar_xml_desde_sri(clave_acceso: str) -> dict:
    """Consulta celcer y devuelve xml_autorizado oficial si aún está disponible."""
    return consultar_autorizacion_pruebas(clave_acceso)
