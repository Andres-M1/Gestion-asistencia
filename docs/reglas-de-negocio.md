# Reglas de negocio

Reglas que aplica la API, con el lugar del código donde está cada una.

## Índice

1. [Avisos](#1-avisos)
2. [Notificaciones](#2-notificaciones)
3. [Zona horaria](#3-zona-horaria)
4. [Usuarios y acceso](#4-usuarios-y-acceso)
5. [Datos de la institución](#5-datos-de-la-institución)

---

## 1. Avisos

Código: `app/services/ausencias.py`.

### 1.1 Qué es una clase

Una **clase** es una cátedra en una fecha concreta. No se guarda en ninguna tabla: se calcula con los datos de la cátedra.

- La cátedra se dicta un día de la semana (`dia_semana`: 1 = lunes … 7 = domingo) de `hora_inicio` a `hora_fin`.
- Una fecha es clase de una cátedra si `fecha.isoweekday() == dia_semana`.
- El inicio de la clase es `fecha + hora_inicio` en hora de Argentina.
- No se consideran feriados ni días sin clase.

### 1.2 Constantes

| Constante | Valor | Uso |
|-----------|-------|-----|
| `ANTICIPACION_MINIMA` | 1 hora | Mínimo que tiene que faltar para el inicio de la clase. |
| `VENTANA` | 7 días | Máximo que puede faltar para el inicio de la clase. |
| `ZONA` | `America/Argentina/Buenos_Aires` | Zona de todas las comparaciones. |

### 1.3 Clases disponibles (lista para el docente)

`GET /docente/clases-disponibles` devuelve una clase si se cumplen **todas** estas condiciones:

1. la cátedra es del docente logueado;
2. la fecha cae en el `dia_semana` de la cátedra;
3. `ahora + 1 hora ≤ inicio ≤ ahora + 7 días`, con los dos extremos incluidos;
4. no existe un aviso para esa cátedra y fecha.

La lista se ordena por fecha y hora de inicio.

### 1.4 Registrar un aviso

`POST /docente/avisos` recibe `{catedra_id, fecha}` y **vuelve a validar todo** en el servidor, sin suponer que el cliente mandó una opción de la lista. Las validaciones van en este orden y se corta en la primera que falla:

| # | Regla | Si no se cumple |
|---|-------|-----------------|
| 1 | La cátedra existe y es del docente | `404` Cátedra no encontrada |
| 2 | `fecha` cae en el `dia_semana` de la cátedra | `422` |
| 3 | `inicio ≥ ahora + 1 hora` (esto también rechaza las clases pasadas) | `422` |
| 4 | `inicio ≤ ahora + 7 días` | `422` |
| 5 | No hay otro aviso para esa cátedra y fecha (restricción `uq_ausencia_catedra_fecha`) | `409` |

La regla 5 no se consulta antes de insertar: la garantiza la base de datos, y el `IntegrityError` se traduce a `409`.

Datos del aviso guardado:

- **Sin motivo**: la tabla `ausencia` no tiene esa columna.
- `docente_id` = el docente logueado que dio el aviso.
- `estado = activo`: es el único valor del enum `EstadoAusencia`.
- `creado_en` = momento del registro, en UTC.

### 1.5 Un aviso no se modifica

No hay endpoints para cancelar, editar ni borrar avisos (HU-04 descartada). La respuesta de los avisos no incluye `estado`, porque siempre es `activo`.

### 1.6 Quién ve cada aviso

| Quién | Endpoint | Qué avisos | Orden |
|-------|----------|------------|-------|
| Docente | `GET /docente/avisos` | Los que dio él (`ausencia.docente_id`), pasados y futuros. | Más nuevo primero: fecha ↓, hora de inicio ↓, id ↓ |
| Alumno | `GET /alumno/avisos` | Los de las cátedras donde tiene inscripción **vigente**, con `fecha ≥ hoy` (Argentina). El de hoy aparece aunque la clase ya haya terminado. | Más próximo primero: fecha ↑, hora de inicio ↑, id ↑ |
| Admin | `GET /admin/avisos` | Todos, pasados y futuros, con filtros combinables. | Más nuevo primero: fecha ↓, hora de inicio ↓, id ↓ |

El orden siempre termina en `id`, así es determinístico y la paginación con `offset`/`limit` no repite ni saltea avisos.

**El aviso queda a nombre del docente que lo dio.** `ausencia.docente_id` se guarda al registrar el aviso y no cambia. Si el admin reasigna la cátedra a otro docente (`PATCH /catedras/{id}` con `docente_id`):

- los avisos anteriores siguen en el historial del docente que los dio, y el docente nuevo no los ve;
- el campo `docente` de `AvisoDetalle` muestra a quien dio el aviso, no al docente actual de la cátedra;
- el filtro `docente_id` del admin también usa el docente del aviso;
- los avisos que dé el docente nuevo desde ese momento quedan a su nombre.

Lo que sigue buscándose **por cátedra**:

- los avisos del alumno (HU-05), según sus inscripciones vigentes;
- los destinatarios de las notificaciones (HU-06);
- las clases disponibles y la validación del `POST`, que usan el docente **actual** de la cátedra: solo él puede dar avisos nuevos.

### 1.7 Filtros del admin (HU-09)

- `carrera_id`: la carrera de la materia de la cátedra.
- `materia_id`: la de la cátedra.
- `docente_id`: el docente que dio el aviso (`ausencia.docente_id`), no el docente actual de la cátedra.
- `comision`: igualdad exacta sin distinguir mayúsculas (`lower(comision) = lower(valor)`). No es una búsqueda parcial.
- `fecha_desde` y `fecha_hasta`: inclusive. Si `fecha_desde > fecha_hasta`, `422`.
- Los filtros se combinan con AND. Los ids inexistentes devuelven `[]`, no `404`.

---

## 2. Notificaciones

Código: `app/services/notificaciones.py`, `app/core/correo.py`, `app/core/push.py`.

### 2.1 Cuándo

Solo cuando se registra un aviso (`POST /docente/avisos` con respuesta `201`). No hay otras notificaciones: no hay recordatorios ni avisos de cambios.

### 2.2 Destinatarios

| Destinatario | Correo | Push | Condiciones |
|--------------|:------:|:----:|-------------|
| Alumno | ✅ al email de su perfil (`alumno.email`) | ✅ si tiene `fcm_token` | Inscripción **vigente** en la cátedra del aviso y usuario **activo**. |
| Preceptor (`admin`) | ✅ al `usuario.email` | ❌ | Usuario **activo** con `email` cargado. Todos los admins, sin filtrar por carrera. |
| Docente que avisa | ❌ | ❌ | No se le notifica. |

Los emails y los tokens repetidos se envían una sola vez.

### 2.3 Contenido

Ejemplo para una clase de Programación I, comisión 1K1, del lunes 02/11/2026 de 18:00 a 20:00, docente Laura Gómez:

**Correo** (texto plano)

```
Asunto: Aviso de ausencia: Programación I 1K1 - lunes 02/11/2026

El docente Laura Gómez no dará la clase de:

Materia:  Programación I
Comisión: 1K1
Fecha:    lunes 02/11/2026
Horario:  18:00 a 20:00
```

**Push**

- Título: `Clase suspendida: Programación I 1K1`
- Cuerpo: `lunes 02/11/2026, 18:00 a 20:00. Docente: Laura Gómez`

### 2.4 Cómo se envía

1. Durante el request se arman los destinatarios y los textos. Se hace ahí porque FastAPI cierra la sesión de la base antes de correr los `BackgroundTasks`.
2. Se agrega **una sola** tarea a `BackgroundTasks` y la API responde `201` sin esperar el envío.
3. **Correo**:
   - una conexión SMTP con STARTTLS (login si hay `SMTP_USER`) y timeout de 15 segundos;
   - **un mensaje por destinatario**, con el destinatario en "Para": nadie ve los emails de los demás;
   - remitente: `SMTP_FROM` o, si está vacío, `SMTP_USER`.
4. **Push**:
   - Firebase Cloud Messaging, `send_each_for_multicast`;
   - tandas de hasta **500** tokens (`TANDA`).
5. Sin colas, sin reintentos y sin historial de envíos en la base: solo queda el log.

### 2.5 Fallos

El aviso **queda creado siempre**. Ninguna falla de notificación cambia la respuesta `201`.

| Falla | Qué pasa |
|-------|----------|
| Error al armar los destinatarios | Se registra en el log; no se envía nada. |
| Falla un correo | Se registra y se sigue con el siguiente destinatario. |
| Falla la conexión SMTP | Se registra; no se envían correos, pero sí los push. |
| No se puede iniciar Firebase (credenciales inválidas o inexistentes) | Se registra; no se envían push. |
| Falla una tanda de push | Se registra y se sigue con la siguiente tanda. |
| FCM responde `UNREGISTERED` o `SENDER_ID_MISMATCH` para un token | Ese token queda en `null` en `usuario.fcm_token`. |
| FCM responde otro error para un token (ej. `INVALID_ARGUMENT`) | Warning en el log. El token **no** se borra, porque ese error puede venir de un mensaje mal armado y borraría los tokens de todos. |

### 2.6 Configuración faltante

- Sin `SMTP_HOST`, o sin `SMTP_USER`/`SMTP_FROM`, no se envían correos.
- Sin `FIREBASE_CREDENTIALS`, no se envían push.

En los dos casos la app arranca igual, deja un warning en el log al iniciar y saltea ese tipo de envío en cada aviso.

### 2.7 Token FCM (un celular por usuario)

- Se guarda en `usuario.fcm_token`. No hay tabla de dispositivos.
- `PUT /auth/me/fcm-token` (rol `docente` o `estudiante`) guarda el token. Si otro usuario tenía ese mismo token (alguien cerró sesión y entró otra persona en el mismo celular), se le quita para que no reciba push ajenos.
- `DELETE /auth/me/fcm-token` lo borra (al cerrar sesión).
- El admin no registra celular (`403`): los preceptores no tienen push.

---

## 3. Zona horaria

- Todas las reglas de avisos usan `America/Argentina/Buenos_Aires` (`zoneinfo`), **nunca** la hora del servidor (el contenedor corre en UTC).
- "Ahora" sale de `ausencias.ahora()`, que devuelve `datetime.now(ZONA)`. Los tests la reemplazan para fijar la hora.
- El inicio de una clase es `datetime.combine(fecha, hora_inicio, tzinfo=ZONA)`.
- `hora_inicio` y `hora_fin` se guardan como `time` sin zona y se interpretan como hora de Argentina.
- "Hoy", para los avisos del alumno, es la fecha actual en Argentina.
- `creado_en` se guarda como `timestamptz` en UTC y se devuelve en ISO 8601 con `Z`.
- Las fechas de los filtros del admin (`fecha_desde`, `fecha_hasta`) se comparan contra `ausencia.fecha`, que es la fecha de la clase, no la de creación del aviso.

---

## 4. Usuarios y acceso

Código: `app/services/auth.py`, `app/services/personas.py`, `app/api/deps.py`, `app/core/security.py`.

### 4.1 Login

- Login con **DNI** y contraseña. Las contraseñas se guardan hasheadas con Argon2 (`pwdlib`).
- El login falla con el mismo mensaje (`401` `"DNI o contraseña incorrectos"`) si el DNI no existe, si la contraseña es incorrecta o si el usuario está inactivo.
- Si el DNI no existe, igual se verifica la contraseña contra un hash ficticio, para que el tiempo de respuesta no revele qué DNIs existen.
- El token es un JWT HS256 firmado con `SECRET_KEY`, con `sub` (id del usuario), `rol` y `exp`. Dura `ACCESS_TOKEN_EXPIRE_MINUTES` (480 por defecto).

### 4.2 En cada request

- Se decodifica el token y se busca el usuario.
- Si no existe o está inactivo, `401`: desactivar a alguien invalida sus tokens al instante.
- Cada endpoint exige un rol con `requiere_rol(...)`. Si el rol no coincide, `403`.
- Los endpoints de docente y alumno además exigen el perfil correspondiente. Si falta, `403`.

### 4.3 Roles y perfiles

| Rol | Perfil | Cliente | Cómo se crea |
|-----|--------|---------|--------------|
| `admin` (preceptor) | Ninguno. El email opcional está en `usuario.email`. | Web | Script `python -m app.scripts.crear_admin --dni ... [--email ...]`. La contraseña se pide por teclado (mínimo 8 caracteres). |
| `docente` | `docente` (1 a 1 con `usuario`) | App Android | `POST /docentes/` (admin) |
| `estudiante` | `alumno` (1 a 1 con `usuario`) | App Android | `POST /alumnos/` (admin) |

### 4.4 Alta y baja de personas

- El alta crea `usuario` y perfil en **una sola transacción**: o se crean los dos, o ninguno.
- DNI: solo dígitos, entre 6 y 10. Único entre todos los usuarios.
- Contraseña: mínimo 8 caracteres. El admin puede asignar una nueva con `PATCH`; el usuario no puede cambiarla él mismo.
- Email: válido y único entre los docentes y entre los alumnos.
- El DNI no se puede cambiar.
- **No se borran personas**: se desactivan con `activo: false`. Un usuario inactivo no puede loguearse y no recibe notificaciones. Se conserva el historial de avisos.

---

## 5. Datos de la institución

| Regla | Dónde |
|-------|-------|
| Una cátedra por materia y comisión. | `uq_catedra_materia_comision` |
| `dia_semana` entre 1 y 7; `hora_fin > hora_inicio`. | Schema de alta y `CHECK` en la base. |
| Una inscripción por alumno y cátedra. | `uq_inscripcion_alumno_catedra` |
| La baja de una inscripción se hace con `vigente = false`: el alumno deja de ver la cátedra y sus avisos, y deja de recibir notificaciones. | `PATCH /inscripciones/{id}` |
| Nombre de carrera único. | `uq_carrera_nombre` |
| No se puede borrar un registro que tiene datos asociados (las FK no tienen `ON DELETE`). | `409` |
