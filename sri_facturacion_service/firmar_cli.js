/**
 * CLI de firma XAdES para que Flask lo invoque.
 * STDIN JSON: { "xml": "...", "p12_path": "...", "password": "..." }
 * STDOUT JSON: { success, mensaje, xmlFirmado? }
 *
 * El .p12 lo pasa Flask en un archivo temporal; Flask lo borra después.
 */
const { firmarXmlFactura } = require('./firmar');

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  raw += chunk;
});
process.stdin.on('end', () => {
  try {
    const input = JSON.parse(raw || '{}');
    const xml = input.xml;
    const p12Path = input.p12_path;
    const password = input.password;
    if (!xml || !p12Path) {
      process.stdout.write(
        JSON.stringify({ success: false, mensaje: 'Faltan xml o p12_path.' })
      );
      process.exit(0);
      return;
    }
    const result = firmarXmlFactura(xml, p12Path, password == null ? '' : String(password));
    process.stdout.write(JSON.stringify(result));
  } catch (e) {
    process.stdout.write(
      JSON.stringify({ success: false, mensaje: e.message || String(e) })
    );
  }
});
