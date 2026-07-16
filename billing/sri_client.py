"""Cliente HTTP hacia el microservicio del SRI (carpeta `sri_service/`).

Django NO habla con la API del SRI directamente — le hace peticiones HTTP
a ese microservicio aparte. Si no está corriendo, lanza SriServiceError."""
import json
import urllib.error
import urllib.request

from django.conf import settings


class SriServiceError(Exception):
    pass


def _get(path):
    url = f'{settings.SRI_SERVICE_URL}{path}'
    req = urllib.request.Request(url, method='GET', headers={'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
            raise SriServiceError(body.get('error', str(e)))
        except (ValueError, json.JSONDecodeError):
            raise SriServiceError(str(e))
    except urllib.error.URLError:
        raise SriServiceError(
            'No se pudo conectar con el microservicio del SRI. '
            '¿Está corriendo? (sri_service/app.py)'
        )


def consultar_contribuyente(ruc):
    """Devuelve datos consolidados del RUC vía microservicio."""
    ruc = (ruc or '').strip()
    if not ruc.isdigit() or len(ruc) != 13:
        raise SriServiceError('El RUC debe tener exactamente 13 dígitos numéricos.')
    return _get(f'/contribuyentes/{ruc}')
