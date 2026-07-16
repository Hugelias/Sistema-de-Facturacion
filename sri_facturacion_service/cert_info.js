/**
 * Extrae RUC / nombre del certificado .p12 (firma electrónica Ecuador).
 * Si no encuentra RUC, success=false pero igual devuelve subject/cn para diagnóstico.
 */
const forge = require('node-forge');
const fs = require('fs');

function attrValue(attrs, names) {
  const set = new Set(names.map((n) => String(n).toLowerCase()));
  for (const a of attrs || []) {
    const keys = [a.name, a.shortName, a.type].filter(Boolean).map((x) => String(x).toLowerCase());
    if (keys.some((k) => set.has(k))) return String(a.value || '');
  }
  return '';
}

function allAttrText(attrs) {
  return (attrs || [])
    .map((a) => `${a.shortName || a.name || a.type || '?'}=${a.value || ''}`)
    .join(' | ');
}

/** Busca cualquier secuencia de exactamente 13 dígitos (RUC Ecuador). */
function findRucInText(text) {
  if (!text) return null;
  const matches = String(text).match(/\d{13}/g);
  if (!matches || !matches.length) return null;
  // Preferir los que terminan en 001 (persona natural / matriz común)
  const preferred = matches.find((m) => m.endsWith('001'));
  return preferred || matches[0];
}

function limpiarRazonSocial(cn, ruc) {
  let name = String(cn || '').trim();
  if (!name) return '';
  if (ruc) name = name.replace(new RegExp(ruc, 'g'), '').trim();
  name = name.replace(/[:\-|]+$/g, '').replace(/^[:\-|]+/g, '').trim();
  const parts = name.split(':');
  if (parts.length > 1) name = parts[0].trim();
  return name || cn;
}

function collectCertBag(p12) {
  const bags =
    p12.getBags({ bagType: forge.pki.oids.certBag })[forge.pki.oids.certBag] || [];
  return bags.map((b) => b.cert).filter(Boolean);
}

function leerInfoCertificado(p12Path, password) {
  if (!fs.existsSync(p12Path)) {
    return { success: false, mensaje: `Certificado no encontrado: ${p12Path}` };
  }
  try {
    const p12Buffer = fs.readFileSync(p12Path);
    const p12Asn1 = forge.asn1.fromDer(p12Buffer.toString('binary'));
    let p12;
    try {
      p12 = forge.pkcs12.pkcs12FromAsn1(p12Asn1, password);
    } catch (e) {
      return { success: false, mensaje: 'Contraseña incorrecta o archivo P12 inválido.' };
    }

    const certs = collectCertBag(p12);
    if (!certs.length) {
      return { success: false, mensaje: 'No se pudo leer el certificado del P12.' };
    }

    // Recorrer todos los certificados del contenedor (a veces el RUC está en uno secundario)
    let best = null;
    for (const cert of certs) {
      const attrs = cert.subject.attributes || [];
      const cn = attrValue(attrs, ['commonName', 'CN', '2.5.4.3']);
      const serialDn = attrValue(attrs, ['serialNumber', '2.5.4.5']);
      const org = attrValue(attrs, ['organizationName', 'O', '2.5.4.10']);
      const ou = attrValue(attrs, ['organizationalUnitName', 'OU', '2.5.4.11']);
      const title = attrValue(attrs, ['title', '2.5.4.12']);
      const email = attrValue(attrs, ['emailAddress', 'E', '1.2.840.113549.1.9.1']);
      const subjectText = allAttrText(attrs);

      let sanText = '';
      try {
        const ext = cert.getExtension('subjectAltName');
        if (ext && Array.isArray(ext.altNames)) {
          sanText = ext.altNames.map((n) => n.value || '').join(' ');
        }
      } catch (_) {
        /* ignore */
      }

      const blob = [serialDn, cn, title, org, ou, email, subjectText, sanText].join(' ');
      const ruc = findRucInText(blob);
      const razon = limpiarRazonSocial(cn || org, ruc) || cn || org || '';

      const candidate = {
        ruc: ruc || null,
        razon_social: razon,
        common_name: cn,
        subject: subjectText,
      };
      if (ruc) {
        best = candidate;
        break;
      }
      if (!best) best = candidate;
    }

    if (best && best.ruc) {
      return {
        success: true,
        ruc: best.ruc,
        razon_social: best.razon_social || `Emisor ${best.ruc}`,
        common_name: best.common_name,
        subject: best.subject,
      };
    }

    return {
      success: false,
      mensaje:
        'No se pudo leer un RUC de 13 dígitos del certificado. Ingresa el RUC manualmente en el formulario.',
      subject: best ? best.subject : '',
      common_name: best ? best.common_name : '',
      razon_social: best ? best.razon_social : '',
    };
  } catch (e) {
    return { success: false, mensaje: e.message || String(e) };
  }
}

module.exports = { leerInfoCertificado };
