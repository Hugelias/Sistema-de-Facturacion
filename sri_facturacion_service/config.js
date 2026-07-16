/**
 * Configuración SRI — ÚNICAMENTE ambiente de PRUEBAS (celcer).
 * Producción (cel.sri.gob.ec) está prohibida en este microservicio.
 */
require('dotenv').config();
const path = require('path');
const fs = require('fs');

const AMBIENTE_CODIGO = '1';
const AMBIENTE_NOMBRE = 'PRUEBAS';

const SRI_RECEPCION =
  'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl';
const SRI_AUTORIZACION =
  'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl';

const URLS_PERMITIDAS = new Set([SRI_RECEPCION, SRI_AUTORIZACION]);

function assertUrlPruebas(url) {
  if (!URLS_PERMITIDAS.has(url)) {
    throw new Error(
      'URL SRI no permitida. Este servicio solo usa ambiente de pruebas (celcer).'
    );
  }
}

function getCertConfig() {
  const p12Path = (process.env.SRI_CERT_P12 || '').trim();
  const password = process.env.SRI_CERT_PASSWORD || '';
  if (!p12Path) {
    throw new Error(
      'Falta SRI_CERT_P12 en .env (ruta al certificado .p12 de pruebas).'
    );
  }
  if (!password) {
    throw new Error('Falta SRI_CERT_PASSWORD en .env.');
  }
  const resolved = path.resolve(p12Path);
  if (!fs.existsSync(resolved)) {
    throw new Error(`No se encontró el certificado .p12 en: ${resolved}`);
  }
  return { p12Path: resolved, password };
}

module.exports = {
  PORT: Number(process.env.PORT || 5003),
  AMBIENTE_CODIGO,
  AMBIENTE_NOMBRE,
  SRI_RECEPCION,
  SRI_AUTORIZACION,
  WAIT_AUTORIZACION_MS: Number(process.env.SRI_WAIT_AUTORIZACION_SEC || 3) * 1000,
  assertUrlPruebas,
  getCertConfig,
};
