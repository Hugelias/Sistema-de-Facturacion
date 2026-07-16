"""Facturación electrónica SRI — ambiente de PRUEBAS únicamente (TecnoStock).

Flujo (microservicio Flask :5003 + firma Node):
  modal pide .p12 + contraseña → generar XML → firmar XAdES → celcer recepción/autorización

El certificado NO se guarda en Django ni en el microservicio: solo viaja en ese request.
"""
from decimal import Decimal
from xml.sax.saxutils import escape
import re

from django.utils import timezone

from .sri_facturacion_client import SriFacturacionServiceError, emitir_pruebas

# Datos de marca en PDF/UI (mientras no haya emisor guardado en la factura).
EMISOR_RUC = '1790000000001'
EMISOR_RAZON_SOCIAL = 'TecnoStock S.A.'
TIPO_COMPROBANTE_FACTURA = '01'
TIPO_EMISION_NORMAL = '1'
AMBIENTE_PRUEBAS = '1'


def ruc_desde_clave(clave_acceso):
    """Extrae el RUC (13 dígitos) de la clave de acceso SRI."""
    clave = re.sub(r'\D', '', str(clave_acceso or ''))
    if len(clave) >= 23:
        return clave[10:23]
    return ''


def _tipo_id_comprador(dni):
    digitos = ''.join(ch for ch in str(dni or '') if ch.isdigit())
    if digitos == '9999999999999':
        return '07'
    if len(digitos) == 13:
        return '04'
    if len(digitos) == 10:
        return '05'
    return '07'


def _money(value):
    try:
        return f'{float(value):.2f}'
    except (TypeError, ValueError):
        return '0.00'


def _payload_desde_invoice(invoice):
    fecha = timezone.localtime(invoice.invoice_date)
    customer = invoice.customer
    dni = (customer.dni or '').strip()
    return {
        'ruc_emisor': '0000000000001',
        'razon_social_emisor': EMISOR_RAZON_SOCIAL,
        'tipo_comprobante': TIPO_COMPROBANTE_FACTURA,
        'establecimiento': invoice.establecimiento,
        'punto_emision': invoice.punto_emision,
        'secuencial': invoice.number or 0,
        'fecha_emision': fecha.strftime('%d%m%Y'),
        'fecha_emision_display': fecha.strftime('%d/%m/%Y'),
        'razon_social_comprador': customer.full_name,
        'identificacion_comprador': dni,
        'tipo_identificacion_comprador': _tipo_id_comprador(dni),
        'direccion_comprador': customer.address or 'S/N',
        'subtotal': str(invoice.subtotal),
        'iva': str(invoice.tax),
        'tax': str(invoice.tax),
        'total': str(invoice.total),
        'forma_pago': '20' if invoice.tipo_pago == 'credito' else '01',
        'obligado_contabilidad': 'NO',
        'dir_matriz': 'Quito, Ecuador',
        'dir_establecimiento': 'Quito, Ecuador',
        'detalles': [
            {
                'codigo': str(d.product_id),
                'descripcion': d.product.name,
                'cantidad': str(d.quantity),
                'precio_unitario': str(d.unit_price),
                'subtotal': str(d.subtotal),
            }
            for d in invoice.details.select_related('product').all()
        ],
    }


def autorizar_factura_electronica(
    invoice,
    cert_file,
    password,
    cert_filename='certificado.p12',
    ruc_emisor=None,
    razon_social_emisor=None,
):
    """Autoriza en PRUEBAS con el .p12 que el usuario acaba de subir (no se persiste)."""
    if not cert_file:
        raise SriFacturacionServiceError('Debes seleccionar el archivo .p12.')
    if not password:
        raise SriFacturacionServiceError('Debes ingresar la contraseña del certificado.')

    ruc = re.sub(r'\D', '', str(ruc_emisor or ''))
    razon = (razon_social_emisor or '').strip()
    if len(ruc) != 13:
        raise SriFacturacionServiceError('El RUC del emisor debe tener 13 dígitos.')
    if not razon:
        raise SriFacturacionServiceError('Ingresa la razón social del emisor.')

    invoice.ambiente = AMBIENTE_PRUEBAS
    payload = _payload_desde_invoice(invoice)
    payload['ruc_emisor'] = ruc
    payload['razon_social_emisor'] = razon
    payload['nombre_comercial'] = razon
    resultado = emitir_pruebas(payload, cert_file, cert_filename, password)

    invoice.clave_acceso = resultado['clave_acceso']
    invoice.numero_autorizacion = resultado.get('numero_autorizacion') or resultado['clave_acceso']
    invoice.estado_sri = resultado.get('estado_sri') or 'autorizada'
    invoice.fecha_autorizacion = timezone.now()
    invoice.ruc_emisor = resultado.get('ruc_certificado') or ruc
    invoice.razon_social_emisor = resultado.get('razon_social_certificado') or razon

    xml_guardar = (resultado.get('xml_autorizado') or '').strip()
    if not xml_guardar:
        xml_firmado = (resultado.get('xml_firmado') or '').strip()
        if xml_firmado:
            xml_guardar = armar_xml_estilo_escritorio(invoice, xml_firmado)
    if xml_guardar:
        invoice.xml_autorizado = xml_guardar

    update_fields = [
        'ambiente', 'clave_acceso', 'numero_autorizacion', 'fecha_autorizacion', 'estado_sri',
        'ruc_emisor', 'razon_social_emisor',
    ]
    if xml_guardar:
        update_fields.append('xml_autorizado')
    invoice.save(update_fields=update_fields)
    return invoice


def armar_xml_estilo_escritorio(invoice, xml_factura_firmado):
    """Como verificarFactura.js: inserta <autorizacion> antes de </factura>."""
    num = invoice.numero_autorizacion or invoice.clave_acceso or ''
    fecha_aut = timezone.localtime(invoice.fecha_autorizacion or timezone.now())
    amb = invoice.ambiente or AMBIENTE_PRUEBAS
    bloque = (
        '    <autorizacion>\n'
        '      <estado>AUTORIZADO</estado>\n'
        f'      <numeroAutorizacion>{escape(num)}</numeroAutorizacion>\n'
        f'      <fechaAutorizacion>{fecha_aut.strftime("%d/%m/%Y %H:%M:%S")}</fechaAutorizacion>\n'
        f'      <ambiente>{escape(amb)}</ambiente>\n'
        '    </autorizacion>\n'
    )
    if re.search(r'</factura>', xml_factura_firmado, flags=re.I):
        return re.sub(r'</factura>', bloque + '</factura>', xml_factura_firmado, count=1, flags=re.I)
    return xml_factura_firmado


def armar_xml_autorizacion_sri(invoice, xml_factura_firmado):
    """Formato portal SRI: <autorizacion> + factura firmada en CDATA."""
    fecha_aut = timezone.localtime(invoice.fecha_autorizacion or timezone.now())
    ambiente = 'PRUEBAS' if str(invoice.ambiente or '1') == '1' else 'PRODUCCION'
    cuerpo = xml_factura_firmado.replace(']]>', ']]]]><![CDATA[>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<autorizacion>\n'
        '  <estado>AUTORIZADO</estado>\n'
        f'  <numeroAutorizacion>{escape(invoice.numero_autorizacion or invoice.clave_acceso or "")}</numeroAutorizacion>\n'
        f'  <fechaAutorizacion>{fecha_aut.strftime("%d/%m/%Y %H:%M:%S")}</fechaAutorizacion>\n'
        f'  <ambiente>{ambiente}</ambiente>\n'
        f'  <comprobante><![CDATA[{cuerpo}]]></comprobante>\n'
        '</autorizacion>\n'
    )


def generar_factura_xml_sri(invoice):
    """XML de factura (sin firma) con datos reales del emisor/comprador — fallback."""
    ruc = (invoice.ruc_emisor or '').strip() or ruc_desde_clave(invoice.clave_acceso) or EMISOR_RUC
    razon = (invoice.razon_social_emisor or '').strip() or EMISOR_RAZON_SOCIAL
    customer = invoice.customer
    tipo_id = _tipo_id_comprador(customer.dni)
    forma_pago = '20' if invoice.tipo_pago == 'credito' else '01'
    detalles = []
    for idx, d in enumerate(invoice.details.select_related('product').all(), start=1):
        sub = d.subtotal
        iva = (sub * Decimal('0.15')).quantize(Decimal('0.01'))
        detalles.append(f"""
        <detalle>
            <codigoPrincipal>{escape(str(d.product_id or idx))}</codigoPrincipal>
            <descripcion>{escape(d.product.name)}</descripcion>
            <cantidad>{_money(d.quantity)}</cantidad>
            <precioUnitario>{_money(d.unit_price)}</precioUnitario>
            <descuento>0.00</descuento>
            <precioTotalSinImpuesto>{_money(sub)}</precioTotalSinImpuesto>
            <impuestos>
                <impuesto>
                    <codigo>2</codigo>
                    <codigoPorcentaje>4</codigoPorcentaje>
                    <tarifa>15.00</tarifa>
                    <baseImponible>{_money(sub)}</baseImponible>
                    <valor>{_money(iva)}</valor>
                </impuesto>
            </impuestos>
        </detalle>""")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.1.0">
    <infoTributaria>
        <ambiente>{invoice.ambiente or AMBIENTE_PRUEBAS}</ambiente>
        <tipoEmision>{TIPO_EMISION_NORMAL}</tipoEmision>
        <razonSocial>{escape(razon)}</razonSocial>
        <nombreComercial>{escape(razon)}</nombreComercial>
        <ruc>{escape(ruc)}</ruc>
        <claveAcceso>{invoice.clave_acceso}</claveAcceso>
        <codDoc>{TIPO_COMPROBANTE_FACTURA}</codDoc>
        <estab>{invoice.establecimiento}</estab>
        <ptoEmi>{invoice.punto_emision}</ptoEmi>
        <secuencial>{(invoice.number or 0):09d}</secuencial>
        <dirMatriz>Quito, Ecuador</dirMatriz>
    </infoTributaria>
    <infoFactura>
        <fechaEmision>{timezone.localtime(invoice.invoice_date):%d/%m/%Y}</fechaEmision>
        <dirEstablecimiento>Quito, Ecuador</dirEstablecimiento>
        <obligadoContabilidad>NO</obligadoContabilidad>
        <tipoIdentificacionComprador>{tipo_id}</tipoIdentificacionComprador>
        <razonSocialComprador>{escape(customer.full_name)}</razonSocialComprador>
        <identificacionComprador>{escape(customer.dni or '')}</identificacionComprador>
        <direccionComprador>{escape(customer.address or 'S/N')}</direccionComprador>
        <totalSinImpuestos>{_money(invoice.subtotal)}</totalSinImpuestos>
        <totalDescuento>0.00</totalDescuento>
        <totalConImpuestos>
            <totalImpuesto>
                <codigo>2</codigo>
                <codigoPorcentaje>4</codigoPorcentaje>
                <baseImponible>{_money(invoice.subtotal)}</baseImponible>
                <tarifa>15.00</tarifa>
                <valor>{_money(invoice.tax)}</valor>
            </totalImpuesto>
        </totalConImpuestos>
        <propina>0.00</propina>
        <importeTotal>{_money(invoice.total)}</importeTotal>
        <moneda>DOLAR</moneda>
        <pagos>
            <pago>
                <formaPago>{forma_pago}</formaPago>
                <total>{_money(invoice.total)}</total>
            </pago>
        </pagos>
    </infoFactura>
    <detalles>{''.join(detalles)}
    </detalles>
</factura>
"""


def generar_xml_autorizacion(invoice, request=None):
    """XML de autorización para descarga (.xml real, sin XSLT que se vea como PDF)."""
    stored = (getattr(invoice, 'xml_autorizado', None) or '').strip()
    if stored.startswith('<?xml') or stored.startswith('<autorizacion'):
        return stored

    # Fallback: reconstruir envoltorio con factura (sin firma XAdES si no se guardó)
    factura = generar_factura_xml_sri(invoice)
    return armar_xml_autorizacion_sri(invoice, factura)
