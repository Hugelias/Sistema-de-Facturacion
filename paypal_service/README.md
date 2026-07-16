# paypal_service — Microservicio PayPal

Flask independiente. Django **no** habla con PayPal directamente: llama a este
servicio (`:5001`), que usa la Orders API v2 (Sandbox).

## Instalación (una vez)

```powershell
cd paypal_service
pip install -r requirements.txt
```

Configura `PAYPAL_CLIENT_ID` y `PAYPAL_CLIENT_SECRET` (variables de entorno o
valores en `app.py`) desde [developer.paypal.com](https://developer.paypal.com/).
El mismo Client ID público debe coincidir con `PAYPAL_CLIENT_ID` en
`config/settings.py`.

## Ejecución

```powershell
cd paypal_service
python app.py
```

Escucha en **http://localhost:5001**

## Uso en TecnoStock

Necesario para cobrar saldos pendientes con PayPal en la vista pública de factura.
