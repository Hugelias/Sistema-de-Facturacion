/**
 * Microservicio WhatsApp — TecnoStock S.A.
 *
 * Igual que tu proyecto de facturación (Baileys / Evolution), pero
 * 100 % LOCAL: escaneas el QR con TU WhatsApp y los mensajes salen
 * desde ese número. Sin Green-API, sin Meta Cloud API, sin CallMeBot.
 *
 * Arranque:
 *   npm install
 *   node server.js
 * Luego: http://localhost:5004/vincular
 */
import express from 'express';
import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
} from '@whiskeysockets/baileys';
import QRCode from 'qrcode';
import pino from 'pino';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 5004);
const AUTH_DIR = path.join(__dirname, 'session');
const DEFAULT_COUNTRY = (process.env.WHATSAPP_DEFAULT_COUNTRY || '593').replace(/\D/g, '') || '593';

const app = express();
app.use(express.json({ limit: '1mb' }));

const logger = pino({ level: process.env.LOG_LEVEL || 'silent' });

/** @type {import('@whiskeysockets/baileys').WASocket | null} */
let sock = null;
let lastQrDataUrl = null;
let connectionState = 'close'; // connecting | open | close
let numeroEmisor = null;
let startPromise = null;

function soloDigitos(v) {
  return String(v || '').replace(/\D/g, '');
}

function normalizarTelefono(telefono, codigoPais) {
  let digitos = soloDigitos(telefono);
  if (digitos.length < 8) throw new Error('El teléfono parece incompleto.');
  const pais = soloDigitos(codigoPais || DEFAULT_COUNTRY) || '593';

  if (digitos.startsWith(pais) && digitos.length >= pais.length + 8) {
    return digitos;
  }
  if (pais === '593' && digitos.startsWith('0') && digitos.length === 10) {
    digitos = digitos.slice(1);
  }
  return `${pais}${digitos}`;
}

async function ensureAuthDir() {
  if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
  }
}

async function startWhatsApp() {
  if (startPromise) return startPromise;
  startPromise = (async () => {
    await ensureAuthDir();
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
      version,
      auth: state,
      logger,
      printQRInTerminal: false,
      browser: ['TecnoStock', 'Chrome', '1.0.0'],
      syncFullHistory: false,
      markOnlineOnConnect: false,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        connectionState = 'connecting';
        try {
          lastQrDataUrl = await QRCode.toDataURL(qr, { margin: 2, width: 280 });
        } catch {
          lastQrDataUrl = null;
        }
      }

      if (connection === 'open') {
        connectionState = 'open';
        lastQrDataUrl = null;
        const id = sock?.user?.id || '';
        numeroEmisor = id.split(':')[0].split('@')[0] || null;
        console.log(`[whatsapp] Vinculado. Envía desde: +${numeroEmisor || '?'}`);
      }

      if (connection === 'close') {
        connectionState = 'close';
        numeroEmisor = null;
        const code = lastDisconnect?.error?.output?.statusCode;
        const shouldReconnect = code !== DisconnectReason.loggedOut;
        console.log(`[whatsapp] Desconectado (code=${code}). Reconectar=${shouldReconnect}`);
        sock = null;
        startPromise = null;
        if (shouldReconnect) {
          setTimeout(() => {
            startWhatsApp().catch((e) => console.error('[whatsapp] reconnect', e.message));
          }, 2000);
        } else {
          lastQrDataUrl = null;
        }
      }

      if (connection === 'connecting') {
        connectionState = 'connecting';
      }
    });

    return sock;
  })();

  try {
    return await startPromise;
  } catch (e) {
    startPromise = null;
    throw e;
  }
}

async function logoutWhatsApp() {
  try {
    if (sock) {
      await sock.logout().catch(() => {});
    }
  } finally {
    sock = null;
    startPromise = null;
    connectionState = 'close';
    numeroEmisor = null;
    lastQrDataUrl = null;
    if (fs.existsSync(AUTH_DIR)) {
      fs.rmSync(AUTH_DIR, { recursive: true, force: true });
    }
  }
  // Volver a generar QR
  await startWhatsApp();
}

const VINCULAR_HTML = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vincular WhatsApp — TecnoStock</title>
  <style>
    :root { --bg:#0f172a; --card:#1e293b; --text:#f8fafc; --muted:#94a3b8; --ok:#22c55e; --warn:#f59e0b; --accent:#25D366; }
    * { box-sizing: border-box; }
    body { margin:0; min-height:100vh; font-family: system-ui, Segoe UI, sans-serif;
           background: radial-gradient(ellipse at top, #1e293b, var(--bg)); color: var(--text);
           display:flex; align-items:center; justify-content:center; padding:24px; }
    .box { width:min(440px,100%); background:var(--card); border-radius:20px; padding:28px 24px;
           box-shadow:0 20px 50px rgba(0,0,0,.35); text-align:center; }
    h1 { margin:0 0 8px; font-size:1.35rem; }
    .sub { color:var(--muted); font-size:.9rem; margin:0 0 20px; line-height:1.45; }
    #qr { width:280px; height:280px; margin:0 auto 16px; background:#fff; border-radius:12px;
          display:flex; align-items:center; justify-content:center; overflow:hidden; }
    #qr img { width:100%; height:100%; object-fit:contain; }
    .badge { display:inline-block; padding:6px 12px; border-radius:999px; font-size:.8rem; font-weight:700; margin-bottom:12px; }
    .ok { background:rgba(34,197,94,.15); color:var(--ok); }
    .warn { background:rgba(245,158,11,.15); color:var(--warn); }
    .emisor { font-size:1.05rem; font-weight:700; color:var(--accent); margin:8px 0 4px; }
    ol { text-align:left; color:var(--muted); font-size:.85rem; line-height:1.55; margin:16px 0 0; padding-left:1.2rem; }
    button { margin-top:16px; border:none; border-radius:10px; padding:10px 16px; font-weight:700;
             cursor:pointer; background:#334155; color:#fff; }
    button:hover { background:#475569; }
    a { color:var(--accent); }
  </style>
</head>
<body>
  <div class="box">
    <h1>Vincular tu WhatsApp</h1>
    <p class="sub">Sesión local (Baileys), igual que WhatsApp Web. <strong>Sin plataformas externas.</strong> Los mensajes salen desde el número que escanees.</p>
    <div id="estado" class="badge warn">Comprobando…</div>
    <div class="emisor" id="emisor"></div>
    <div id="qr"><span style="color:#64748b;font-size:.85rem;padding:12px">Cargando QR…</span></div>
    <ol>
      <li>Abre WhatsApp en el teléfono de la empresa.</li>
      <li>Menú → <strong>Dispositivos vinculados</strong> → Vincular dispositivo.</li>
      <li>Escanea este código.</li>
      <li>En Django usa <strong>Enviar por WhatsApp</strong> en la factura.</li>
    </ol>
    <button type="button" id="btn-refresh">Actualizar</button>
    <button type="button" id="btn-logout" style="background:#7f1d1d;margin-left:8px">Cerrar sesión</button>
    <p class="sub" style="margin-top:18px;margin-bottom:0"><a href="/estado">/estado</a> · <a href="/health">/health</a></p>
  </div>
  <script>
    async function j(url, opts) {
      const r = await fetch(url, opts);
      return r.json();
    }
    async function refresh() {
      const est = document.getElementById('estado');
      const emisor = document.getElementById('emisor');
      const qr = document.getElementById('qr');
      try {
        const s = await j('/estado');
        if (s.autorizado) {
          est.className = 'badge ok';
          est.textContent = 'Vinculado — listo para enviar';
          emisor.textContent = s.numero_emisor ? ('Envía desde: +' + s.numero_emisor) : 'WhatsApp autorizado';
          qr.innerHTML = '<span style="color:#166534;font-weight:700;padding:16px">Sesión activa</span>';
          return;
        }
        est.className = 'badge warn';
        est.textContent = s.detalle || 'Esperando escaneo…';
        emisor.textContent = '';
        const q = await j('/qr');
        if (q.ok && q.imagen_data_url) {
          qr.innerHTML = '<img alt="QR WhatsApp" src="' + q.imagen_data_url + '">';
        } else {
          qr.innerHTML = '<span style="color:#64748b;padding:12px;font-size:.85rem">' +
            (q.detalle || 'Generando QR… espera unos segundos') + '</span>';
        }
      } catch (e) {
        est.className = 'badge warn';
        est.textContent = 'Error de red';
        qr.innerHTML = '<span style="color:#b91c1c;padding:12px;font-size:.85rem">' + e + '</span>';
      }
    }
    document.getElementById('btn-refresh').onclick = refresh;
    document.getElementById('btn-logout').onclick = async () => {
      await j('/logout', { method: 'POST' });
      setTimeout(refresh, 1500);
    };
    refresh();
    setInterval(refresh, 4000);
  </script>
</body>
</html>`;

app.get('/', (_req, res) => {
  res.json({
    ok: true,
    servicio: 'whatsapp_service',
    motor: 'baileys',
    mensaje: 'WhatsApp propio por QR (local). Sin Meta Cloud / Green-API.',
    vincular_qr: 'GET /vincular',
    endpoints: {
      estado: 'GET /estado',
      qr: 'GET /qr',
      logout: 'POST /logout',
      enviar: 'POST /mensajes/enviar',
      health: 'GET /health',
    },
    django: 'http://localhost:8000 — botón Enviar por WhatsApp',
  });
});

app.get('/vincular', (_req, res) => {
  res.type('html').send(VINCULAR_HTML);
});

app.get('/estado', (_req, res) => {
  const autorizado = connectionState === 'open' && Boolean(sock);
  res.json({
    ok: true,
    proveedor: 'baileys',
    motor: 'baileys-local',
    estado: connectionState,
    autorizado,
    numero_emisor: autorizado ? numeroEmisor : null,
    detalle: autorizado
      ? 'WhatsApp vinculado. Los mensajes salen desde ese número.'
      : 'Escanea el QR en /vincular con tu WhatsApp (Dispositivos vinculados).',
  });
});

app.get('/qr', (_req, res) => {
  if (connectionState === 'open') {
    return res.json({
      ok: true,
      type: 'alreadyLogged',
      detalle: 'Ya hay un WhatsApp vinculado.',
      numero_emisor: numeroEmisor,
    });
  }
  if (lastQrDataUrl) {
    return res.json({
      ok: true,
      type: 'qrCode',
      imagen_data_url: lastQrDataUrl,
      detalle: 'Escanea con WhatsApp → Dispositivos vinculados.',
    });
  }
  return res.json({
    ok: false,
    type: 'waiting',
    detalle: 'Aún no hay QR. Espera 2–5 s y pulsa Actualizar.',
  });
});

app.post('/logout', async (_req, res) => {
  try {
    await logoutWhatsApp();
    res.json({ ok: true, detalle: 'Sesión cerrada. Escanea el nuevo QR.' });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message || String(e) });
  }
});

app.get('/health', (_req, res) => {
  res.json({
    ok: true,
    servicio: 'whatsapp_service',
    motor: 'baileys',
    estado: connectionState,
    autorizado: connectionState === 'open',
    numero_emisor: numeroEmisor,
    meta_cloud_api: false,
    plataforma_externa: false,
    vincular: '/vincular',
  });
});

app.post('/mensajes/enviar', async (req, res) => {
  try {
    const telefono = req.body?.telefono || req.body?.phone || '';
    const mensaje = String(req.body?.mensaje || req.body?.message || '').trim();
    const codigoPais = req.body?.codigo_pais || req.body?.country_code;

    if (!mensaje) {
      return res.status(400).json({ ok: false, error: 'El mensaje es obligatorio.' });
    }
    if (mensaje.length > 4000) {
      return res.status(400).json({ ok: false, error: 'El mensaje es demasiado largo (máx. 4000).' });
    }
    if (connectionState !== 'open' || !sock) {
      return res.status(502).json({
        ok: false,
        error: 'WhatsApp no está vinculado. Abre http://localhost:5004/vincular y escanea el QR.',
        proveedor: 'baileys',
      });
    }

    const destino = normalizarTelefono(telefono, codigoPais);
    const jid = `${destino}@s.whatsapp.net`;
    await sock.sendMessage(jid, { text: mensaje });

    return res.json({
      ok: true,
      proveedor: 'baileys',
      telefono: destino,
      numero_emisor: numeroEmisor,
      detalle: `Mensaje enviado desde WhatsApp +${numeroEmisor || '?'} hacia ${destino}.`,
    });
  } catch (e) {
    return res.status(502).json({
      ok: false,
      error: e.message || String(e),
      proveedor: 'baileys',
    });
  }
});

app.listen(PORT, async () => {
  console.log(`whatsapp_service (Baileys local) en http://localhost:${PORT}`);
  console.log(`Vincular tu WhatsApp: http://localhost:${PORT}/vincular`);
  try {
    await startWhatsApp();
  } catch (e) {
    console.error('No se pudo iniciar Baileys:', e.message || e);
  }
});
