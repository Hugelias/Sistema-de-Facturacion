"""RIDE — Representación Impresa del Documento Electrónico (factura SRI Ecuador).

Formato alineado al PDF del proyecto de facturación (panel derecho FACTURA +
clave/código de barras + emisor + comprador + detalle + totales).
"""
from __future__ import annotations

import io
import re
from decimal import Decimal
from xml.etree import ElementTree as ET

from django.utils import timezone
from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .electronic_invoice import EMISOR_RAZON_SOCIAL, EMISOR_RUC, ruc_desde_clave

BLACK = colors.HexColor('#1a1a1a')
GRAY = colors.HexColor('#555555')
LIGHT = colors.HexColor('#cccccc')
BOX_FILL = colors.HexColor('#e8e8e8')
AUTH_BG = colors.HexColor('#e8f4e8')
AUTH_BORDER = colors.HexColor('#b0d0b0')
AUTH_TXT = colors.HexColor('#1a4d1a')


def _tag(el):
    return el.tag.split('}')[-1] if '}' in el.tag else el.tag


def _text_from_xml(xml_text: str) -> dict | None:
    """Extrae datos del XML autorizado/firmado si está guardado."""
    if not xml_text or not xml_text.strip():
        return None
    try:
        raw = xml_text.strip()
        # Preferir factura dentro de CDATA
        m = re.search(r'<!\[CDATA\[(.*?)\]\]>', raw, flags=re.DOTALL | re.I)
        factura_xml = (m.group(1).strip() if m else raw)
        # Si el envoltorio es <autorizacion>, quitar signature noise — parse factura
        if '<factura' in factura_xml:
            start = factura_xml.find('<factura')
            end = factura_xml.rfind('</factura>')
            if start >= 0 and end > start:
                factura_xml = factura_xml[start:end + len('</factura>')]
        root = ET.fromstring(factura_xml)
        if _tag(root) != 'factura':
            for el in root.iter():
                if _tag(el) == 'factura':
                    root = el
                    break
        info_t = {}
        info_f = {}
        detalles = []
        for child in list(root):
            tag = _tag(child)
            if tag == 'infoTributaria':
                info_t = {_tag(c): (c.text or '').strip() for c in list(child)}
            elif tag == 'infoFactura':
                info_f = {_tag(c): (c.text or '').strip() for c in list(child) if _tag(c) != 'totalConImpuestos' and _tag(c) != 'pagos'}
                for c in list(child):
                    if _tag(c) == 'totalConImpuestos':
                        for ti in c.iter():
                            if _tag(ti) == 'valor' and 'iva' not in info_f:
                                # último valor IVA típico
                                info_f['iva'] = (ti.text or '').strip()
            elif tag == 'detalles':
                for det in child:
                    if _tag(det) != 'detalle':
                        continue
                    d = {_tag(c): (c.text or '').strip() for c in list(det) if _tag(c) != 'impuestos'}
                    detalles.append(d)
        # autorización del envoltorio original
        auth = {}
        try:
            wrap = ET.fromstring(raw) if raw.lstrip().startswith('<') else None
            if wrap is not None and _tag(wrap) == 'autorizacion':
                auth = {_tag(c): (c.text or '').strip() for c in list(wrap) if _tag(c) != 'comprobante'}
        except ET.ParseError:
            pass
        return {'infoTributaria': info_t, 'infoFactura': info_f, 'detalles': detalles, 'autorizacion': auth}
    except Exception:
        return None


def _datos_ride(invoice) -> dict:
    """Arma el diccionario RIDE desde XML guardado o desde el modelo Invoice."""
    parsed = _text_from_xml(getattr(invoice, 'xml_autorizado', '') or '')
    if parsed and parsed.get('infoTributaria', {}).get('ruc'):
        it = parsed['infoTributaria']
        iff = parsed['infoFactura']
        return {
            'ruc': it.get('ruc') or '',
            'razon_social': it.get('razonSocial') or '',
            'nombre_comercial': it.get('nombreComercial') or it.get('razonSocial') or '',
            'dir_matriz': it.get('dirMatriz') or 'Quito, Ecuador',
            'dir_establecimiento': iff.get('dirEstablecimiento') or it.get('dirMatriz') or 'Quito, Ecuador',
            'estab': it.get('estab') or invoice.establecimiento,
            'pto_emi': it.get('ptoEmi') or invoice.punto_emision,
            'secuencial': it.get('secuencial') or f'{(invoice.number or 0):09d}',
            'ambiente': it.get('ambiente') or invoice.ambiente or '1',
            'tipo_emision': it.get('tipoEmision') or '1',
            'clave_acceso': it.get('claveAcceso') or invoice.clave_acceso or '',
            'fecha_emision': iff.get('fechaEmision') or timezone.localtime(invoice.invoice_date).strftime('%d/%m/%Y'),
            'obligado': iff.get('obligadoContabilidad') or 'NO',
            'comprador': iff.get('razonSocialComprador') or invoice.customer.full_name,
            'identificacion': iff.get('identificacionComprador') or invoice.customer.dni,
            'direccion_comprador': iff.get('direccionComprador') or (invoice.customer.address or 'S/N'),
            'subtotal': iff.get('totalSinImpuestos') or str(invoice.subtotal),
            'iva': iff.get('iva') or str(invoice.tax),
            'total': iff.get('importeTotal') or str(invoice.total),
            'detalles': parsed.get('detalles') or [],
            'numero_autorizacion': (
                parsed.get('autorizacion', {}).get('numeroAutorizacion')
                or invoice.numero_autorizacion
                or invoice.clave_acceso
                or ''
            ),
            'fecha_autorizacion': (
                parsed.get('autorizacion', {}).get('fechaAutorizacion')
                or (
                    timezone.localtime(invoice.fecha_autorizacion).strftime('%d/%m/%Y %H:%M:%S')
                    if invoice.fecha_autorizacion else ''
                )
            ),
        }

    ruc = (invoice.ruc_emisor or '').strip() or ruc_desde_clave(invoice.clave_acceso) or EMISOR_RUC
    razon = (invoice.razon_social_emisor or '').strip() or EMISOR_RAZON_SOCIAL
    detalles = []
    for d in invoice.details.select_related('product').all():
        detalles.append({
            'codigoPrincipal': str(d.product_id),
            'descripcion': d.product.name,
            'cantidad': f'{Decimal(d.quantity):.2f}',
            'precioUnitario': f'{Decimal(d.unit_price):.2f}',
            'descuento': '0.00',
            'precioTotalSinImpuesto': f'{Decimal(d.subtotal):.2f}',
        })
    return {
        'ruc': ruc,
        'razon_social': razon,
        'nombre_comercial': razon,
        'dir_matriz': 'Quito, Ecuador',
        'dir_establecimiento': 'Quito, Ecuador',
        'estab': invoice.establecimiento,
        'pto_emi': invoice.punto_emision,
        'secuencial': f'{(invoice.number or 0):09d}',
        'ambiente': invoice.ambiente or '1',
        'tipo_emision': '1',
        'clave_acceso': invoice.clave_acceso or '',
        'fecha_emision': timezone.localtime(invoice.invoice_date).strftime('%d/%m/%Y'),
        'obligado': 'NO',
        'comprador': invoice.customer.full_name,
        'identificacion': invoice.customer.dni,
        'direccion_comprador': invoice.customer.address or 'S/N',
        'subtotal': f'{invoice.subtotal:.2f}',
        'iva': f'{invoice.tax:.2f}',
        'total': f'{invoice.total:.2f}',
        'detalles': detalles,
        'numero_autorizacion': invoice.numero_autorizacion or invoice.clave_acceso or '',
        'fecha_autorizacion': (
            timezone.localtime(invoice.fecha_autorizacion).strftime('%d/%m/%Y %H:%M:%S')
            if invoice.fecha_autorizacion else ''
        ),
    }


def _rounded_rect(c, x, y, w, h, r=6):
    c.roundRect(x, y, w, h, r, stroke=1, fill=0)


def generar_factura_pdf(invoice):
    """Devuelve los bytes del PDF RIDE de la factura."""
    data = _datos_ride(invoice)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_l = 40
    margin_r = 40
    usable = width - margin_l - margin_r

    tiene_auth = bool(data.get('clave_acceso') or data.get('numero_autorizacion'))
    # ── Bloque derecho FACTURA ────────────────────────────────────────────
    box_x = 280
    box_w = 275
    box_top = height - 30
    box_h = 268 if tiene_auth else 210
    box_y = box_top - box_h
    _rounded_rect(c, box_x, box_y, box_w, box_h, 8)

    c.setFillColor(BLACK)
    c.setFont('Helvetica', 9)
    c.drawString(box_x + 10, box_top - 18, f"R.U.C.: {data['ruc']}")

    c.setFillColor(BOX_FILL)
    c.setStrokeColor(LIGHT)
    c.roundRect(box_x + 10, box_top - 48, box_w - 20, 22, 4, stroke=1, fill=1)
    c.setFillColor(BLACK)
    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(box_x + box_w / 2, box_top - 42, 'FACTURA')

    c.setFont('Helvetica', 9)
    c.setFillColor(GRAY)
    y = box_top - 68
    c.drawString(box_x + 10, y, f"No. {data['estab']}-{data['pto_emi']}-{data['secuencial']}")
    y -= 14
    amb = 'PRUEBAS' if str(data['ambiente']) == '1' else 'PRODUCCIÓN'
    c.drawString(box_x + 10, y, f'AMBIENTE: {amb}')
    y -= 14
    c.drawString(box_x + 10, y, 'EMISIÓN: Normal')
    y -= 14
    c.drawString(box_x + 10, y, f"FECHA DE EMISIÓN: {data['fecha_emision']}")

    # Clave + barcode
    y -= 10
    c.setStrokeColor(LIGHT)
    c.line(box_x + 10, y, box_x + box_w - 10, y)
    y -= 14
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(GRAY)
    c.drawCentredString(box_x + box_w / 2, y, 'CLAVE DE ACCESO')
    y -= 8
    clave = data.get('clave_acceso') or ''
    if clave:
        try:
            barcode = code128.Code128(clave, barHeight=22, barWidth=0.85, humanReadable=False)
            bw = barcode.width
            bx = box_x + (box_w - bw) / 2
            barcode.drawOn(c, bx, y - 26)
            y -= 30
        except Exception:
            y -= 4
        c.setFont('Helvetica', 6.5)
        c.setFillColor(GRAY)
        c.drawCentredString(box_x + box_w / 2, y - 8, clave)
        y -= 16
    else:
        c.setFont('Helvetica', 8)
        c.drawCentredString(box_x + box_w / 2, y - 12, 'Pendiente de autorización')
        y -= 20

    if tiene_auth and data.get('numero_autorizacion'):
        c.setStrokeColor(LIGHT)
        c.line(box_x + 10, y, box_x + box_w - 10, y)
        y -= 8
        c.setFillColor(AUTH_BG)
        c.setStrokeColor(AUTH_BORDER)
        c.roundRect(box_x + 12, y - 36, box_w - 24, 38, 4, stroke=1, fill=1)
        c.setFillColor(AUTH_TXT)
        c.setFont('Helvetica-Bold', 8)
        c.drawString(box_x + 18, y - 12, 'AUTORIZACIÓN SRI')
        c.setFont('Helvetica', 6.5)
        c.setFillColor(BLACK)
        num = data['numero_autorizacion']
        if len(num) > 42:
            c.drawString(box_x + 18, y - 22, f'Nº: {num[:42]}')
            c.drawString(box_x + 18, y - 30, num[42:])
        else:
            c.drawString(box_x + 18, y - 24, f'Nº: {num}')
        if data.get('fecha_autorizacion'):
            c.drawString(box_x + 18, y - 34, f"Fecha y hora: {data['fecha_autorizacion']}")

    # ── Emisor (izquierda) ────────────────────────────────────────────────
    offset_y = 58 if tiene_auth else 0
    em_top = height - 140 - offset_y
    em_h = 100
    em_y = em_top - em_h
    _rounded_rect(c, margin_l, em_y, 230, em_h, 8)
    c.setFillColor(BLACK)
    c.setFont('Helvetica-Bold', 9)
    razon = (data['razon_social'] or '').upper()
    c.drawString(margin_l + 10, em_top - 16, razon[:42])
    if len(razon) > 42:
        c.drawString(margin_l + 10, em_top - 28, razon[42:84])
        ty = em_top - 42
    else:
        ty = em_top - 32
    c.setFont('Helvetica', 8)
    c.setFillColor(GRAY)
    c.drawString(margin_l + 10, ty, f"Dirección Matriz: {data['dir_matriz'][:36]}")
    ty -= 14
    c.drawString(margin_l + 10, ty, f"Dirección Sucursal: {data['dir_establecimiento'][:34]}")
    ty -= 14
    c.drawString(margin_l + 10, ty, f"OBLIGADO A LLEVAR CONTABILIDAD: {data['obligado']}")

    # ── Comprador ─────────────────────────────────────────────────────────
    cli_top = em_y - 16
    cli_h = 70
    cli_y = cli_top - cli_h
    _rounded_rect(c, margin_l, cli_y, usable, cli_h, 8)
    c.setFont('Helvetica', 8)
    c.setFillColor(GRAY)
    c.drawString(margin_l + 10, cli_top - 14, 'Razón Social / Nombres y Apellidos:')
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(BLACK)
    c.drawString(margin_l + 190, cli_top - 14, (data['comprador'] or '')[:55])
    c.setFont('Helvetica', 8)
    c.setFillColor(GRAY)
    c.drawString(margin_l + 10, cli_top - 30, 'Identificación:')
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(BLACK)
    c.drawString(margin_l + 190, cli_top - 30, data['identificacion'] or '')
    c.setFont('Helvetica', 8)
    c.setFillColor(GRAY)
    c.drawString(margin_l + 10, cli_top - 46, 'Dirección:')
    c.setFillColor(BLACK)
    c.drawString(margin_l + 190, cli_top - 46, (data['direccion_comprador'] or '')[:60])

    # ── Tabla detalle ─────────────────────────────────────────────────────
    headers = [
        ('Código', 45),
        ('Descripción', 250),
        ('Cant.', 40),
        ('P. Unitario', 55),
        ('Descuento', 50),
        ('Total', 55),
    ]
    table_top = cli_y - 16
    row_h = 18
    c.setStrokeColor(BLACK)
    c.rect(margin_l, table_top - row_h, usable, row_h, stroke=1, fill=0)
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(BLACK)
    x = margin_l + 4
    for text, w in headers:
        c.drawCentredString(x + w / 2, table_top - 12, text)
        x += w

    y = table_top - row_h
    c.setFont('Helvetica', 7.5)
    detalles = data.get('detalles') or []
    if not detalles:
        detalles = [{
            'codigoPrincipal': '',
            'descripcion': '(sin detalles)',
            'cantidad': '0.00',
            'precioUnitario': '0.00',
            'descuento': '0.00',
            'precioTotalSinImpuesto': '0.00',
        }]

    for det in detalles:
        y -= row_h
        if y < 120:
            c.showPage()
            y = height - 60
        c.setStrokeColor(LIGHT)
        c.rect(margin_l, y, usable, row_h, stroke=1, fill=0)
        c.setFillColor(BLACK)
        vals = [
            det.get('codigoPrincipal') or det.get('codigo') or '',
            (det.get('descripcion') or '')[:58],
            det.get('cantidad') or '',
            det.get('precioUnitario') or '',
            det.get('descuento') or '0.00',
            det.get('precioTotalSinImpuesto') or det.get('total') or '',
        ]
        x = margin_l + 4
        for i, (val, (_, w)) in enumerate(zip(vals, headers)):
            if i in (2, 3, 4, 5):
                c.drawRightString(x + w - 4, y + 5, str(val))
            else:
                c.drawString(x + 2, y + 5, str(val))
            x += w

    # ── Totales ───────────────────────────────────────────────────────────
    tot_x = margin_l + usable - 180
    y -= 10
    c.setFont('Helvetica', 9)
    c.setFillColor(BLACK)
    rows_tot = [
        ('SUBTOTAL SIN IMPUESTOS', f"$ {data['subtotal']}"),
        ('IVA 15%', f"$ {data['iva']}"),
        ('VALOR TOTAL', f"$ {data['total']}"),
    ]
    for i, (lbl, val) in enumerate(rows_tot):
        y -= 16
        font = 'Helvetica-Bold' if i == len(rows_tot) - 1 else 'Helvetica'
        c.setFont(font, 9 if i < 2 else 11)
        c.drawString(tot_x, y, lbl)
        c.drawRightString(margin_l + usable - 4, y, val)

    # Pie
    y -= 28
    c.setStrokeColor(LIGHT)
    c.line(margin_l, y, margin_l + usable, y)
    y -= 14
    c.setFont('Helvetica', 7)
    c.setFillColor(GRAY)
    c.drawString(margin_l, y, 'Información adicional: Documento generado como RIDE (Representación Impresa del Documento Electrónico).')
    y -= 12
    if str(data['ambiente']) == '1':
        c.drawString(margin_l, y, 'AMBIENTE: PRUEBAS — Este comprobante no tiene validez tributaria en producción.')
    y -= 12
    c.drawRightString(
        margin_l + usable,
        y,
        f"Factura {data['estab']}-{data['pto_emi']}-{data['secuencial']}",
    )

    c.save()
    return buffer.getvalue()
