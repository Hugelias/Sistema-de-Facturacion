/**
 * CLI: lee RUC del .p12
 * STDIN JSON: { p12_path, password }
 * STDOUT JSON: { success, ruc?, razon_social?, mensaje? }
 */
const { leerInfoCertificado } = require('./cert_info');

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  raw += chunk;
});
process.stdin.on('end', () => {
  try {
    const input = JSON.parse(raw || '{}');
    const result = leerInfoCertificado(input.p12_path, input.password == null ? '' : String(input.password));
    process.stdout.write(JSON.stringify(result));
  } catch (e) {
    process.stdout.write(JSON.stringify({ success: false, mensaje: e.message || String(e) }));
  }
});
