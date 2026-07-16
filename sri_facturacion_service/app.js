/**
 * LEGACY Node-only server.
 * Usa ahora Flask:  python app.py
 *
 * La firma XAdES sigue en firmar.js / firmar_cli.js (invocada por Flask).
 */
console.error(
  'Deprecado: arranca Flask → python app.py\n'
  + 'La API es Flask; Node solo firma vía firmar_cli.js.'
);
process.exit(1);
