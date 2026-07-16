# Microservicio WhatsApp — TecnoStock S.A.

**Tu propio WhatsApp por QR** (motor **Baileys**, el mismo que usa Evolution
en tu proyecto de facturación). **Sin Green-API, sin Meta Cloud API, sin CallMeBot.**

Los mensajes salen desde el número que escanees en `/vincular`.

## Arranque (igual patrón que los otros microservicios)

```powershell
cd whatsapp_service
npm install          # una vez
node server.js
```

Escucha en **http://localhost:5004**.

1. Abre **http://localhost:5004/vincular**
2. WhatsApp del teléfono → **Dispositivos vinculados** → escanea el QR
3. En Django (`:8000`):
   - Factura → **Enviar por WhatsApp**
   - Login 2FA (si el usuario tiene teléfono y 2FA activo)

## Endpoints

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/vincular` | Página con QR |
| GET | `/estado` | ¿Vinculado? ¿Número emisor? |
| GET | `/qr` | QR en JSON |
| POST | `/logout` | Cerrar sesión / nuevo QR |
| POST | `/mensajes/enviar` | Enviar texto (Django) |
| GET | `/health` | Health check |

## Nota sobre “Purple” / Evolution

- Pidgin/libpurple no es API HTTP.
- En `Proyectos Brayana\Analisis\facturacion` usas **Evolution + Baileys** en un servidor.
- Aquí Baileys corre **en tu PC**, sin depender de `wa.datasmartify.com` ni otra nube.

La sesión se guarda en la carpeta `session/` (no subir a Git).
