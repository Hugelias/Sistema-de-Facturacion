# Sistema de Ventas y Facturación — TecnoStock S.A.

Sistema web de gestión de ventas, facturación, compras e inventario desarrollado con Django 6 para la empresa TecnoStock S.A.

---

## Tecnologías

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.14, Django 6.0.6 |
| Base de datos | SQLite (desarrollo) |
| Frontend | Bootstrap 5.3, Bootstrap Icons 1.11.3, Chart.js 4.x |
| Fuente tipográfica | Inter (Google Fonts) |

---

## Estructura del proyecto

```
Sistema de Ventas y Facturación/
├── config/          # Configuración del proyecto (settings, URLs raíz)
├── billing/         # Módulo principal: ventas, facturación, catálogo y clientes
├── purchasing/      # Módulo de compras a proveedores
├── cobros/          # Cobro de facturas de venta a crédito (cuentas por cobrar)
├── pagos/           # Pago de compras a crédito a proveedores (cuentas por pagar)
├── shared/          # Utilidades reutilizables (mixins, decoradores, validadores)
├── templates/       # Plantillas globales (base, auth, admin)
└── manage.py
```

---

## Módulos

### `billing` — Ventas y Facturación

Módulo central del sistema. Gestiona el catálogo de productos, clientes y el proceso de facturación.

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
| `/accounts/signup/` | Solicitud de acceso (crea la cuenta inactiva, pendiente de aprobación) |
| `/security/users/` | Listado de usuarios con KPIs, filtros por nombre, grupo y estado |
| `/security/users/create/` | Nuevo usuario con asignación de grupo |
| `/security/users/<id>/edit/` | Editar usuario (datos, grupo, nueva contraseña opcional) |
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
| `UserCreateForm` | `User` | Crea usuario con grupo y contraseña |
| `UserEditForm` | `User` | Edita usuario; grupo y nueva contraseña opcionales |

`ActiveSelect` es un widget `Select` personalizado con opciones `[('True', 'Activo'), ('False', 'Inactivo')]`, compatible con `BooleanField` de Django.

`InvoiceDetailFormSet` se construye con `inlineformset_factory(Invoice, InvoiceDetail, formset=BaseInvoiceDetailFormSet, ...)`. `BaseInvoiceDetailFormSet.clean()` rechaza la factura si el mismo producto aparece en más de una línea no eliminada (reforzado también en el navegador, marcando el `<select>` duplicado en rojo).

La validación del límite de crédito (`_check_credit_limit`, en `billing/views.py`) corre en `invoice_create`/`invoice_update` **antes** de guardar nada: calcula el total propuesto a partir del formset, lo suma a la deuda pendiente del cliente y lo compara contra `Customer.get_credit_limit()` — ver regla en la sección de `Customer` más abajo.

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

Módulo de seguridad basado en el sistema de `auth` de Django (grupos + permisos), extendido con una pantalla de selección de perfil y aprobación manual de cuentas nuevas.

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

1. **`/accounts/select-role/`** (`registration/role_select.html`) es el punto de entrada real: es tanto `LOGIN_URL` como `LOGOUT_REDIRECT_URL`, así que cualquier intento de acceder a una vista protegida sin sesión (o cualquier logout) cae aquí primero, con el destino original preservado en `?next=`.
2. Cada tarjeta de perfil (Administrador/Gerente/Vendedor/Comprador) enlaza a `/accounts/login/?role=<perfil>`, que solo cambia el badge visual ("Accediendo como...") — **no** es en sí mismo un control de acceso.
3. El control de acceso real ocurre en `RoleAwareAuthenticationForm` (`billing/views.py`), que sobreescribe `confirm_login_allowed()` para rechazar el login con un mensaje específico según el caso:
   - Cuenta inactiva → pendiente de aprobación.
   - Cuenta activa sin ningún grupo asignado.
   - Rol elegido en la tarjeta que no coincide con el grupo real del usuario.
   - Los **superusuarios quedan exentos** de las dos últimas comprobaciones (necesario porque `admin` no pertenece a ningún grupo).
4. `RoleAwareLoginView` (registrada en `accounts/login/` en `config/urls.py`, sobrescribiendo la que trae `django.contrib.auth.urls`) simplemente usa ese form.
5. `AUTHENTICATION_BACKENDS` se cambió a `AllowAllUsersModelBackend`: el backend por defecto de Django rechaza a los usuarios inactivos *antes* de llegar a `confirm_login_allowed` (mensaje genérico de "credenciales incorrectas"), así que hace falta este backend para poder mostrar el mensaje específico de "cuenta inactiva".

### Solicitud de acceso (signup)

`/accounts/signup/` ya no inicia sesión automáticamente: `SignUpForm.save()` crea la cuenta con `is_active = False` y el usuario ve un mensaje de "un administrador debe activarla y asignarte un rol". Un administrador la aprueba desde `/security/users/` (activar + asignar grupo) — flujo elegido porque, dado que el login ahora exige pertenecer a un grupo, una cuenta autoregistrada sin rol no podría hacer nada de todas formas.

### Protección de cuentas de superusuario

Un usuario `is_staff` no-superusuario (p. ej. `administrador`) puede editar/resetear la contraseña de cualquier usuario normal desde `/security/users/<id>/edit/` — es el comportamiento esperado del rol. Pero **no puede tocar una cuenta de superusuario**: `security_user_edit` y `security_user_toggle` rechazan la operación si el objetivo es superusuario y quien la pide no lo es, y `security_user_list.html` oculta los botones de editar/activar-desactivar para esas filas (candado en su lugar).

---

## Funcionalidades destacadas

- **Dashboard interactivo:** KPIs en tiempo real (productos activos, clientes, facturas, compras), gráfico de líneas Ventas vs Compras de los últimos 6 meses, gráfico de dona de distribución por grupo y resumen financiero mensual con variación porcentual respecto al mes anterior.
- **Catálogo de productos:** filtros combinados (nombre, descripción, marca, grupo, proveedor, rango de precio y stock), tabla con badges de grupo, píldoras de estado y botones de acción. Exportación a PDF y Excel con selección de columnas. Paginación inteligente con elipsis.
- **Gestión de clientes:** panel KPI en el listado (total, activos, inactivos, nuevos del mes con % de variación). Filtros por nombre, cédula, email, ciudad, estado y fecha de registro. Formulario con validación de cédula ecuatoriana (algoritmo SRI) en cliente y servidor.
- **Facturación completa:** creación y edición de facturas, subtotal por línea, IVA 15% y total calculados automáticamente al guardar. Vista PDF imprimible con estado de cobro. Anulación lógica (no elimina el registro).
- **Ventas a contado y a crédito:** cada factura define `tipo_pago`; el Consumidor Final (sembrado automáticamente) solo admite contado, bloqueado tanto en el navegador como en el servidor. El límite de crédito se calcula solo según el historial de pago del cliente (ver sección dedicada) y se valida antes de guardar la factura.
- **Cobro de facturas a crédito (`cobros`):** listado de facturas pendientes, registro de abonos, historial de pagos y cálculo automático de saldo/estado — ver módulo `cobros` más arriba.
- **Pago de compras a crédito (`pagos`):** cuentas por pagar a proveedores — listado de compras pendientes, registro de pagos, historial y cálculo automático de saldo/estado, con las mismas reglas de integridad que `cobros` — ver módulo `pagos` más arriba.
- **Validación de productos duplicados:** una factura no puede tener el mismo producto en dos líneas distintas; se valida en el formset del servidor y se resalta en vivo en el formulario.
- **Filtros avanzados en facturas:** por cliente, número de factura, rango de fechas, estado, tipo de pago y rango de total.
- **Compras con formset dinámico:** tabla de productos con filas añadibles/eliminables, cálculo de subtotal por fila e IVA/Total en tiempo real en el navegador. Validación de N° de factura duplicado por proveedor.
- **Control de stock:** las compras incrementan el inventario de productos al registrarse. Las facturas lo decrementan; la edición de facturas reconcilia el delta de stock automáticamente.
- **Exportación PDF / Excel:** disponible en el listado de productos (y extensible a otros módulos vía `ExportMixin`), con selección dinámica de columnas.
- **Auditoría:** cada acción crítica queda registrada en el log con usuario, ruta y tipo de operación.
- **Autenticación con selección de perfil:** pantalla de selección de rol antes del login, mensajes de error específicos (cuenta inactiva / sin rol / rol equivocado), registro como solicitud de acceso pendiente de aprobación, y recuperación de contraseña vía Django `auth` — ver sección "Autenticación y control de acceso".
- **Gestión de seguridad (usuarios y grupos):** listado de usuarios con KPIs (total, activos, inactivos), filtros por nombre, grupo y estado; alta, edición (con cambio opcional de contraseña) y activación/desactivación de usuarios; listado de grupos con conteo de usuarios y permisos. Restringido a personal `staff`, con las cuentas de superusuario protegidas frente a ediciones de otros administradores.
- **Panel de administración integrado:** el index de Django Admin está sobrescrito con el diseño de TecnoStock (sidebar + topbar + tarjetas por aplicación con color temático y acciones recientes).

---

## Diseño de interfaz (UI/UX)

- **Sidebar oscuro** (`#0B1120`, 260 px) colapsable con estado persistido en `localStorage`.
- **Topbar sticky** (blanco, 64 px) con búsqueda global (`Ctrl + /`), chip de usuario y logout.
- **Páginas de auth standalone** — login, signup y flujo completo de recuperación de contraseña (`password_reset_form`, `_done`, `_confirm`, `_complete`) con fondo degradado, formas blobs, logo hexagonal y tarjeta flotante.
- **Formularios de creación/edición** con diseño corporativo: cabecera oscura (`#1E293B`), inputs con caja de icono lateral, borde azul en focus, selector de estado (`Activo / Inactivo`) y asterisco rojo en campos obligatorios.
- **Admin index** sobrescrito con layout completo del sistema (sidebar, topbar, grid de apps con iconos y color por módulo, panel lateral de acciones recientes).
- Bootstrap Icons 1.11.3 y fuente Inter en toda la interfaz.
- Soporte de mensajes flash (Django `messages`) integrado en el layout base.

### Plantillas por módulo

| Sección | Plantillas |
|---------|-----------|
| Global | `base.html` |
| Auth standalone | `role_select.html`, `login.html`, `signup.html`, `password_reset_form.html`, `password_reset_done.html`, `password_reset_confirm.html`, `password_reset_complete.html` |
| Admin | `admin/index.html` (override del admin de Django) |
| Billing | `home.html`, `brand_*.html`, `productgroup_*.html`, `supplier_*.html`, `product_*.html`, `customer_*.html`, `invoice_*.html`, `security_user_list.html`, `security_user_form.html`, `security_group_list.html` |
| Purchasing | `purchase_*.html` |
| Cobros | `factura_pendiente_list.html`, `cobro_historial.html`, `cobro_form.html`, `cobro_confirm_delete.html` |
| Pagos | `compra_pendiente_list.html`, `pago_historial.html`, `pago_form.html`, `pago_confirm_delete.html` |

---

## Instalación y ejecución

### Requisitos previos

- Python 3.14
- Entorno virtual disponible en `venv/`

### Pasos

```powershell
# 1. Activar el entorno virtual
.\venv\Scripts\Activate.ps1

# 2. Instalar dependencias (si es necesario)
pip install -r requirements.txt

# 3. Aplicar migraciones
python manage.py migrate

# 4. Iniciar el servidor de desarrollo
python manage.py runserver
```

Abrir en el navegador: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

### Crear superusuario

```powershell
python manage.py createsuperuser
```

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

## Contexto académico

Proyecto desarrollado para la asignatura de Programación Orientada a Objetos (Tarea 2 — POO). El módulo `cobros` amplía el sistema original a partir del caso de estudio **"Integración de Pagos de Créditos"** (cobro de facturas de venta a crédito), y el módulo `pagos` a partir del caso de estudio **"Pago de Compras a Crédito"** (cuentas por pagar a proveedores) — ambos reutilizan los modelos de `billing` y `purchasing` ya existentes en el sistema. El módulo de seguridad (grupos, permisos, login por perfil) sigue la **"Guía Práctica 4 — Desarrollo del Módulo de Seguridad utilizando el Administrador de Django"**.
