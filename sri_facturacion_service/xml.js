const { AMBIENTE_CODIGO } = require('./config');

const PESOS = [2, 3, 4, 5, 6, 7];

function digitoVerificador(digits48) {
  let total = 0;
  const rev = digits48.split('').reverse();
  for (let i = 0; i < rev.length; i++) {
    total += Number(rev[i]) * PESOS[i % 6];
  }
  const residuo = 11 - (total % 11);
  if (residuo === 11) return 0;
  if (residuo === 10) return 1;
  return residuo;
}

function escapeXml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function normalizarFecha(payload) {
  let fecha = payload.fecha_emision || '';
  if (fecha.includes('/')) {
    const p = fecha.split('/');
    if (p.length === 3) fecha = `${p[0]}${p[1]}${p[2]}`;
  }
  if (!/^\d{8}$/.test(fecha)) {
    const now = new Date();
    const dd = String(now.getDate()).padStart(2, '0');
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const yyyy = String(now.getFullYear());
    fecha = `${dd}${mm}${yyyy}`;
  }
  return fecha;
}

function generarClaveAcceso(payload) {
  const fecha = normalizarFecha(payload);
  const ruc = String(payload.ruc_emisor || '').trim();
  const tipo = String(payload.tipo_comprobante || '01');
  const serie = `${payload.establecimiento || '001'}${payload.punto_emision || '001'}`;
  const secuencial = String(Number(payload.secuencial || 1)).padStart(9, '0');
  const codigo = String(Math.floor(Math.random() * 1e8)).padStart(8, '0');
  const digits48 = `${fecha}${tipo}${ruc}${AMBIENTE_CODIGO}${serie}${secuencial}${codigo}1`;
  if (digits48.length !== 48 || !/^\d{48}$/.test(digits48)) {
    throw new Error('No se pudo armar la clave de acceso (revisa RUC 13 dígitos y datos).');
  }
  return digits48 + String(digitoVerificador(digits48));
}

function generarXmlFactura(payload, claveAcceso) {
  const detalles = payload.detalles || [];
  const lineas = detalles
    .map(
      (d) => `
        <detalle>
            <descripcion>${escapeXml(d.descripcion || '')}</descripcion>
            <cantidad>${escapeXml(d.cantidad ?? 0)}</cantidad>
            <precioUnitario>${escapeXml(d.precio_unitario ?? 0)}</precioUnitario>
            <precioTotalSinImpuesto>${escapeXml(d.subtotal ?? 0)}</precioTotalSinImpuesto>
        </detalle>`
    )
    .join('');

  const fechaDisplay =
    payload.fecha_emision_display ||
    (() => {
      const f = normalizarFecha(payload);
      return `${f.slice(0, 2)}/${f.slice(2, 4)}/${f.slice(4)}`;
    })();

  return `<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.1.0">
    <infoTributaria>
        <ambiente>${AMBIENTE_CODIGO}</ambiente>
        <tipoEmision>1</tipoEmision>
        <razonSocial>${escapeXml(payload.razon_social_emisor || '')}</razonSocial>
        <ruc>${escapeXml(payload.ruc_emisor || '')}</ruc>
        <claveAcceso>${claveAcceso}</claveAcceso>
        <codDoc>${escapeXml(payload.tipo_comprobante || '01')}</codDoc>
        <estab>${escapeXml(payload.establecimiento || '001')}</estab>
        <ptoEmi>${escapeXml(payload.punto_emision || '001')}</ptoEmi>
        <secuencial>${String(Number(payload.secuencial || 1)).padStart(9, '0')}</secuencial>
        <dirMatriz>${escapeXml(payload.dir_matriz || 'Quito, Ecuador')}</dirMatriz>
    </infoTributaria>
    <infoFactura>
        <fechaEmision>${escapeXml(fechaDisplay)}</fechaEmision>
        <razonSocialComprador>${escapeXml(payload.razon_social_comprador || '')}</razonSocialComprador>
        <identificacionComprador>${escapeXml(payload.identificacion_comprador || '')}</identificacionComprador>
        <totalSinImpuestos>${escapeXml(payload.subtotal ?? 0)}</totalSinImpuestos>
        <importeTotal>${escapeXml(payload.total ?? 0)}</importeTotal>
    </infoFactura>
    <detalles>${lineas}
    </detalles>
</factura>`;
}

module.exports = { generarClaveAcceso, generarXmlFactura };
