# Sistema de Ventas y Facturación — TecnoStock S.A.

Sistema web de gestión de ventas, facturación, compras e inventario desarrollado con Django 6 para la empresa TecnoStock S.A.

Incluye **4 microservicios** auxiliares (PayPal, SRI RUC, facturación electrónica celcer, WhatsApp/2FA).

---

## Tecnologías

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.14, Django 6.0.6 |
| Microservicios | Flask (PayPal, SRI, Facturación) + Node/Baileys (WhatsApp) |
| Base de datos | SQLite (desarrollo) |
| Frontend | Bootstrap 5.3, Bootstrap Icons 1.11.3, Chart.js 4.x |
| Fuente tipográfica | Inter (Google Fonts) |

---

## Estructura del proyecto

```
Sistema de Ventas y Facturación/
├── config/                    # Settings, URLs raíz
├── billing/                   # Ventas, facturación, catálogo, clientes
├── purchasing/                # Compras a proveedores
├── cobros/                    # Cuentas por cobrar
├── pagos/                     # Cuentas por pagar
├── security/                  # Usuarios, grupos, login, 2FA WhatsApp
├── shared/                    # Mixins, decoradores, validadores
├── templates/                 # Plantillas globales
├── paypal_service/            # Microservicio PayPal          → :5001
├── sri_service/               # Microservicio consulta RUC    → :5002
├── sri_facturacion_service/   # Factura electrónica (pruebas) → :5003
├── whatsapp_service/          # WhatsApp propio (Baileys)     → :5004
├── manage.py
└── requirements.txt           # Dependencias del proyecto Django
```

---

## Instalación y ejecución (guía rápida)

> En Windows, si el comando `python` no funciona, usa la ruta completa, por ejemplo:  
> `C:\Users\user\AppData\Local\Python\pythoncore-3.14-64\python.exe`

### Requisitos previos

- **Python 3.14** (o 3.12+)
- **Node.js 18+** (solo para facturación SRI y WhatsApp)
- Opcional: entorno virtual `venv/`

---

### 1) Proyecto principal (Django) — puerto **8000**

**Instalación (una vez):**

```powershell
cd "C:\Users\user\Documents\Sistema de Ventas y Facturación"

# Opcional: entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

**Ejecución (cada vez que trabajes en el sistema):**

```powershell
cd "C:\Users\user\Documents\Sistema de Ventas y Facturación"
python manage.py runserver
```

Abrir: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)  
Entrada: [http://127.0.0.1:8000/accounts/select-role/](http://127.0.0.1:8000/accounts/select-role/)

---

### 2) Microservicio PayPal — puerto **5001**

Documentación: **[paypal_service/README.md](paypal_service/README.md)**

```powershell
# Instalación (una vez)
cd paypal_service
pip install -r requirements.txt

# Ejecución
python app.py
```

→ [http://localhost:5001](http://localhost:5001)

---

### 3) Microservicio SRI (consulta RUC) — puerto **5002**

Documentación: **[sri_service/README.md](sri_service/README.md)**

```powershell
# Instalación (una vez)
cd sri_service
pip install -r requirements.txt

# Ejecución
python app.py
```

→ [http://localhost:5002](http://localhost:5002)

---

### 4) Microservicio facturación electrónica SRI (solo pruebas) — puerto **5003**

Documentación: **[sri_facturacion_service/README.md](sri_facturacion_service/README.md)**

Requiere **Node.js** (firma XAdES) + Python/Flask.

```powershell
# Instalación (una vez)
cd sri_facturacion_service
pip install -r requirements.txt
npm install

# Ejecución
python app.py
```

→ [http://localhost:5003](http://localhost:5003)

Solo ambiente **celcer** (pruebas). El `.p12` se pide en un modal y **no se guarda**.

---

### 5) Microservicio WhatsApp (Baileys, tu propio número) — puerto **5004**

Documentación: **[whatsapp_service/README.md](whatsapp_service/README.md)**

Requiere **Node.js**. Sin Meta Cloud API ni Green-API.

```powershell
# Instalación (una vez)
cd whatsapp_service
npm install

# Ejecución
node server.js
```

→ [http://localhost:5004](http://localhost:5004)  
Vincular QR: [http://localhost:5004/vincular](http://localhost:5004/vincular)

Usos en TecnoStock:

- Botón **Enviar por WhatsApp** en el detalle de factura
- **2FA al login**: código temporal al teléfono del usuario (`/security/users/`)

---

### Resumen de puertos

| Qué | Puerto | Instalar | Correr | README |
|-----|--------|----------|--------|--------|
| Django (TecnoStock) | **8000** | `pip install -r requirements.txt` + `migrate` | `python manage.py runserver` | este archivo |
| PayPal | **5001** | `pip install -r paypal_service/requirements.txt` | `python paypal_service/app.py` | [paypal_service/README.md](paypal_service/README.md) |
| SRI RUC | **5002** | `pip install -r sri_service/requirements.txt` | `python sri_service/app.py` | [sri_service/README.md](sri_service/README.md) |
| Facturación SRI | **5003** | `pip` + `npm install` en la carpeta | `python sri_facturacion_service/app.py` | [sri_facturacion_service/README.md](sri_facturacion_service/README.md) |
| WhatsApp | **5004** | `npm install` en la carpeta | `node whatsapp_service/server.js` | [whatsapp_service/README.md](whatsapp_service/README.md) |

Cada microservicio se abre en **su propia terminal**. Django puede arrancar solo; los demás solo cuando uses esa función.

---

### Orden sugerido al levantar todo

```text
Terminal 1 → Django          (:8000)
Terminal 2 → PayPal          (:5001)   si vas a cobrar con PayPal
Terminal 3 → SRI RUC         (:5002)   si vas a consultar RUC de proveedores
Terminal 4 → Facturación SRI (:5003)   si vas a autorizar facturas en celcer
Terminal 5 → WhatsApp        (:5004)   si vas a enviar facturas o usar 2FA
```

---

## Módulos

### `billing` — Ventas y Facturación

Módulo central del sistema. Gestiona el catálogo de productos, clientes y el ciclo de facturación.

**Modelos:**

| Modelo | Descripción |
|--------|-------------|
| `Brand` | Marcas de productos |
| `ProductGroup` | Grupos / categorías de productos |
| `Supplier` | Proveedores con RUC, contacto, email y dirección |
| `Product` | Productos con stock, precio unitario, marca, grupo y foto |
| `Customer` | Clientes con cédula o RUC ecuatoriano. Incluye `is_generic` para el cliente sembrado **Consumidor Final** (DNI `9999999999999`) |
| `CustomerProfile` | Tipo de contribuyente, plazo de pago y límite de crédito (manual, heredado) |
| `Invoice` | Facturas con IVA 15% calculado automáticamente. Incluye `tipo_pago` (Contado/Crédito), `saldo` y `estado` (Pendiente/Pagada) para ventas a crédito |
| `InvoiceDetail` | Líneas de factura con subtotal auto-calculado |

**Rutas (`/`):**

| Ruta | Descripción |
|------|-------------|
| `/` | Dashboard con KPIs, gráficos y resumen financiero |
| `/brands/` | Listado de marcas con filtros y paginación |
| `/brands/create/` | Nueva marca |
| `/brands/<id>/edit/` | Editar marca |
| `/brands/<id>/delete/` | Eliminar marca |
| `/groups/` | Listado de grupos de productos |
| `/groups/create/` | Nuevo grupo |
| `/groups/<id>/edit/` | Editar grupo |
| `/groups/<id>/delete/` | Eliminar grupo |
| `/suppliers/` | Listado de proveedores con filtros y paginación |
| `/suppliers/create/` | Nuevo proveedor |
| `/suppliers/<id>/edit/` | Editar proveedor |
| `/suppliers/<id>/delete/` | Eliminar proveedor |
| `/products/` | Catálogo de productos con filtros, exportación y paginación |
| `/products/create/` | Nuevo producto |
| `/products/<id>/` | Detalle de producto |
| `/products/<id>/edit/` | Editar producto |
| `/products/<id>/delete/` | Eliminar producto |
| `/customers/` | Listado de clientes con KPIs y filtros |
| `/customers/create/` | Nuevo cliente con validación de cédula ecuatoriana |
| `/customers/<id>/` | Perfil de cliente |
| `/customers/<id>/edit/` | Editar cliente |
| `/customers/<id>/delete/` | Eliminar cliente |
| `/invoices/` | Listado de facturas con filtros avanzados |
| `/invoices/create/` | Nueva factura con formset dinámico |
| `/invoices/<id>/` | Detalle de factura |
| `/invoices/<id>/edit/` | Editar factura |
| `/invoices/<id>/pdf/` | Vista PDF de factura |
| `/invoices/<id>/delete/` | Anular factura |
| `/accounts/select-role/` | Selección de perfil (pantalla de entrada al sistema) |
| `/accounts/login/` | Login, consciente del rol elegido (ver sección "Autenticación") |
| `/accounts/login/2fa/` | Código WhatsApp (2FA) tras usuario/contraseña |
| `/accounts/signup/` | Solicitud de acceso (crea la cuenta inactiva, pendiente de aprobación) |
| `/security/users/` | Listado de usuarios con KPIs, filtros por nombre, grupo y estado |
| `/security/users/create/` | Nuevo usuario (teléfono WhatsApp + 2FA opcional) |
| `/security/users/<id>/edit/` | Editar usuario (datos, grupo, teléfono, 2FA, contraseña) |
| `/security/users/<id>/toggle/` | Activar / desactivar usuario |
| `/security/groups/` | Listado de grupos con conteo de usuarios y permisos |

---

### `purchasing` — Compras

Registra las compras a proveedores y actualiza el stock de productos automáticamente al confirmar.

**Modelos:**

| Modelo | Descripción |
|--------|-------------|
| `Purchase` | Orden de compra con IVA 15%. Incluye `tipo_pago` (Contado/Crédito), `saldo` y `estado` (Pendiente/Pagada) para compras a crédito |
| `PurchaseDetail` | Líneas de compra con subtotal auto-calculado |

**Rutas (`/purchasing/`):**

| Ruta | Descripción |
|------|-------------|
| `/purchasing/` | Listado de compras con filtros y paginación |
| `/purchasing/new/` | Nueva compra con formset dinámico e IVA calculado en cliente |
| `/purchasing/<id>/` | Detalle de compra |
| `/purchasing/<id>/delete/` | Anular compra |

---

### `cobros` — Cobro de Facturas a Crédito

Módulo de cuentas por cobrar: registra los abonos que los clientes hacen sobre facturas emitidas a crédito y mantiene su saldo y estado siempre al día.

**Modelos:**

| Modelo | Descripción |
|--------|-------------|
| `CobroFactura` | Abono sobre una `Invoice` a crédito: factura (FK), fecha de pago, valor y observación |

**Rutas (`/cobros/`):**

| Ruta | Descripción |
|------|-------------|
| `/cobros/pendientes/` | Listado de facturas a crédito con saldo pendiente, con filtro por cliente |
| `/cobros/facturas/<id>/pagos/` | Historial de pagos de una factura, con saldo y estado en tiempo real |
| `/cobros/facturas/<id>/pagos/nuevo/` | Registrar un nuevo abono |
| `/cobros/pagos/<id>/edit/` | Editar un abono |
| `/cobros/pagos/<id>/delete/` | Eliminar un abono (bloqueado si la factura ya está pagada por completo) |

**Reglas de negocio:**

- `Invoice.actualizar_saldo()` recalcula `saldo` y `estado` como `total − Σ(cobros.valor)` cada vez que se crea, edita o elimina un abono — nunca se incrementa/decrementa a mano, así el saldo no puede quedar inconsistente.
- No se puede abonar a una factura anulada ni ya pagada por completo.
- No se aceptan abonos `<= 0` ni mayores al saldo pendiente.
- La fecha de pago no puede ser anterior a la fecha de emisión de la factura (sí admite hoy o fechas futuras).
- Un abono solo puede eliminarse mientras la factura siga en estado *Pendiente*.

---

### `pagos` — Pago de Compras a Crédito

Módulo de cuentas por pagar: registra los pagos que la empresa hace a sus proveedores sobre compras efectuadas a crédito y mantiene su saldo y estado siempre al día. Reutiliza el modelo `Purchase` ya existente en `purchasing`, siguiendo el mismo patrón que `cobros`.

**Modelos:**

| Modelo | Descripción |
|--------|-------------|
| `PagoCompra` | Pago sobre una `Purchase` a crédito: compra (FK), fecha de pago, valor y observación |

**Rutas (`/pagos/`):**

| Ruta | Descripción |
|------|-------------|
| `/pagos/pendientes/` | Listado de compras a crédito con saldo pendiente, con filtro por proveedor |
| `/pagos/compras/<id>/pagos/` | Historial de pagos de una compra, con saldo y estado en tiempo real |
| `/pagos/compras/<id>/pagos/nuevo/` | Registrar un nuevo pago |
| `/pagos/pagos/<id>/edit/` | Editar un pago |
| `/pagos/pagos/<id>/delete/` | Eliminar un pago (bloqueado si la compra ya está cancelada por completo) |

**Reglas de negocio:**

- `Purchase.actualizar_saldo()` recalcula `saldo` y `estado` como `total − Σ(pagos.valor)` cada vez que se crea, edita o elimina un pago — igual que en `cobros`, nunca se incrementa/decrementa a mano.
- No se puede pagar una compra anulada ni ya cancelada por completo.
- No se aceptan pagos `<= 0` ni mayores al saldo pendiente.
- Un pago solo puede eliminarse mientras la compra siga en estado *Pendiente*.
- Registrar y eliminar un pago corre dentro de una transacción (`@transaction.atomic`) para que el pago y el recálculo de saldo se confirmen o reviertan juntos.

---

### `security` — Usuarios, grupos y 2FA

| Pieza | Descripción |
|-------|-------------|
| Usuarios / grupos | Alta, edición, activación; asignación de roles |
| `UserProfile` | Teléfono WhatsApp + flag 2FA |
| `LoginOTPCode` | Código de 6 dígitos en BD (válido 10 min) enviado por WhatsApp al login |
| Flujo 2FA | Usuario/contraseña → código WhatsApp → ingreso |

Detalle del microservicio: [whatsapp_service/README.md](whatsapp_service/README.md)

---

### `shared` — Utilidades

| Componente | Descripción |
|-----------|-------------|
| `PermissionMixin` | Redirige a login si no autentica; lanza 403 si le falta el permiso requerido |
| `StaffRequiredMixin` | Restringe una CBV a usuarios `is_staff`, redirige con mensaje de error si no lo es |
| `@staff_required` | Equivalente a `StaffRequiredMixin` para vistas basadas en función |
| `ExportMixin` | Exportación a PDF y Excel desde cualquier `ListView` |
| `@audit_action` | Registra en log cada acción con usuario, ruta y tipo de operación |
| `validate_cedula_ec` | Valida cédula (10 dígitos) y RUC (13 dígitos) con algoritmo del SRI |

---

## Formularios personalizados

### `billing/forms.py`

| Clase | Modelo | Notas |
|-------|--------|-------|
| `SignUpForm` | `User` | Extiende `UserCreationForm` con nombres y email; `save()` crea la cuenta con `is_active=False` (solicitud de acceso, pendiente de aprobación) |
| `BrandForm` | `Brand` | `ActiveSelect` para `is_active` |
| `ProductGroupForm` | `ProductGroup` | `ActiveSelect` para `is_active` |
| `SupplierForm` | `Supplier` | `ActiveSelect` para `is_active`; grilla 2 columnas |
| `ProductForm` | `Product` | Toggle switch para `is_active`, `FileInput` para imagen, valida precio > 0 |
| `InvoiceForm` | `Invoice` | Cliente vía `CustomerChoiceField`: en el desplegable muestra junto al nombre si es *Nuevo en crédito*, tiene *Historial de crédito bueno* o es el *Consumidor Final*, con su límite calculado. En `clean()` bloquea crédito para el Consumidor Final |
| `InvoiceDetailForm` | `InvoiceDetail` | Valida stock disponible en `clean()`; usado dentro de `InvoiceDetailFormSet` |

`ActiveSelect` es un widget `Select` personalizado con opciones `[('True', 'Activo'), ('False', 'Inactivo')]`, compatible con `BooleanField` de Django.

`InvoiceDetailFormSet` se construye con `inlineformset_factory(Invoice, InvoiceDetail, formset=BaseInvoiceDetailFormSet, ...)`. `BaseInvoiceDetailFormSet.clean()` rechaza la factura si el mismo producto aparece en más de una línea no eliminada (reforzado también en el navegador, marcando el `<select>` duplicado en rojo).

La validación del límite de crédito (`_check_credit_limit`, en `billing/views.py`) corre en `invoice_create`/`invoice_update` **antes** de guardar nada: calcula el total propuesto a partir del formset, lo suma a la deuda pendiente del cliente y lo compara contra `Customer.get_credit_limit()`.

### `security/forms.py`

| Clase | Notas |
|-------|-------|
| `UserCreateForm` / `UserEditForm` | Usuario + grupo + **teléfono WhatsApp** + switch **2FA** |
| `RoleAwareAuthenticationForm` | Login con mensajes por rol / cuenta inactiva |
| `LoginOTPForm` | Código de 6 dígitos del 2FA |

### `purchasing/forms.py`

| Clase | Modelo | Notas |
|-------|--------|-------|
| `PurchaseForm` | `Purchase` | Selecciona proveedor, N° de factura del proveedor y tipo de pago (Contado/Crédito); valida que no haya duplicados por proveedor + N° de documento |
| `PurchaseDetailFormSet` | `PurchaseDetail` | Formset inline con campos producto, cantidad y costo unitario |

### `cobros/forms.py`

| Clase | Modelo | Notas |
|-------|--------|-------|
| `CobroFacturaForm` | `CobroFactura` | Campo `fecha` con formato ISO fijo (evita que el `<input type="date">` se vacíe por el locale `es-ec`). Valida en `clean_fecha` que no sea anterior a la factura, y en `clean_valor` que sea `> 0` y no exceda el saldo pendiente |

### `pagos/forms.py`

| Clase | Modelo | Notas |
|-------|--------|-------|
| `PagoCompraForm` | `PagoCompra` | Mismo patrón que `CobroFacturaForm`: campo `fecha` en formato ISO fijo; `clean_valor` exige `> 0` y no exceder el saldo pendiente de la compra |

---

## Límite de crédito por cliente

`Customer.get_credit_limit()` calcula el límite de crédito automáticamente a partir del historial de facturas del propio cliente — no es un valor que se edite a mano:

| Situación del cliente | Límite |
|------------------------|--------|
| Nunca ha comprado a crédito | $ 400 |
| Ya usó crédito antes y lo pagó por completo (sin saldo pendiente actual) | $ 2 000 |
| Tiene una factura a crédito pendiente ahora mismo | $ 400 (se mantiene conservador hasta que salde su deuda) |
| Consumidor Final | $ 0 (no aplica; el crédito está bloqueado para este cliente) |

`Customer.credit_status_label()` traduce esa misma lógica a un texto ("Nuevo en crédito", "Historial de crédito bueno", "Crédito pendiente", "Consumidor Final") que se muestra junto al nombre del cliente en el selector de `InvoiceForm`.

---

## Autenticación y control de acceso

Módulo de seguridad basado en el sistema de `auth` de Django (grupos + permisos), extendido con una pantalla de selección de perfil, aprobación manual de cuentas nuevas y **2FA por WhatsApp**.

### Grupos y permisos

4 grupos, cada uno con solo los permisos que necesita (asignados por grupo, nunca al usuario directamente):

| Grupo | Alcance |
|-------|---------|
| **Administrador** | CRUD completo en `billing`, `purchasing`, `cobros` y `pagos` |
| **Gerente** | Solo `view_*` en todos los modelos (consulta y exportación de reportes, sin eliminar) |
| **Compras** | CRUD en proveedores y compras (`purchasing`) + cuentas por pagar (`pagos`); sin acceso a clientes/facturas/cobros |
| **Ventas** | CRUD en clientes y facturas (`billing`) + cuentas por cobrar (`cobros`); sin acceso a proveedores/compras/pagos |

Cada grupo tiene un usuario de ejemplo (`administrador`, `gerente`, `comprador`, `vendedor`) además del superusuario `admin`. **Los grupos y sus permisos viven en la base de datos, no en una migración** — si el proyecto se reinstala desde cero hay que volver a crearlos (vía Django Admin o un script one-off), igual que indica la Guía Práctica 4 del curso.

### Flujo de login

1. **`/accounts/select-role/`** es el punto de entrada: `LOGIN_URL` y `LOGOUT_REDIRECT_URL`.
2. Cada tarjeta de perfil enlaza a `/accounts/login/?role=<perfil>`.
3. `RoleAwareAuthenticationForm` valida cuenta activa, grupo y rol elegido.
4. Si el usuario tiene **2FA WhatsApp** activo (`UserProfile`): no entra aún → se genera `LoginOTPCode` en BD, se envía por `whatsapp_service` y se pide el código en `/accounts/login/2fa/`.
5. Sin 2FA (o sin teléfono): login normal.

### Solicitud de acceso (signup)

`/accounts/signup/` crea la cuenta con `is_active = False`. Un administrador la aprueba desde `/security/users/` (activar + grupo + opcionalmente teléfono/2FA).

### Protección de cuentas de superusuario

Un `is_staff` no-superusuario no puede editar/toggle cuentas de superusuario.

---

## Funcionalidades destacadas

- **Dashboard interactivo:** KPIs, gráficos Ventas vs Compras, distribución por grupo.
- **Catálogo de productos:** filtros, exportación PDF/Excel, paginación.
- **Clientes:** KPIs, cédula/RUC ecuatoriano, límite de crédito automático.
- **Facturación:** IVA 15%, contado/crédito, PDF/XML, anulación lógica.
- **Facturación electrónica SRI (pruebas):** modal `.p12` → microservicio `:5003` → celcer.
- **PayPal:** cobro de saldos vía microservicio `:5001`.
- **WhatsApp:** envío de enlace de factura + **2FA en login** vía `:5004`.
- **Cobros / pagos** a crédito con saldo recalculado siempre desde la suma de abonos.
- **Consulta RUC SRI** en proveedores (`:5002`).
- **Autenticación por perfil** + gestión de usuarios/grupos + 2FA WhatsApp.
- **Auditoría** de acciones críticas.

---

## Diseño de interfaz (UI/UX)

- **Sidebar oscuro** colapsable con estado en `localStorage`.
- **Topbar sticky** con búsqueda global (`Ctrl + /`).
- **Páginas de auth standalone** (rol, login, signup, reset, 2FA WhatsApp).
- Bootstrap Icons 1.11.3 y fuente Inter.
- Mensajes flash (Django `messages`) en el layout base.

### Plantillas por módulo

| Sección | Plantillas |
|---------|-----------|
| Global | `base.html` |
| Auth | `role_select.html`, `login.html`, `login_2fa.html`, `signup.html`, reset password |
| Admin | `admin/index.html` |
| Billing | `home.html`, `brand_*.html`, `productgroup_*.html`, `supplier_*.html`, `product_*.html`, `customer_*.html`, `invoice_*.html` |
| Security | `user_*.html`, `group_*.html` |
| Purchasing | `purchase_*.html` |
| Cobros | `factura_pendiente_list.html`, `cobro_*.html` |
| Pagos | `compra_pendiente_list.html`, `pago_*.html` |

---

## Usuarios del sistema

| Usuario | Grupo | Notas |
|---------|-------|-------|
| `admin` | — (superusuario) | Contraseña gestionada por el desarrollador; no está documentada aquí. Bypasa las restricciones de rol/grupo en el login. |
| `administrador` | Administrador | Acceso completo vía grupo |
| `gerente` | Gerente | Solo consulta |
| `comprador` | Compras | Proveedores, compras y pagos |
| `vendedor` | Ventas | Clientes, facturas y cobros |

Panel de administración: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## Documentación de microservicios

| Servicio | README |
|----------|--------|
| PayPal | [paypal_service/README.md](paypal_service/README.md) |
| SRI RUC | [sri_service/README.md](sri_service/README.md) |
| Facturación electrónica | [sri_facturacion_service/README.md](sri_facturacion_service/README.md) |
| WhatsApp / 2FA | [whatsapp_service/README.md](whatsapp_service/README.md) |

---

## Contexto académico

Proyecto desarrollado para la asignatura de Programación Orientada a Objetos. El módulo `cobros` amplía el sistema con el caso **"Integración de Pagos de Créditos"**; el módulo `pagos` con **"Pago de Compras a Crédito"**. El módulo de seguridad sigue la **"Guía Práctica 4 — Desarrollo del Módulo de Seguridad utilizando el Administrador de Django"**. Los microservicios (PayPal, SRI, facturación electrónica, WhatsApp) demuestran arquitectura por servicios independientes que el sistema Django consume por HTTP.
