const axios = require('axios');
const https = require('https');
const xml2js = require('xml2js');
const {
  SRI_RECEPCION,
  SRI_AUTORIZACION,
  AMBIENTE_NOMBRE,
  assertUrlPruebas,
} = require('./config');

const agent = new https.Agent({
  keepAlive: true,
  rejectUnauthorized: true,
  timeout: 30000,
});

async function postSoap(url, body) {
  assertUrlPruebas(url);
  const response = await axios.post(url, body, {
    headers: {
      'Content-Type': 'text/xml; charset=UTF-8',
      SOAPAction: '',
    },
    timeout: 30000,
    httpsAgent: agent,
    maxBodyLength: Infinity,
    maxContentLength: Infinity,
    validateStatus: () => true,
  });
  if (response.status !== 200) {
    throw new Error(`SRI pruebas HTTP ${response.status}: ${String(response.data).slice(0, 300)}`);
  }
  return String(response.data);
}

async function enviarRecepcion(xmlFirmado) {
  const xmlBase64 = Buffer.from(xmlFirmado, 'utf8').toString('base64');
  const envelope = `<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.recepcion">
  <soapenv:Header/>
  <soapenv:Body>
    <ec:validarComprobante>
      <xml>${xmlBase64}</xml>
    </ec:validarComprobante>
  </soapenv:Body>
</soapenv:Envelope>`;

  const raw = await postSoap(SRI_RECEPCION, envelope);
  const parsed = await xml2js.parseStringPromise(raw, { explicitArray: false });
  const respuesta =
    parsed?.['soap:Envelope']?.['soap:Body']?.['ns2:validarComprobanteResponse']
      ?.RespuestaRecepcionComprobante;
  const estado = respuesta?.estado || null;
  const recibido = estado === 'RECIBIDO' || estado === 'RECIBIDA';

  let mensajes = [];
  const ms = respuesta?.comprobantes?.comprobante?.mensajes?.mensaje;
  if (Array.isArray(ms)) mensajes = ms;
  else if (ms) mensajes = [ms];

  return {
    ambiente: AMBIENTE_NOMBRE,
    url: SRI_RECEPCION,
    estado,
    recibido,
    mensajes,
    respuesta_xml: raw.slice(0, 4000),
  };
}

async function consultarAutorizacion(claveAcceso) {
  const envelope = `<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.autorizacion">
  <soapenv:Header/>
  <soapenv:Body>
    <ec:autorizacionComprobante>
      <claveAccesoComprobante>${claveAcceso}</claveAccesoComprobante>
    </ec:autorizacionComprobante>
  </soapenv:Body>
</soapenv:Envelope>`;

  const raw = await postSoap(SRI_AUTORIZACION, envelope);
  const parsed = await xml2js.parseStringPromise(raw, { explicitArray: false });
  const respuestaContent =
    parsed?.['soap:Envelope']?.['soap:Body']?.['ns2:autorizacionComprobanteResponse']
      ?.RespuestaAutorizacionComprobante;

  let estado = 'NO_AUTORIZADO';
  let autorizacion = null;
  if (respuestaContent?.autorizaciones?.autorizacion) {
    const lista = Array.isArray(respuestaContent.autorizaciones.autorizacion)
      ? respuestaContent.autorizaciones.autorizacion
      : [respuestaContent.autorizaciones.autorizacion];
    autorizacion = lista[0];
    estado = autorizacion.estado || estado;
  } else if (respuestaContent?.estado) {
    estado = respuestaContent.estado;
  }

  return {
    ambiente: AMBIENTE_NOMBRE,
    url: SRI_AUTORIZACION,
    clave_acceso: claveAcceso,
    estado,
    autorizado: String(estado).toUpperCase() === 'AUTORIZADO',
    numero_autorizacion: autorizacion?.numeroAutorizacion || null,
    fecha_autorizacion: autorizacion?.fechaAutorizacion || null,
    respuesta_xml: raw.slice(0, 4000),
  };
}

module.exports = { enviarRecepcion, consultarAutorizacion };
