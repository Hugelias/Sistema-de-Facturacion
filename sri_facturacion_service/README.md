# sri_facturacion_service — SOLO PRUEBAS (celcer)

Flask es la API. Node solo firma XAdES (`firmar_cli.js` + `node-forge`).

El certificado **.p12 no se guarda**: TecnoStock muestra un modal, lo sube en ese
request, Flask lo escribe en un tempfile, Node firma, se borra el archivo y se
envía a celcer.

## Arranque

```bat
pip install -r requirements.txt
npm install
python app.py
```

Puerto: **5003**

Debes tener **Node.js** en el PATH (solo para firmar).

## Endpoints

| Método | Ruta | Notas |
|--------|------|--------|
| GET | `/salud` | Estado |
| POST | `/comprobantes/emitir` | **multipart**: `payload` (JSON), `password`, `certificado` (.p12) |
| POST | `/comprobantes/emitir-local` | Fallback sin SRI real |
| POST | `/comprobantes/firmar` | Solo firma (también con multipart) |
| POST | `/comprobantes/recibir` | SOAP recepción celcer |
| POST | `/comprobantes/autorizar` | SOAP autorización celcer |

## URLs oficiales (pruebas)

- Recepción: `https://celcer.sri.gob.ec/.../RecepcionComprobantesOffline?wsdl`
- Autorización: `https://celcer.sri.gob.ec/.../AutorizacionComprobantesOffline?wsdl`

Producción (`cel.sri.gob.ec`) está bloqueada en código.
