"""Microservicio facturación electrónica SRI — SOLO PRUEBAS (celcer).

Flask es la API. La firma XAdES la hace Node (firmar_cli.js + node-forge)
porque el formato del SRI ya está validado en tu proyecto de escritorio.

El .p12 NO se guarda: llega por multipart en cada emisión, se escribe en un
tempfile, se firma, se envía a celcer y se borra el archivo.
"""
from __future__ import annotations

import base64
import json
import os
import random
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

import requests
from flask import Flask, jsonify, request

BASE_DIR = Path(__file__).resolve().parent
PORT = int(os.environ.get('PORT', '5003'))
AMBIENTE_CODIGO = '1'
AMBIENTE_NOMBRE = 'PRUEBAS'
WAIT_AUTORIZACION_SEC = float(os.environ.get('SRI_WAIT_AUTORIZACION_SEC', '3'))

SRI_RECEPCION = (
    'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/'
    'RecepcionComprobantesOffline?wsdl'
)
SRI_AUTORIZACION = (
    'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/'
    'AutorizacionComprobantesOffline?wsdl'
)
URLS_PERMITIDAS = {SRI_RECEPCION, SRI_AUTORIZACION}

PESOS = [2, 3, 4, 5, 6, 7]

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB (p12 + json)


def _assert_url_pruebas(url: str) -> None:
    if url not in URLS_PERMITIDAS:
        raise RuntimeError(
            'URL SRI no permitida. Este servicio solo usa ambiente de pruebas (celcer).'
        )


def _digito_verificador(digits48: str) -> int:
    total = sum(int(ch) * PESOS[i % 6] for i, ch in enumerate(reversed(digits48)))
    residuo = 11 - (total % 11)
    if residuo == 11:
        return 0
    if residuo == 10:
        return 1
    return residuo


def _normalizar_fecha(payload: dict) -> str:
    fecha = str(payload.get('fecha_emision') or '')
    if '/' in fecha:
        parts = fecha.split('/')
        if len(parts) == 3:
            fecha = f'{parts[0]}{parts[1]}{parts[2]}'
    if not re.fullmatch(r'\d{8}', fecha):
        from datetime import datetime

        now = datetime.now()
        fecha = now.strftime('%d%m%Y')
    return fecha


def generar_clave_acceso(payload: dict) -> str:
    fecha = _normalizar_fecha(payload)
    ruc = str(payload.get('ruc_emisor') or '').strip()
    tipo = str(payload.get('tipo_comprobante') or '01')
    serie = f"{payload.get('establecimiento') or '001'}{payload.get('punto_emision') or '001'}"
    secuencial = f"{int(payload.get('secuencial') or 1):09d}"
    codigo = f'{random.randint(0, 99_999_999):08d}'
    digits48 = f'{fecha}{tipo}{ruc}{AMBIENTE_CODIGO}{serie}{secuencial}{codigo}1'
    if len(digits48) != 48 or not digits48.isdigit():
        raise ValueError('No se pudo armar la clave de acceso (revisa RUC 13 dígitos y datos).')
    return digits48 + str(_digito_verificador(digits48))


def _money(value) -> str:
    try:
        return f'{float(value):.2f}'
    except (TypeError, ValueError):
        return '0.00'


def _tipo_id_comprador(identificacion: str, tipo_hint: str | None = None) -> str:
    hint = str(tipo_hint or '').strip().upper()
    if hint in ('04', '05', '06', '07', '08'):
        return hint
    if hint in ('RUC',):
        return '04'
    if hint in ('CEDULA', 'CÉDULA', 'CI'):
        return '05'
    if hint in ('PASAPORTE',):
        return '06'
    if hint in ('CONSUMIDOR_FINAL', 'FINAL'):
        return '07'
    digitos = re.sub(r'\D', '', str(identificacion or ''))
    if digitos == '9999999999999':
        return '07'
    if len(digitos) == 13:
        return '04'
    if len(digitos) == 10:
        return '05'
    return '07'


def generar_xml_factura(payload: dict, clave_acceso: str) -> str:
    """XML factura alineado al XSD SRI (campos mínimos habituales en pruebas)."""
    detalles_in = payload.get('detalles') or []
    lineas = []
    total_sin = 0.0
    total_iva = 0.0

    for idx, d in enumerate(detalles_in, start=1):
        try:
            cant = float(d.get('cantidad') or 0)
            punit = float(d.get('precio_unitario') or 0)
        except (TypeError, ValueError):
            cant, punit = 0.0, 0.0
        try:
            sub = float(d.get('subtotal')) if d.get('subtotal') is not None else cant * punit
        except (TypeError, ValueError):
            sub = cant * punit
        sub = round(sub, 2)
        total_sin = round(total_sin + sub, 2)
        iva_linea = round(sub * 0.15, 2)
        total_iva = round(total_iva + iva_linea, 2)
        codigo = str(d.get('codigo') or d.get('codigo_principal') or f'ITEM{idx:03d}')
        lineas.append(
            f"""
        <detalle>
            <codigoPrincipal>{escape(codigo)}</codigoPrincipal>
            <descripcion>{escape(str(d.get('descripcion') or ''))}</descripcion>
            <cantidad>{_money(cant)}</cantidad>
            <precioUnitario>{_money(punit)}</precioUnitario>
            <descuento>0.00</descuento>
            <precioTotalSinImpuesto>{_money(sub)}</precioTotalSinImpuesto>
            <impuestos>
                <impuesto>
                    <codigo>2</codigo>
                    <codigoPorcentaje>4</codigoPorcentaje>
                    <tarifa>15.00</tarifa>
                    <baseImponible>{_money(sub)}</baseImponible>
                    <valor>{_money(iva_linea)}</valor>
                </impuesto>
            </impuestos>
        </detalle>"""
        )

    # Preferir totales del payload si vienen coherentes; si no, recalcular
    try:
        subtotal_payload = float(payload.get('subtotal')) if payload.get('subtotal') is not None else total_sin
    except (TypeError, ValueError):
        subtotal_payload = total_sin
    try:
        iva_payload = float(payload.get('iva') or payload.get('tax')) if (payload.get('iva') is not None or payload.get('tax') is not None) else total_iva
    except (TypeError, ValueError):
        iva_payload = total_iva
    try:
        total_payload = float(payload.get('total')) if payload.get('total') is not None else round(subtotal_payload + iva_payload, 2)
    except (TypeError, ValueError):
        total_payload = round(subtotal_payload + iva_payload, 2)

    # Si el payload no trae IVA, usar el recalculado
    if abs(iva_payload) < 0.0001 and total_iva > 0:
        iva_payload = total_iva
        total_payload = round(subtotal_payload + iva_payload, 2)

    fecha = _normalizar_fecha(payload)
    fecha_display = payload.get('fecha_emision_display') or f'{fecha[:2]}/{fecha[2:4]}/{fecha[4:]}'
    id_comprador = str(payload.get('identificacion_comprador') or '')
    tipo_id = _tipo_id_comprador(id_comprador, payload.get('tipo_identificacion_comprador'))
    forma_pago = str(payload.get('forma_pago') or '01')
    nombre_comercial = str(payload.get('nombre_comercial') or payload.get('razon_social_emisor') or '')

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.1.0">
    <infoTributaria>
        <ambiente>{AMBIENTE_CODIGO}</ambiente>
        <tipoEmision>1</tipoEmision>
        <razonSocial>{escape(str(payload.get('razon_social_emisor') or ''))}</razonSocial>
        <nombreComercial>{escape(nombre_comercial)}</nombreComercial>
        <ruc>{escape(str(payload.get('ruc_emisor') or ''))}</ruc>
        <claveAcceso>{clave_acceso}</claveAcceso>
        <codDoc>{escape(str(payload.get('tipo_comprobante') or '01'))}</codDoc>
        <estab>{escape(str(payload.get('establecimiento') or '001'))}</estab>
        <ptoEmi>{escape(str(payload.get('punto_emision') or '001'))}</ptoEmi>
        <secuencial>{int(payload.get('secuencial') or 1):09d}</secuencial>
        <dirMatriz>{escape(str(payload.get('dir_matriz') or 'Quito, Ecuador'))}</dirMatriz>
    </infoTributaria>
    <infoFactura>
        <fechaEmision>{escape(str(fecha_display))}</fechaEmision>
        <dirEstablecimiento>{escape(str(payload.get('dir_establecimiento') or payload.get('dir_matriz') or 'Quito, Ecuador'))}</dirEstablecimiento>
        <obligadoContabilidad>{escape(str(payload.get('obligado_contabilidad') or 'NO'))}</obligadoContabilidad>
        <tipoIdentificacionComprador>{tipo_id}</tipoIdentificacionComprador>
        <razonSocialComprador>{escape(str(payload.get('razon_social_comprador') or ''))}</razonSocialComprador>
        <identificacionComprador>{escape(id_comprador)}</identificacionComprador>
        <direccionComprador>{escape(str(payload.get('direccion_comprador') or 'S/N'))}</direccionComprador>
        <totalSinImpuestos>{_money(subtotal_payload)}</totalSinImpuestos>
        <totalDescuento>0.00</totalDescuento>
        <totalConImpuestos>
            <totalImpuesto>
                <codigo>2</codigo>
                <codigoPorcentaje>4</codigoPorcentaje>
                <baseImponible>{_money(subtotal_payload)}</baseImponible>
                <tarifa>15.00</tarifa>
                <valor>{_money(iva_payload)}</valor>
            </totalImpuesto>
        </totalConImpuestos>
        <propina>0.00</propina>
        <importeTotal>{_money(total_payload)}</importeTotal>
        <moneda>DOLAR</moneda>
        <pagos>
            <pago>
                <formaPago>{escape(forma_pago)}</formaPago>
                <total>{_money(total_payload)}</total>
            </pago>
        </pagos>
    </infoFactura>
    <detalles>{''.join(lineas)}
    </detalles>
</factura>"""


def _node_json_cli(script_name: str, payload: dict, timeout: int = 60) -> dict:
    try:
        proc = subprocess.run(
            ['node', str(BASE_DIR / script_name)],
            input=json.dumps(payload).encode('utf-8'),
            capture_output=True,
            cwd=str(BASE_DIR),
            timeout=timeout,
        )
        out = (proc.stdout or b'').decode('utf-8', errors='replace').strip()
        if not out:
            err = (proc.stderr or b'').decode('utf-8', errors='replace')
            return {'success': False, 'mensaje': err or f'Node ({script_name}) sin salida.'}
        return json.loads(out)
    except FileNotFoundError:
        return {
            'success': False,
            'mensaje': 'Node.js no está instalado o no está en el PATH (necesario para firmar).',
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'mensaje': f'Timeout en {script_name}.'}
    except json.JSONDecodeError:
        return {'success': False, 'mensaje': f'Respuesta inválida de {script_name}.'}


def _with_temp_p12(p12_bytes: bytes):
    """Context-like helper: escribe .p12 temporal y lo borra al final."""
    fd, tmp_path = tempfile.mkstemp(suffix='.p12', prefix='sri_cert_')
    os.close(fd)
    with open(tmp_path, 'wb') as f:
        f.write(p12_bytes)
    return tmp_path


def _safe_unlink(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def leer_cert_info(p12_bytes: bytes, password: str) -> dict:
    tmp_path = None
    try:
        tmp_path = _with_temp_p12(p12_bytes)
        return _node_json_cli('cert_cli.js', {'p12_path': tmp_path, 'password': password})
    finally:
        _safe_unlink(tmp_path)


def firmar_con_node(xml: str, p12_bytes: bytes, password: str) -> dict:
    """Firma vía Node. El .p12 vive solo en tempfile y se borra al terminar."""
    tmp_path = None
    try:
        tmp_path = _with_temp_p12(p12_bytes)
        return _node_json_cli(
            'firmar_cli.js',
            {'xml': xml, 'p12_path': tmp_path, 'password': password},
            timeout=60,
        )
    finally:
        _safe_unlink(tmp_path)


def _local_tag(el) -> str:
    return el.tag.split('}')[-1] if '}' in el.tag else el.tag


def _format_mensajes_sri(mensajes: list) -> str:
    parts = []
    for m in mensajes or []:
        if not isinstance(m, dict):
            parts.append(str(m))
            continue
        ident = m.get('identificador') or m.get('id') or ''
        tipo = m.get('tipo') or ''
        msg = m.get('mensaje') or m.get('texto') or ''
        info = m.get('informacionAdicional') or m.get('informacionadicional') or ''
        chunk = ' — '.join(x for x in [ident, tipo, msg, info] if x)
        if chunk:
            parts.append(chunk)
    return ' | '.join(parts) if parts else ''


def _post_soap(url: str, body: str) -> str:
    _assert_url_pruebas(url)
    resp = requests.post(
        url,
        data=body.encode('utf-8'),
        headers={'Content-Type': 'text/xml; charset=UTF-8', 'SOAPAction': ''},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f'SRI pruebas HTTP {resp.status_code}: {resp.text[:300]}')
    return resp.text


def enviar_recepcion(xml_firmado: str) -> dict:
    xml_b64 = base64.b64encode(xml_firmado.encode('utf-8')).decode('ascii')
    envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.recepcion">
  <soapenv:Header/>
  <soapenv:Body>
    <ec:validarComprobante>
      <xml>{xml_b64}</xml>
    </ec:validarComprobante>
  </soapenv:Body>
</soapenv:Envelope>"""
    raw = _post_soap(SRI_RECEPCION, envelope)
    estado = None
    mensajes = []
    try:
        root = ET.fromstring(raw)
        for el in root.iter():
            tag = _local_tag(el)
            if tag == 'estado' and estado is None:
                estado = (el.text or '').strip() or None
            if tag == 'mensaje':
                item = {}
                for child in list(el):
                    item[_local_tag(child)] = (child.text or '').strip()
                if not item and el.text:
                    item = {'texto': el.text.strip()}
                if item:
                    mensajes.append(item)
    except ET.ParseError:
        pass
    recibido = estado in ('RECIBIDO', 'RECIBIDA')
    detalle = _format_mensajes_sri(mensajes)
    return {
        'ambiente': AMBIENTE_NOMBRE,
        'url': SRI_RECEPCION,
        'estado': estado,
        'recibido': recibido,
        'mensajes': mensajes,
        'detalle': detalle,
        'respuesta_xml': raw[:4000],
    }


def consultar_autorizacion(clave_acceso: str) -> dict:
    envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.autorizacion">
  <soapenv:Header/>
  <soapenv:Body>
    <ec:autorizacionComprobante>
      <claveAccesoComprobante>{clave_acceso}</claveAccesoComprobante>
    </ec:autorizacionComprobante>
  </soapenv:Body>
</soapenv:Envelope>"""
    raw = _post_soap(SRI_AUTORIZACION, envelope)
    estado = 'NO AUTORIZADO'
    numero = None
    fecha = None
    ambiente_autorizacion = None
    comprobante = None  # XML factura firmada (contenido de CDATA o texto)
    mensajes = []
    try:
        root = ET.fromstring(raw)
        auth_el = None
        for el in root.iter():
            if _local_tag(el) == 'autorizacion':
                auth_el = el
                break
        if auth_el is not None:
            for child in list(auth_el):
                tag = _local_tag(child)
                text = (child.text or '').strip()
                if tag == 'estado' and text:
                    estado = text
                elif tag == 'numeroAutorizacion':
                    numero = text or None
                elif tag == 'fechaAutorizacion':
                    fecha = text or None
                elif tag == 'ambiente':
                    ambiente_autorizacion = text or None
                elif tag == 'comprobante':
                    # CDATA suele venir en .text; a veces hay wrappers
                    comprobante = (child.text or '').strip() or None
                    if not comprobante and list(child):
                        # Algunos parsers dejan el XML hijo parseado
                        comprobante = ET.tostring(child[0], encoding='unicode')
                elif tag == 'mensajes':
                    for msg_el in child.iter():
                        if _local_tag(msg_el) != 'mensaje':
                            continue
                        item = {}
                        for c in list(msg_el):
                            item[_local_tag(c)] = (c.text or '').strip()
                        if item:
                            mensajes.append(item)
        else:
            for el in root.iter():
                if _local_tag(el) == 'estado' and (el.text or '').strip():
                    estado = el.text.strip()
                    break
    except ET.ParseError:
        pass

    # Fallback: extraer CDATA de comprobante con regex si ET no lo trae
    if not comprobante:
        m = re.search(
            r'<comprobante[^>]*>\s*<!\[CDATA\[(.*?)\]\]>\s*</comprobante>',
            raw,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if m:
            comprobante = m.group(1).strip()

    estado_up = str(estado).upper().replace('_', ' ').strip()
    detalle = _format_mensajes_sri(mensajes)

    # XML de descarga estilo portal SRI (autorizacion + CDATA)
    xml_autorizado_sri = None
    if estado_up == 'AUTORIZADO' and comprobante:
        cuerpo = comprobante.replace(']]>', ']]]]><![CDATA[>')
        amb = ambiente_autorizacion or AMBIENTE_NOMBRE
        xml_autorizado_sri = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<autorizacion>\n'
            f'  <estado>{estado}</estado>\n'
            f'  <numeroAutorizacion>{numero or clave_acceso}</numeroAutorizacion>\n'
            f'  <fechaAutorizacion>{fecha or ""}</fechaAutorizacion>\n'
            f'  <ambiente>{amb}</ambiente>\n'
            f'  <comprobante><![CDATA[{cuerpo}]]></comprobante>\n'
            '</autorizacion>\n'
        )

    return {
        'ambiente': AMBIENTE_NOMBRE,
        'url': SRI_AUTORIZACION,
        'clave_acceso': clave_acceso,
        'estado': estado,
        'autorizado': estado_up == 'AUTORIZADO',
        'numero_autorizacion': numero,
        'fecha_autorizacion': fecha,
        'ambiente_autorizacion': ambiente_autorizacion,
        'comprobante': comprobante,
        'xml_autorizado': xml_autorizado_sri,
        'mensajes': mensajes,
        'detalle': detalle,
        'respuesta_xml': raw[:8000],
    }


def _parse_payload_from_request() -> tuple[dict, bytes | None, str]:
    """JSON o multipart: payload + (opcional) archivo p12 + password."""
    p12_bytes = None
    password = ''

    if request.content_type and 'multipart/form-data' in request.content_type:
        raw_payload = request.form.get('payload') or '{}'
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as e:
            raise ValueError(f'payload JSON inválido: {e}') from e
        password = request.form.get('password') or ''
        cert = request.files.get('certificado') or request.files.get('p12')
        if cert and cert.filename:
            p12_bytes = cert.read()
            if not p12_bytes:
                raise ValueError('El archivo .p12 está vacío.')
    else:
        payload = request.get_json(silent=True) or {}
        password = str(payload.pop('password', '') or '')
        # Compat: base64 en JSON (no recomendado; preferir multipart)
        b64 = payload.pop('certificado_base64', None) or payload.pop('p12_base64', None)
        if b64:
            p12_bytes = base64.b64decode(b64)

    if not isinstance(payload, dict):
        raise ValueError('payload debe ser un objeto JSON.')
    return payload, p12_bytes, password


@app.get('/salud')
def salud():
    return jsonify({
        'status': 'ok',
        'servicio': 'sri-facturacion-service',
        'runtime': 'flask+node-firma',
        'ambiente': AMBIENTE_NOMBRE,
        'ambiente_codigo': AMBIENTE_CODIGO,
        'produccion_habilitada': False,
        'certificado': 'se pide por request (no se guarda en el servidor)',
        'urls_pruebas': {
            'recepcion': SRI_RECEPCION,
            'autorizacion': SRI_AUTORIZACION,
        },
    })


@app.get('/ambiente')
def ambiente():
    return jsonify({
        'ambiente': AMBIENTE_NOMBRE,
        'codigo': AMBIENTE_CODIGO,
        'produccion_habilitada': False,
        'nota': 'Solo pruebas (celcer). El .p12 se envía en cada emisión y no se almacena.',
    })


@app.post('/comprobantes/clave-acceso')
def api_clave():
    try:
        clave = generar_clave_acceso(request.get_json(silent=True) or {})
        return jsonify({
            'clave_acceso': clave,
            'ambiente': AMBIENTE_NOMBRE,
            'ambiente_codigo': AMBIENTE_CODIGO,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.post('/comprobantes/generar-xml')
def api_generar_xml():
    try:
        data = request.get_json(silent=True) or {}
        clave = data.get('clave_acceso') or generar_clave_acceso(data)
        xml = generar_xml_factura(data, clave)
        return jsonify({'clave_acceso': clave, 'ambiente': AMBIENTE_NOMBRE, 'xml': xml})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.post('/comprobantes/firmar')
def api_firmar():
    try:
        payload, p12_bytes, password = _parse_payload_from_request()
        xml = payload.get('xml') or (request.form.get('xml') if request.form else None)
        if not xml and request.is_json:
            xml = (request.get_json(silent=True) or {}).get('xml')
        if not xml:
            return jsonify({'error': 'Falta xml.'}), 400
        if not p12_bytes:
            return jsonify({'error': 'Falta certificado .p12 (multipart campo certificado).'}), 400
        firma = firmar_con_node(xml, p12_bytes, password)
        if not firma.get('success'):
            return jsonify({'error': firma.get('mensaje', 'Error al firmar')}), 400
        return jsonify({
            'ambiente': AMBIENTE_NOMBRE,
            'xml_firmado': firma.get('xmlFirmado'),
            'mensaje': firma.get('mensaje'),
            'certificado_persistido': False,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.post('/comprobantes/recibir')
def api_recibir():
    try:
        body = request.get_json(silent=True) or {}
        xml = body.get('xml') or body.get('xml_firmado')
        if not xml and body.get('xml_base64'):
            xml = base64.b64decode(body['xml_base64']).decode('utf-8')
        if not xml:
            return jsonify({'error': 'Falta xml / xml_firmado.'}), 400
        return jsonify(enviar_recepcion(xml))
    except Exception as e:
        return jsonify({'error': str(e)}), 502


@app.post('/comprobantes/autorizar')
def api_autorizar():
    try:
        body = request.get_json(silent=True) or {}
        clave = str(body.get('clave_acceso') or '').strip()
        if not re.fullmatch(r'\d{49}', clave):
            return jsonify({'error': 'clave_acceso debe tener 49 dígitos.'}), 400
        return jsonify(consultar_autorizacion(clave))
    except Exception as e:
        return jsonify({'error': str(e)}), 502


@app.post('/comprobantes/emitir')
def api_emitir():
    """Emisión completa en PRUEBAS con .p12 enviado en este request (no se guarda)."""
    try:
        data, p12_bytes, password = _parse_payload_from_request()
        if not p12_bytes:
            return jsonify({
                'error': 'Debes enviar el certificado .p12 en este request (multipart: certificado + password + payload).',
            }), 400
        if not password:
            return jsonify({'error': 'Falta la contraseña del certificado.'}), 400

        data = dict(data or {})
        cert_info = leer_cert_info(p12_bytes, password)
        msg_cert = str(cert_info.get('mensaje') or '')
        if 'Contraseña incorrecta' in msg_cert or 'P12 inválido' in msg_cert:
            return jsonify({'error': f'Certificado: {msg_cert}'}), 400

        ruc_manual = re.sub(r'\D', '', str(data.get('ruc_emisor') or ''))
        razon_manual = str(data.get('razon_social_emisor') or '').strip()

        # Preferir RUC/razón del formulario; si faltan, intentar leerlos del .p12
        if len(ruc_manual) == 13 and razon_manual:
            data['ruc_emisor'] = ruc_manual
            data['razon_social_emisor'] = razon_manual
            if not data.get('nombre_comercial'):
                data['nombre_comercial'] = razon_manual
        elif cert_info.get('success') and cert_info.get('ruc'):
            data['ruc_emisor'] = cert_info['ruc']
            if cert_info.get('razon_social'):
                data['razon_social_emisor'] = cert_info['razon_social']
                if not data.get('nombre_comercial'):
                    data['nombre_comercial'] = cert_info['razon_social']
        else:
            return jsonify({
                'error': (
                    'Ingresa el RUC (13 dígitos) y la razón social del emisor. '
                    f"({msg_cert or 'el certificado no trajo un RUC legible'})"
                ),
                'subject': cert_info.get('subject'),
            }), 400

        if not str(data.get('razon_social_emisor') or '').strip():
            return jsonify({'error': 'Falta la razón social del emisor.'}), 400
        if not re.fullmatch(r'\d{13}', str(data.get('ruc_emisor') or '')):
            return jsonify({'error': 'El RUC del emisor debe tener 13 dígitos.'}), 400

        clave = generar_clave_acceso(data)
        xml = generar_xml_factura(data, clave)
        firma = firmar_con_node(xml, p12_bytes, password)
        if not firma.get('success'):
            return jsonify({
                'error': f"Firma: {firma.get('mensaje')}",
                'clave_acceso': clave,
                'ruc_certificado': data.get('ruc_emisor'),
            }), 400

        recepcion = enviar_recepcion(firma['xmlFirmado'])
        if not recepcion.get('recibido'):
            detalle = recepcion.get('detalle') or 'sin detalle del SRI'
            return jsonify({
                'error': (
                    f"El SRI (pruebas) no recibió el comprobante "
                    f"(estado: {recepcion.get('estado') or 'N/A'}). {detalle}"
                ),
                'clave_acceso': clave,
                'ruc_certificado': data.get('ruc_emisor'),
                'razon_social_certificado': data.get('razon_social_emisor'),
                'ambiente': AMBIENTE_NOMBRE,
                'recepcion': recepcion,
            }), 502

        time.sleep(WAIT_AUTORIZACION_SEC)
        autorizacion = consultar_autorizacion(clave)
        # Reintentos si aún está en procesamiento
        for _ in range(3):
            estado_tmp = str(autorizacion.get('estado') or '')
            if autorizacion.get('autorizado'):
                break
            if not re.search(r'PROCESO|PPR|EN PROCESAMIENTO', estado_tmp, re.I):
                break
            time.sleep(WAIT_AUTORIZACION_SEC)
            autorizacion = consultar_autorizacion(clave)

        if not autorizacion.get('autorizado'):
            detalle = autorizacion.get('detalle') or ''
            err = f"SRI pruebas no autorizó (estado: {autorizacion.get('estado')})."
            if detalle:
                err = f'{err} Motivo SRI: {detalle}'
            else:
                err = (
                    f'{err} Suele ocurrir si el RUC no está habilitado en ambiente de pruebas, '
                    'el establecimiento/punto de emisión no coincide, o hay error de esquema/firma.'
                )
            return jsonify({
                'error': err,
                'clave_acceso': clave,
                'ruc_certificado': data.get('ruc_emisor'),
                'ambiente': AMBIENTE_NOMBRE,
                'recepcion': recepcion,
                'autorizacion': autorizacion,
            }), 502

        xml_firmado = firma.get('xmlFirmado') or ''
        # Prioridad: XML oficial del SRI (autorizacion + CDATA con factura firmada).
        # Fallback escritorio: insertar bloque <autorizacion> antes de </factura>.
        xml_autorizado = autorizacion.get('xml_autorizado')
        if not xml_autorizado and xml_firmado:
            num = autorizacion.get('numero_autorizacion') or clave
            fecha_a = autorizacion.get('fecha_autorizacion') or ''
            amb = autorizacion.get('ambiente_autorizacion') or AMBIENTE_CODIGO
            bloque = (
                '    <autorizacion>\n'
                '      <estado>AUTORIZADO</estado>\n'
                f'      <numeroAutorizacion>{num}</numeroAutorizacion>\n'
                f'      <fechaAutorizacion>{fecha_a}</fechaAutorizacion>\n'
                f'      <ambiente>{amb}</ambiente>\n'
                '    </autorizacion>\n'
            )
            if re.search(r'</factura>', xml_firmado, flags=re.I):
                xml_autorizado = re.sub(r'</factura>', bloque + '</factura>', xml_firmado, count=1, flags=re.I)
            else:
                xml_autorizado = xml_firmado

        return jsonify({
            'ambiente': AMBIENTE_NOMBRE,
            'ambiente_codigo': AMBIENTE_CODIGO,
            'produccion_habilitada': False,
            'modo': 'celcer_pruebas',
            'clave_acceso': clave,
            'ruc_certificado': data.get('ruc_emisor'),
            'razon_social_certificado': data.get('razon_social_emisor'),
            'numero_autorizacion': autorizacion.get('numero_autorizacion') or clave,
            'fecha_autorizacion': autorizacion.get('fecha_autorizacion'),
            'estado_sri': 'autorizada',
            'xml_firmado': xml_firmado,
            'xml_autorizado': xml_autorizado,
            'certificado_persistido': False,
            'recepcion': recepcion,
            'autorizacion': {
                k: v for k, v in autorizacion.items() if k not in ('comprobante', 'respuesta_xml')
            },
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 502


@app.post('/comprobantes/emitir-local')
def api_emitir_local():
    """Fallback académico sin firma ni SRI real (sigue ambiente=1)."""
    try:
        data = request.get_json(silent=True) or {}
        if request.content_type and 'multipart/form-data' in request.content_type:
            data, _, _ = _parse_payload_from_request()
        clave = generar_clave_acceso(data)
        xml = generar_xml_factura(data, clave)
        return jsonify({
            'ambiente': AMBIENTE_NOMBRE,
            'ambiente_codigo': AMBIENTE_CODIGO,
            'modo': 'local_pruebas',
            'produccion_habilitada': False,
            'clave_acceso': clave,
            'numero_autorizacion': clave,
            'estado_sri': 'autorizada',
            'xml': xml,
            'nota': 'Autorización local. Use /comprobantes/emitir con .p12 por request para celcer.',
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    print(f'sri-facturacion-service (Flask + Node firma) PRUEBAS/celcer → http://127.0.0.1:{PORT}')
    print('Producción: DESHABILITADA | .p12: solo por request, no se guarda')
    app.run(host='0.0.0.0', port=PORT, debug=False)
