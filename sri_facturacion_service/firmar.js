/**
 * Firma XAdES de factura XML con ec-sri-invoice-signer
 * (misma librería que el proyecto de escritorio / firmarXML3).
 */
const fs = require('fs');
const { signInvoiceXml } = require('ec-sri-invoice-signer');

function firmarXmlFactura(xml, p12Path, password) {
  if (!xml || typeof xml !== 'string') {
    return { success: false, mensaje: 'XML vacío o inválido.' };
  }
  if (!fs.existsSync(p12Path)) {
    return { success: false, mensaje: `Certificado no encontrado: ${p12Path}` };
  }

  try {
    const p12FileData = fs.readFileSync(p12Path);
    const signedInvoice = signInvoiceXml(xml, p12FileData, {
      pkcs12Password: password == null ? '' : String(password),
    });
    if (!signedInvoice || typeof signedInvoice !== 'string') {
      return { success: false, mensaje: 'La librería no devolvió un XML firmado.' };
    }
    return {
      success: true,
      mensaje: 'XML firmado correctamente (ec-sri-invoice-signer)',
      xmlFirmado: signedInvoice,
    };
  } catch (error) {
    const msg = error && error.message ? error.message : String(error);
    if (/password|contrase[nñ]a|mac|pkcs12|p12/i.test(msg)) {
      return {
        success: false,
        mensaje: 'Contraseña incorrecta o archivo P12 inválido. ' + msg,
      };
    }
    return { success: false, mensaje: msg };
  }
}

module.exports = { firmarXmlFactura };
