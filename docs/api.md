# API: contrato para la app Android y la web

Contrato de la API de **Gestion Asist** para los dos clientes:

- **App Android**: docentes y alumnos.
- **Frontend web**: administrador / preceptor.

La documentación interactiva, generada por FastAPI, está en `/docs` (Swagger) y `/redoc`.

## Índice

- [Generalidades](#generalidades)
- [Común a todos los clientes](#común-a-todos-los-clientes)
- [App Android: docente](#app-android-docente)
- [App Android: alumno](#app-android-alumno)
- [App Android: docente y alumno (celular para push)](#app-android-docente-y-alumno-celular-para-push)
- [Web: administrador / preceptor](#web-administrador--preceptor)
- [Mensajes de restricciones de la base](#mensajes-de-restricciones-de-la-base)
- [Endpoints auxiliares](#endpoints-auxiliares)

---

## Generalidades

| Tema | Regla |
|------|-------|
| **URL base** | `http://<host>:8000/api/v1`. Todas las rutas de este documento son relativas a esa base. |
| **Formato** | JSON en request y response (`Content-Type: application/json`). |
| **Autenticación** | `Authorization: Bearer <access_token>`, obtenido con `POST /auth/login`. Todos los endpoints la piden, salvo `/auth/login` y `/health`. |
| **Vencimiento del token** | `ACCESS_TOKEN_EXPIRE_MINUTES` (480 minutos por defecto). Cuando vence, la API responde `401` y hay que volver a hacer login. No hay refresh token. |
| **Roles** | `docente` y `estudiante` usan la app; `admin` usa la web. Si un rol llama a un endpoint de otro rol, recibe `403`. |
| **Fechas** | `date`: `"AAAA-MM-DD"`. `time`: `"HH:MM:SS"` (al enviar también vale `"HH:MM"`). `creado_en`: ISO 8601 en UTC, ej. `"2026-10-27T01:57:50.103609Z"`. |
| **Hora de las clases** | `hora_inicio` y `hora_fin` son hora de Argentina (`America/Argentina/Buenos_Aires`). |
| **`dia_semana`** | Entero: `1` = lunes … `7` = domingo. |
| **Paginación** | En los listados: `offset` (por defecto `0`) y `limit` (por defecto `100`, máximo `100`; si es mayor, `422`). |
| **Barra final** | Las rutas de colección del admin terminan en `/` (ej. `POST /docentes/`). |
| **CORS** | Los orígenes permitidos para la web se configuran en `CORS_ORIGINS`. |

### Formato de los errores

Los errores de negocio traen un mensaje en `detail`:

```json
{ "detail": "Cátedra no encontrada" }
```

Los errores de validación (`422` de FastAPI/Pydantic) traen una lista con el campo afectado en `loc`:

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["query", "limit"],
      "msg": "Input should be less than or equal to 100",
      "input": "101",
      "ctx": { "le": 100 }
    }
  ]
}
```

Así que `detail` es un **string** en los errores de negocio y una **lista** en los de validación. Los clientes tienen que manejar los dos casos.

### Errores comunes

Valen para todos los endpoints con autenticación y no se repiten en cada uno.

| Código | Cuándo | `detail` |
|--------|--------|----------|
| `401` | Falta el header `Authorization` | `"Not authenticated"` |
| `401` | Token inválido o vencido, o usuario inexistente o desactivado | `"Token inválido o expirado"` |
| `403` | El rol no corresponde al endpoint | `"No tenés permiso para esta acción"` |
| `422` | Body, parámetros de ruta o query inválidos | lista de errores (ver arriba) |

Las respuestas `401` incluyen el header `WWW-Authenticate: Bearer`.

---

## Común a todos los clientes

### `POST /auth/login`

Login con DNI y contraseña (HU-01). No requiere token.

**Request**

```json
{ "dni": "22222222", "password": "prueba123" }
```

**Response `200`**

```json
{ "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "token_type": "bearer" }
```

El token es un JWT HS256 con `sub` (id del usuario, como string), `rol` y `exp`.

**Errores**

| Código | `detail` |
|--------|----------|
| `401` | `"DNI o contraseña incorrectos"`: DNI inexistente, contraseña incorrecta o usuario desactivado; es el mismo mensaje en los tres casos. |
| `422` | Falta `dni` o `password`. |

### `GET /auth/me`

Datos del usuario logueado. Roles: todos.

**Response `200` (docente o alumno)**

```json
{
  "id": 821,
  "dni": "22222222",
  "rol": "docente",
  "perfil": { "id": 328, "nombre": "Laura", "apellido": "Gómez", "email": "laura.gomez@example.com" }
}
```

- `rol` puede ser `"admin"`, `"docente"` o `"estudiante"`.
- `id` es el id del **usuario**; `perfil.id` es el id del docente o del alumno.
- Para el admin, `"perfil": null`.

---

## App Android: docente

Rol requerido: `docente`. Si el usuario no tiene perfil de docente, responde `403` `"El usuario no tiene perfil de docente"`.

### `GET /docente/clases-disponibles`

Clases del docente sobre las que todavía puede avisar (HU-02). La lista incluye las clases que empiezan entre ahora + 1 hora y ahora + 7 días (hora de Argentina) y que no tienen aviso. Viene ordenada por fecha y hora de inicio, y no se pagina.

**Response `200`**

```json
[
  {
    "catedra_id": 488,
    "fecha": "2026-11-02",
    "materia": "Programación I",
    "comision": "1K1",
    "dia_semana": 1,
    "hora_inicio": "18:00:00",
    "hora_fin": "20:00:00"
  },
  {
    "catedra_id": 490,
    "fecha": "2026-11-04",
    "materia": "Base de Datos",
    "comision": "1K1",
    "dia_semana": 3,
    "hora_inicio": "18:00:00",
    "hora_fin": "20:00:00"
  }
]
```

Si no hay clases disponibles, devuelve `[]`.

### `POST /docente/avisos`

Registra el aviso de que el docente no dará una clase (HU-02) y programa las notificaciones (HU-06). Se envían `catedra_id` y `fecha` de una opción de `clases-disponibles`. El servidor vuelve a validar todo.

**Request**

```json
{ "catedra_id": 488, "fecha": "2026-11-02" }
```

**Response `201`**: `AvisoDetalle`

```json
{
  "id": 3743,
  "fecha": "2026-11-02",
  "materia": "Programación I",
  "comision": "1K1",
  "dia_semana": 1,
  "hora_inicio": "18:00:00",
  "hora_fin": "20:00:00",
  "docente": { "nombre": "Laura", "apellido": "Gómez" },
  "creado_en": "2026-10-30T13:05:12.481920Z"
}
```

La respuesta no espera a que salgan los correos y los push: se envían en segundo plano y, si fallan, el aviso queda creado igual.

**Errores**

| Código | `detail` | Cuándo |
|--------|----------|--------|
| `404` | `"Cátedra no encontrada"` | La cátedra no existe o es de otro docente. |
| `422` | `"La fecha no corresponde al día de cursada de la cátedra"` | `fecha` no cae en el `dia_semana` de la cátedra. |
| `422` | `"Solo se puede avisar hasta 1 hora antes del inicio de la clase"` | Falta menos de 1 hora para el inicio, o la clase ya pasó. |
| `422` | `"Solo se puede avisar sobre clases de los próximos 7 días"` | La clase empieza dentro de más de 7 días. |
| `409` | `"Ya hay un aviso para esa cátedra en esa fecha"` | Ya existe un aviso para esa clase. |

### `GET /docente/avisos`

Historial de avisos del docente (HU-03): pasados y futuros, del más nuevo al más viejo (fecha, hora de inicio e `id`, descendentes).

**Query:** `offset`, `limit` (≤ 100).

**Response `200`**: lista de `AvisoDetalle`

```json
[
  {
    "id": 3743,
    "fecha": "2026-10-29",
    "materia": "Análisis de Sistemas I",
    "comision": "2K1",
    "dia_semana": 4,
    "hora_inicio": "14:00:00",
    "hora_fin": "16:00:00",
    "docente": { "nombre": "Laura", "apellido": "Gómez" },
    "creado_en": "2026-10-27T01:57:50.103609Z"
  }
]
```

---

## App Android: alumno

Rol requerido: `estudiante`. Si el usuario no tiene perfil de alumno, responde `403` `"El usuario no tiene perfil de alumno"`.

### `GET /alumno/inscripciones`

Inscripciones **vigentes** del alumno (HU-07), en el orden de la semana (día, hora de inicio e id de la cátedra). No se pagina.

**Response `200`**: lista de `MiInscripcion`

```json
[
  {
    "catedra_id": 488,
    "materia": "Programación I",
    "comision": "1K1",
    "dia_semana": 1,
    "hora_inicio": "18:00:00",
    "hora_fin": "20:00:00",
    "docente": { "nombre": "Laura", "apellido": "Gómez" }
  },
  {
    "catedra_id": 490,
    "materia": "Base de Datos",
    "comision": "1K1",
    "dia_semana": 3,
    "hora_inicio": "18:00:00",
    "hora_fin": "20:00:00",
    "docente": { "nombre": "Laura", "apellido": "Gómez" }
  }
]
```

### `GET /alumno/avisos`

Avisos **de hoy en adelante** (hora de Argentina) de las cátedras donde el alumno tiene inscripción vigente (HU-05). Vienen del más próximo al más lejano (fecha, hora de inicio e `id`, ascendentes). El aviso de hoy aparece aunque la clase ya haya terminado.

**Query**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `catedra_id` | int, opcional | Solo los avisos de esa cátedra (HU-07: "ver los avisos de una inscripción"). |
| `offset`, `limit` | int | Paginación (`limit` ≤ 100). |

**Response `200`**: lista de `AvisoDetalle`, con el mismo formato que en [`GET /docente/avisos`](#get-docenteavisos).

**Errores**

| Código | `detail` | Cuándo |
|--------|----------|--------|
| `404` | `"No tenés una inscripción vigente en esa cátedra"` | `catedra_id` de una cátedra donde no tiene inscripción vigente, o que no existe. |

---

## App Android: docente y alumno (celular para push)

Roles: `docente` y `estudiante`. Si los llama un `admin`, responde `403`.

### `PUT /auth/me/fcm-token`

Guarda el token de Firebase Cloud Messaging del celular (HU-06). Se llama después del login y en `onNewToken`. Hay un solo celular por usuario: el token nuevo reemplaza al anterior. Si otro usuario tenía el mismo token, se le quita.

**Request**

```json
{ "token": "dXNlci1mY20tdG9rZW4tZGUtZWplbXBsbw..." }
```

**Response `204`**, sin cuerpo.

**Errores:** `422` si `token` está vacío o tiene más de 4096 caracteres.

### `DELETE /auth/me/fcm-token`

Borra el token del usuario. Se llama al cerrar sesión.

**Response `204`**, sin cuerpo.

> Hoy solo los **alumnos** reciben push (cuando se registra un aviso de una cátedra donde están inscriptos). El docente puede registrar su token, pero ningún envío lo usa todavía.

---

## Web: administrador / preceptor

Rol requerido: `admin` en todos los endpoints de esta sección.

### `GET /admin/avisos`

Todos los avisos, pasados y futuros, del más nuevo al más viejo (HU-09). Los filtros se combinan entre sí (AND).

**Query**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `carrera_id` | int | Carrera de la materia de la cátedra. |
| `materia_id` | int | |
| `comision` | string | Texto exacto, sin distinguir mayúsculas (`1k1` = `1K1`). No busca coincidencias parciales. |
| `docente_id` | int | Id del **docente**, no del usuario. |
| `fecha_desde` | date | Inclusive. |
| `fecha_hasta` | date | Inclusive. |
| `offset`, `limit` | int | Paginación (`limit` ≤ 100). |

**Ejemplo:** `GET /admin/avisos?carrera_id=1&fecha_desde=2026-11-01&fecha_hasta=2026-11-30`

**Response `200`**: lista de `AvisoDetalle`, con el mismo formato que en [`GET /docente/avisos`](#get-docenteavisos). Si ningún aviso cumple los filtros, o los ids no existen, devuelve `[]`.

**Errores**

| Código | `detail` |
|--------|----------|
| `422` | `"fecha_desde no puede ser posterior a fecha_hasta"` |

### Docentes (HU-08): `/docentes/`

| Método y ruta | Descripción | Respuesta |
|---------------|-------------|-----------|
| `POST /docentes/` | Alta: crea el usuario (rol `docente`) y su perfil. | `201` `DocenteRead` |
| `GET /docentes/` | Listado ordenado por `id`. Query: `offset`, `limit`. | `200` lista de `DocenteRead` |
| `GET /docentes/{docente_id}` | Uno. | `200` `DocenteRead` |
| `PATCH /docentes/{docente_id}` | Edición parcial, nueva contraseña o desactivación. | `200` `DocenteRead` |

No hay `DELETE`: para dar de baja se usa `PATCH` con `{"activo": false}`, y así se conserva el historial de avisos.

**Request `POST`**

```json
{
  "dni": "30123456",
  "password": "clave-segura",
  "nombre": "Ana",
  "apellido": "Martínez",
  "email": "ana.martinez@example.com"
}
```

| Campo | Regla |
|-------|-------|
| `dni` | 6 a 10 dígitos, solo números (sin puntos). |
| `password` | Mínimo 8 caracteres. |
| `nombre`, `apellido` | No vacíos. |
| `email` | Email válido. |

**Request `PATCH`**: todos los campos son opcionales.

```json
{ "nombre": "Ana María", "email": "ana.m@example.com", "password": "otra-clave-segura", "activo": false }
```

El DNI no se puede editar.

**Response** (`DocenteRead`)

```json
{
  "id": 12,
  "dni": "30123456",
  "nombre": "Ana",
  "apellido": "Martínez",
  "email": "ana.martinez@example.com",
  "activo": true
}
```

`id` es el id del **docente**: es el que se usa en `docente_id` de cátedras y filtros.

**Errores**

| Código | `detail` |
|--------|----------|
| `409` | `"Ya existe un usuario con ese DNI"` |
| `409` | `"Ya existe un docente con ese email"` |
| `404` | `"Docente no encontrado"` |

### Alumnos (HU-08): `/alumnos/`

Igual que docentes, con el campo `carrera_id`.

| Método y ruta | Descripción | Respuesta |
|---------------|-------------|-----------|
| `POST /alumnos/` | Alta: crea el usuario (rol `estudiante`) y su perfil. | `201` `AlumnoRead` |
| `GET /alumnos/` | Listado ordenado por `id`. Query: `carrera_id`, `offset`, `limit`. | `200` lista de `AlumnoRead` |
| `GET /alumnos/{alumno_id}` | Uno. | `200` `AlumnoRead` |
| `PATCH /alumnos/{alumno_id}` | Edición parcial (incluye `carrera_id`), nueva contraseña o desactivación. | `200` `AlumnoRead` |

No hay `DELETE`: para dar de baja se usa `PATCH` con `{"activo": false}`.

**Request `POST`**

```json
{
  "dni": "40123456",
  "password": "clave-segura",
  "nombre": "Sofía",
  "apellido": "Díaz",
  "email": "sofia.diaz@example.com",
  "carrera_id": 1
}
```

**Response** (`AlumnoRead`)

```json
{
  "id": 7,
  "dni": "40123456",
  "nombre": "Sofía",
  "apellido": "Díaz",
  "email": "sofia.diaz@example.com",
  "activo": true,
  "carrera_id": 1
}
```

**Errores**

| Código | `detail` |
|--------|----------|
| `409` | `"Ya existe un usuario con ese DNI"` |
| `409` | `"Ya existe un alumno con ese email"` |
| `422` | `"La carrera indicada no existe"` |
| `404` | `"Alumno no encontrado"` |

### Cátedras (HU-10): `/catedras/`

Crear una cátedra es asignar un docente a una materia, con comisión, día y horario.

| Método y ruta | Descripción | Respuesta |
|---------------|-------------|-----------|
| `POST /catedras/` | Alta. | `201` `CatedraRead` |
| `GET /catedras/` | Listado ordenado por `id`. Query: `materia_id`, `docente_id`, `offset`, `limit`. | `200` lista |
| `GET /catedras/{catedra_id}` | Una. | `200` `CatedraRead` |
| `PATCH /catedras/{catedra_id}` | Edición parcial. Con `docente_id` se reasigna la cátedra a otro docente. | `200` `CatedraRead` |
| `DELETE /catedras/{catedra_id}` | Borra la cátedra, si no tiene inscripciones ni avisos. | `204` |

**Request `POST`**

```json
{
  "materia_id": 3,
  "docente_id": 12,
  "comision": "1K1",
  "dia_semana": 2,
  "hora_inicio": "18:00",
  "hora_fin": "20:00"
}
```

| Campo | Regla |
|-------|-------|
| `comision` | No vacía. |
| `dia_semana` | Entre 1 y 7. |
| `hora_fin` | Posterior a `hora_inicio`. |

**Response** (`CatedraRead`)

```json
{
  "id": 25,
  "materia_id": 3,
  "docente_id": 12,
  "comision": "1K1",
  "dia_semana": 2,
  "hora_inicio": "18:00:00",
  "hora_fin": "20:00:00"
}
```

**Errores**

| Código | `detail` |
|--------|----------|
| `409` | `"Esa materia ya tiene una cátedra con esa comisión"` |
| `422` | `"La materia indicada no existe"` / `"El docente indicado no existe"` |
| `422` | `"hora_fin debe ser posterior a hora_inicio"` (en `PATCH`; en `POST` sale como error de validación) |
| `409` | `"No se puede borrar: tiene registros asociados"` (`DELETE`) |
| `404` | `"Cátedra no encontrada"` |

### Carreras: `/carreras/`

| Método y ruta | Body | Respuesta |
|---------------|------|-----------|
| `POST /carreras/` | `{"nombre": "Desarrollo de Software"}` | `201` `{"id": 1, "nombre": "Desarrollo de Software"}` |
| `GET /carreras/` | Query: `offset`, `limit`. | `200` lista |
| `GET /carreras/{carrera_id}` | — | `200` |
| `PATCH /carreras/{carrera_id}` | `{"nombre": "..."}` | `200` |
| `DELETE /carreras/{carrera_id}` | — | `204` |

**Errores**

| Código | `detail` |
|--------|----------|
| `409` | `"Ya existe una carrera con ese nombre"` |
| `409` | `"No se puede borrar: tiene registros asociados"` (tiene materias o alumnos) |
| `404` | `"Carrera no encontrada"` |

### Materias: `/materias/`

| Método y ruta | Body | Respuesta |
|---------------|------|-----------|
| `POST /materias/` | `{"carrera_id": 1, "nombre": "Programación I"}` | `201` `{"id": 3, "carrera_id": 1, "nombre": "Programación I"}` |
| `GET /materias/` | Query: `carrera_id`, `offset`, `limit`. | `200` lista |
| `GET /materias/{materia_id}` | — | `200` |
| `PATCH /materias/{materia_id}` | `{"carrera_id": ..., "nombre": ...}` (opcionales) | `200` |
| `DELETE /materias/{materia_id}` | — | `204` |

**Errores**

| Código | `detail` |
|--------|----------|
| `422` | `"La carrera indicada no existe"` |
| `409` | `"No se puede borrar: tiene registros asociados"` (tiene cátedras) |
| `404` | `"Materia no encontrada"` |

### Inscripciones: `/inscripciones/`

| Método y ruta | Body | Respuesta |
|---------------|------|-----------|
| `POST /inscripciones/` | `{"alumno_id": 7, "catedra_id": 25}` | `201` `{"id": 40, "alumno_id": 7, "catedra_id": 25, "vigente": true}` |
| `GET /inscripciones/` | Query: `alumno_id`, `catedra_id`, `vigente`, `offset`, `limit`. | `200` lista |
| `GET /inscripciones/{inscripcion_id}` | — | `200` |
| `PATCH /inscripciones/{inscripcion_id}` | `{"vigente": false}` (obligatorio) | `200` |
| `DELETE /inscripciones/{inscripcion_id}` | — | `204` |

Para dar de baja una inscripción sin perder el registro, se usa `PATCH` con `{"vigente": false}`. El alumno deja de ver esa cátedra y sus avisos, y deja de recibir notificaciones.

**Errores**

| Código | `detail` |
|--------|----------|
| `409` | `"El alumno ya está inscripto en esa cátedra"` |
| `422` | `"El alumno indicado no existe"` / `"La cátedra indicada no existe"` |
| `404` | `"Inscripción no encontrada"` |

---

## Mensajes de restricciones de la base

Cuando un `POST` o `PATCH` viola una restricción de PostgreSQL, la API devuelve el mensaje de `MENSAJES` (`app/api/errores.py`):

- violación de unicidad → `409`;
- clave foránea inexistente o `CHECK` → `422`;
- `DELETE` de un registro con datos asociados → `409` `"No se puede borrar: tiene registros asociados"`.

| Restricción | Código | `detail` |
|-------------|--------|----------|
| `uq_carrera_nombre` | 409 | Ya existe una carrera con ese nombre |
| `ix_usuario_dni` | 409 | Ya existe un usuario con ese DNI |
| `uq_docente_email` | 409 | Ya existe un docente con ese email |
| `uq_alumno_email` | 409 | Ya existe un alumno con ese email |
| `uq_catedra_materia_comision` | 409 | Esa materia ya tiene una cátedra con esa comisión |
| `uq_inscripcion_alumno_catedra` | 409 | El alumno ya está inscripto en esa cátedra |
| `uq_ausencia_catedra_fecha` | 409 | Ya hay un aviso para esa cátedra en esa fecha |
| `ck_catedra_dia_semana` | 422 | dia_semana debe estar entre 1 (lunes) y 7 (domingo) |
| `ck_catedra_horario` | 422 | hora_fin debe ser posterior a hora_inicio |
| `fk_materia_carrera_id_carrera` | 422 | La carrera indicada no existe |
| `fk_alumno_carrera_id_carrera` | 422 | La carrera indicada no existe |
| `fk_catedra_materia_id_materia` | 422 | La materia indicada no existe |
| `fk_catedra_docente_id_docente` | 422 | El docente indicado no existe |
| `fk_inscripcion_alumno_id_alumno` | 422 | El alumno indicado no existe |
| `fk_inscripcion_catedra_id_catedra` | 422 | La cátedra indicada no existe |
| `fk_ausencia_catedra_id_catedra` | 422 | La cátedra indicada no existe |

Otra restricción sin mensaje propio responde `"Los datos violan una restricción de la base"`.

---

## Endpoints auxiliares

No son parte de ninguna HU ni del contrato con los clientes:

- **`GET /health`**: sin autenticación. Verifica que la API y la base respondan: `{"status": "ok", "database": "ok"}`.
- **`POST /auth/token`**: login en formato OAuth2 (form con `username` = DNI y `password`), para el botón **Authorize** de `/docs`. No aparece en el esquema OpenAPI. Los clientes usan `POST /auth/login`.
