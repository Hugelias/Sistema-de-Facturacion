# sri_service — Consulta RUC (catastro SRI)

Flask independiente. Django **no** consulta el SRI directamente: llama a este
servicio (`:5002`), que consulta el catastro de contribuyentes.

## Instalación (una vez)

```powershell
cd sri_service
pip install -r requirements.txt
```

## Ejecución

```powershell
cd sri_service
python app.py
```

Escucha en **http://localhost:5002**

## Uso en TecnoStock

Botón **Consultar SRI** al crear/editar proveedores (rellena razón social, dirección, etc.).
