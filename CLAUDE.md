# CLAUDE.md: Gestion Asist

Sistema de **avisos de ausencia docente**: el docente avisa desde la app que no va a dar una clase concreta, y los alumnos inscriptos en esa cátedra reciben **una notificación push en la app Android y un correo**. Los preceptores reciben un **correo**.

## Arquitectura y clientes

- **Este repo = solo la API** (FastAPI). No agregar pantallas acá. Las plantillas Jinja existentes quedan como están (página de inicio).
- **App Android** (Android Studio, aparte): la usan **solo docentes y alumnos**. Recibe push por Firebase Cloud Messaging (FCM).
- **Frontend web** (aparte): lo usa **solo el administrador / preceptor** (rol `admin`). CORS se configura con `CORS_ORIGINS`.

## Glosario

- **Cátedra** = una materia dictada por un docente en una **comisión** ("aula" = comisión), un día de la semana y un horario.
- **Clase** = una ocurrencia concreta de una cátedra en una fecha (ej. "Programación II · 1K1 · martes 03/11 · 18:00-20:00"). No es una tabla: se calcula a partir de `dia_semana`, `hora_inicio` y `hora_fin`.
- **Aviso** = modelo `Ausencia`. Rol `estudiante` = modelo `Alumno`. Rol `admin` = preceptor.

## Alcance cerrado

Implementar **solo** estas historias de usuario. No agregar funcionalidades, roles, tablas, dependencias ni pantallas que no estén acá. Si algo parece imprescindible y no está, **preguntar antes**.

| HU | Rol | Qué | Estado |
|----|-----|-----|--------|
| HU-01 | Todos | Login con DNI y contraseña | ✅ hecho (`/auth/login`, `/auth/me`) |
| HU-02 | Docente | Registrar aviso eligiendo **una clase concreta** de una lista (ver reglas abajo). No elige fecha libre ni escribe motivo. | ✅ hecho (`/docente/clases-disponibles`, `POST /docente/avisos`) |
| HU-03 | Docente | Ver el historial de sus avisos | ✅ hecho (`GET /docente/avisos`) |
| ~~HU-04~~ | — | **Descartada.** Un aviso registrado no se cancela ni se edita. | ❌ |
| HU-05 | Estudiante | Ver avisos solo de cátedras donde tiene inscripción vigente | ✅ hecho (`GET /alumno/avisos`) |
| HU-06 | Estudiante / Preceptor | Al registrarse un aviso: cada alumno con inscripción vigente en esa cátedra recibe **push + correo**; los preceptores reciben **correo** | ⏳ |
| HU-07 | Estudiante | Ver sus inscripciones vigentes (materia, comisión, docente) y desde cada una sus avisos | ✅ hecho (`GET /alumno/inscripciones`; avisos por cátedra con `GET /alumno/avisos?catedra_id=`) |
| HU-08 | Admin | Alta de docentes y estudiantes con DNI y contraseña | ✅ hecho |
| HU-09 | Admin | Listar avisos filtrando por carrera, materia, comisión, docente y fecha | ⏳ |
| HU-10 | Admin | Asignar docentes a materias (= crear/editar cátedras) | ✅ hecho |

Carreras, materias e inscripciones tienen CRUD de admin porque son necesarios para cargar los datos. No ampliarlos.

### Reglas de HU-02

- `GET /api/v1/docente/clases-disponibles` devuelve las próximas clases del docente logueado. Cada opción trae: `catedra_id`, `fecha`, materia, comisión, día y horario.
- Una clase **aparece en la lista** solo si:
  - su cátedra es del docente logueado;
  - faltan **al menos 1 hora** para su `hora_inicio` (hora de Argentina);
  - no tiene ya un aviso.
- **Ventana:** la lista muestra las clases de los **próximos 7 días** (desde ahora hasta 7 días después, hora de Argentina). El `POST` rechaza fechas fuera de esa ventana.
- `POST /api/v1/docente/avisos` recibe `{catedra_id, fecha}` y **vuelve a validar todo lo anterior en el servidor** (no confiar en que el cliente mandó una opción de la lista).
- El aviso no tiene motivo. Quitar la columna `motivo` de `Ausencia` con una migración.
- Un aviso por cátedra y fecha: `uq_ausencia_catedra_fecha` (ya existe).

## Fuera de alcance por ahora (no implementar)

- Cambiar o recuperar contraseña.
- Cancelar o editar avisos (HU-04).
- Motivo del aviso.
- Push en la web (los preceptores reciben solo correo).
- Feriados o días sin clase.

## Stack y convenciones (respetar lo existente)

- FastAPI + SQLModel + PostgreSQL + Alembic, todo en Docker (ver README).
- Capas: `endpoints/` (HTTP) → `services/` (reglas de negocio) → `crud/` (BD) → `models/`. Las reglas de HU-02 (cálculo de clases disponibles y validación) van en `services/ausencias.py`.
- Permisos con `requiere_rol(...)` / `AdminUser` / `DocenteUser` / `EstudianteUser` de `app/api/deps.py`.
- Errores de integridad con `manejar_integridad` y `obtener_o_404` de `app/api/errores.py`. Agregar a `MENSAJES` cualquier restricción nueva.
- Nombres en español.
- **Fechas y horas:** comparar siempre en `America/Argentina/Buenos_Aires` (usar `zoneinfo`), nunca con la hora del servidor (el contenedor está en UTC). La regla de "1 hora antes" combina `fecha` + `hora_inicio` en esa zona.
- **Notificaciones (HU-06):** al crear el aviso, el service arma los destinatarios y lanza **un** `BackgroundTasks` que envía:
  - **Correo** a los alumnos con inscripción vigente y a **todos** los preceptores (todos los usuarios `admin` activos, sin filtrar por carrera). El admin hoy no tiene email: agregar `email: str | None` a `Usuario` (o al alta del admin en `crear_admin.py`) para poder enviarle. Los admins sin email no reciben correo.
  - Envío: `smtplib` de la librería estándar, config SMTP en `.env`. Un mensaje por destinatario, o uno solo con todos en **CCO**. Nunca todos en "Para".
  - **Push** a los alumnos: `firebase-admin` (única dependencia nueva permitida), mensaje multicast en tandas de hasta 500 tokens. Credenciales del service account por ruta en `.env`, el JSON nunca se sube a git.
  - Contenido: materia, comisión, fecha, horario y docente.
  - Si falla un correo o un push, se registra en el log y se sigue con el resto. El aviso queda creado igual.
  - Sin colas, sin Celery, sin tabla de historial de notificaciones.
- **Token FCM (mínimo):** columna `fcm_token: str | None` en `Usuario` + `PUT /api/v1/auth/me/fcm-token` (la app lo llama después del login y en `onNewToken`) y `DELETE` del mismo endpoint al cerrar sesión. Un dispositivo por usuario, sin tabla de dispositivos. Si FCM responde que un token es inválido o no registrado, poner `fcm_token = None`.
- **Tests:** mockear SMTP y FCM, y fijar la hora "actual" en los tests de la regla de 1 hora. Los tests nunca envían correos ni push reales.
- **Secretos:** el JSON del service account de Firebase y `.env` van en `.gitignore`. Verificarlo antes de cada commit que toque configuración.
- Dependencias nuevas: solo si son imprescindibles, con versión fija en `requirements.txt`, y avisando antes.

## Migraciones

- Generar desde la máquina local: `alembic revision --autogenerate -m "..."` y **revisar el archivo**.
- Alembic **no detecta** valores nuevos en un enum de PostgreSQL. Si algún día se agrega uno, hay que escribirlo a mano con `op.execute("ALTER TYPE ... ADD VALUE ...")`.
- Columnas `NOT NULL` nuevas en tablas que pueden tener datos: usar `server_default`.

## Forma de trabajo

1. Una HU por vez. Antes de programar, listar qué archivos se van a tocar.
2. Al terminar cada HU: tests en `tests/` que cubran sus criterios de aceptación, y explicar cómo probarla en `/docs`.
3. Mantener el README al día (estado del proyecto, diagrama ER, tabla de endpoints).
