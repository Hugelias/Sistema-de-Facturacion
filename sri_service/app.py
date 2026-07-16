"""Microservicio de consulta al catastro del SRI — TecnoStock S.A.

Servicio independiente (Flask) que expone una API REST propia para validar
RUC y obtener datos de contribuyentes. El sistema principal (Django) NO
llama al SRI directamente: le hace peticiones HTTP a este microservicio.

Cómo correrlo:
    pip install -r requirements.txt
    python app.py
Por defecto queda escuchando en http://localhost:5002
"""
import json
import os
import urllib.error
import urllib.request

from flask import Flask, jsonify

app = Flask(__name__)

SRI_BASE = os.environ.get(
    'SRI_API_BASE',
    'https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest',
)


class SriError(Exception):
    pass


def _sri_get(path):
    url = f'{SRI_BASE}{path}'
    req = urllib.request.Request(
        url,
        method='GET',
        headers={
            'User-Agent': 'TecnoStock-SRI-Service/1.0',
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        raise SriError(f'El SRI respondió con error HTTP {e.code}.')
    except urllib.error.URLError as e:
        raise SriError(f'No se pudo conectar con el SRI: {e.reason}')


def _validar_ruc(ruc):
    ruc = (ruc or '').strip()
    if not ruc.isdigit() or len(ruc) != 13:
        raise ValueError('El RUC debe tener exactamente 13 dígitos numéricos.')
    return ruc


def _existe_ruc(ruc):
    texto = _sri_get(f'/ConsolidadoContribuyente/existePorNumeroRuc?numeroRuc={ruc}')
    return texto.strip().lower() == 'true'


def _obtener_contribuyente(ruc):
    raw = _sri_get(f'/ConsolidadoContribuyente/obtenerPorNumerosRuc?&ruc={ruc}')
    datos = json.loads(raw)
    if not datos:
        raise SriError('El SRI no devolvió datos del contribuyente.')
    return datos[0]


def _obtener_establecimientos(ruc):
    raw = _sri_get(f'/Establecimiento/consultarPorNumeroRuc?numeroRuc={ruc}')
    return json.loads(raw) if raw.strip() else []


def _direccion_principal(establecimientos):
    if not establecimientos:
        return ''
    for est in establecimientos:
        if (est.get('matriz') or '').upper() == 'SI' and (est.get('estado') or '').upper() == 'ABIERTO':
            return est.get('direccionCompleta') or ''
    for est in establecimientos:
        if (est.get('estado') or '').upper() == 'ABIERTO':
            return est.get('direccionCompleta') or ''
    return establecimientos[0].get('direccionCompleta') or ''


def _nombre_comercial(establecimientos):
    if not establecimientos:
        return ''
    for est in establecimientos:
        if (est.get('matriz') or '').upper() == 'SI':
            return est.get('nombreFantasiaComercial') or ''
    return establecimientos[0].get('nombreFantasiaComercial') or ''


def _mapear_establecimientos(establecimientos):
    return [
        {
            'numero': e.get('numeroEstablecimiento', ''),
            'tipo': e.get('tipoEstablecimiento', ''),
            'estado': e.get('estado', ''),
            'direccion': e.get('direccionCompleta', ''),
            'nombre_comercial': e.get('nombreFantasiaComercial', ''),
            'matriz': e.get('matriz', ''),
        }
        for e in establecimientos
    ]


def _respuesta_contribuyente(ruc):
    if not _existe_ruc(ruc):
        return None
    datos = _obtener_contribuyente(ruc)
    establecimientos = _obtener_establecimientos(ruc)
    return {
        'ruc': ruc,
        'existe': True,
        'razon_social': datos.get('razonSocial', ''),
        'estado': datos.get('estadoContribuyenteRuc', ''),
        'tipo_contribuyente': datos.get('tipoContribuyente', ''),
        'actividad_economica': datos.get('actividadEconomicaPrincipal', ''),
        'obligado_contabilidad': datos.get('obligadoLlevarContabilidad', ''),
        'direccion': _direccion_principal(establecimientos),
        'nombre_comercial': _nombre_comercial(establecimientos),
        'establecimientos': _mapear_establecimientos(establecimientos),
    }


@app.route('/salud', methods=['GET'])
def salud():
    return jsonify({'status': 'ok', 'servicio': 'sri-service'})


@app.route('/contribuyentes/<ruc>/existe', methods=['GET'])
def contribuyente_existe(ruc):
    try:
        ruc = _validar_ruc(ruc)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    try:
        existe = _existe_ruc(ruc)
    except SriError as e:
        return jsonify({'error': str(e)}), 502
    return jsonify({'ruc': ruc, 'existe': existe})


@app.route('/contribuyentes/<ruc>/establecimientos', methods=['GET'])
def contribuyente_establecimientos(ruc):
    try:
        ruc = _validar_ruc(ruc)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    try:
        if not _existe_ruc(ruc):
            return jsonify({'error': 'El RUC no está registrado en el SRI.'}), 404
        establecimientos = _obtener_establecimientos(ruc)
    except SriError as e:
        return jsonify({'error': str(e)}), 502
    return jsonify({
        'ruc': ruc,
        'establecimientos': _mapear_establecimientos(establecimientos),
    })


@app.route('/contribuyentes/<ruc>', methods=['GET'])
def contribuyente(ruc):
    """Consulta consolidada: existe, datos y establecimientos."""
    try:
        ruc = _validar_ruc(ruc)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    try:
        resultado = _respuesta_contribuyente(ruc)
    except SriError as e:
        return jsonify({'error': str(e)}), 502
    if not resultado:
        return jsonify({'ruc': ruc, 'existe': False, 'error': 'El RUC no está registrado en el SRI.'}), 404
    return jsonify(resultado)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=False)
