# Decisiones de diseño

Por qué el sistema es como es. Dos partes:

- **Decisiones funcionales**: las definió el cliente o el equipo.
- **Decisiones técnicas**: se tomaron al implementar. Cuando el motivo está escrito en un comentario del código o en `CLAUDE.md`, se cita entre comillas; si no, es la razón técnica que se desprende de la implementación.

## Índice

- [Decisiones funcionales (definidas por el cliente/equipo)](#decisiones-funcionales-definidas-por-el-clienteequipo)
- [Decisiones técnicas](#decisiones-técnicas)
  - [Arquitectura](#arquitectura)
  - [Avisos](#avisos)
  - [Notificaciones](#notificaciones)
  - [Datos y persistencia](#datos-y-persistencia)
  - [Seguridad](#seguridad)
  - [Tests](#tests)

---

## Decisiones funcionales (definidas por el cliente/equipo)

| # | Decisión | Motivo | En el código |
|---|----------|--------|--------------|
| F1 | **"Aula" = comisión.** | No hay aula física en el modelo. | `catedra.comision` (ej. `"1K1"`). No hay tabla de aulas. |
| F2 | **El docente elige una clase concreta de una lista, no una fecha libre.** | Evita errores de fecha. | `GET /docente/clases-disponibles`. El `POST` igual rechaza una fecha que no es día de cursada. |
| F3 | **Se puede avisar hasta 1 hora antes del inicio de la clase.** | Da tiempo a que el alumno se entere antes de salir hacia el instituto. | `ANTICIPACION_MINIMA = timedelta(hours=1)` |
| F4 | **La lista muestra los próximos 7 días.** | Las ausencias se suelen conocer con poca anticipación, y una lista corta es más fácil de usar en el celular. | `VENTANA = timedelta(days=7)`. El `POST` también rechaza las clases fuera de la ventana. |
| F5 | **Sin motivo de ausencia.** | Al alumno no le interesa. | Se quitó la columna `ausencia.motivo` (migración `c5463a887e72`). |
| F6 | **Sin cancelación ni edición (HU-04 descartada).** | Una vez dado el aviso, no hay vuelta atrás. | No hay `PATCH`/`DELETE` de avisos. `EstadoAusencia` tiene solo `activo`. |
| F7 | **Preceptor = rol `admin`; usa solo la web y recibe solo correo.** | No usa la app y no hay push en la web. | `PUT /auth/me/fcm-token` responde `403` al admin. El admin recibe correo a `usuario.email`. |
| F8 | **Todos los preceptores reciben todos los avisos, sin filtrar por carrera.** | Todos los preceptores pueden tener que responder consultas de cualquier curso; es más simple que asignarles carreras. | `_destinatarios`: todos los `admin` activos con email. |
| F9 | **Docentes y alumnos usan solo la app Android; el admin, solo la web.** | Cada cliente atiende un tipo de usuario. | Endpoints separados por rol (`/docente`, `/alumno`, `/admin` y ABM). `CORS_ORIGINS` para la web. |
| F10 | **HU-09 filtra por rango de fechas (desde/hasta) en lugar de fecha exacta.** | Permite ver un día, una semana o un mes. | `fecha_desde` y `fecha_hasta`, inclusive. Para un día: las dos iguales. |
| F11 | **El alumno ve solo avisos de hoy en adelante.** | Los pasados no le sirven. | `Ausencia.fecha >= hoy` (Argentina) en `avisos_del_alumno`. |
| F12 | **Cambio de contraseña fuera de alcance en esta versión.** | Se posterga a una versión futura. | No hay endpoint para el usuario. El admin puede asignar una contraseña nueva con `PATCH`. |

---

## Decisiones técnicas

### Arquitectura

**T1. Este repo es solo la API; dos clientes aparte.**
La app Android y el frontend web son proyectos separados y consumen la misma API. Las plantillas Jinja del repo son solo la página de inicio.
*Por qué:* cada cliente se desarrolla con su propia tecnología (Android Studio y web). La API concentra las reglas para que ningún cliente pueda saltearlas.

**T2. Capas `endpoints → services → crud → models`.**
Los endpoints solo manejan HTTP y permisos. Las reglas de negocio están en `services/` (las de HU-02 en `services/ausencias.py`).
*Por qué:* las reglas se pueden probar y reutilizar sin pasar por HTTP, y cada capa tiene una sola responsabilidad.

**T3. La "clase" no es una tabla.**
Se calcula a partir de `dia_semana`, `hora_inicio` y `hora_fin` de la cátedra.
*Por qué:* así no hay que generar ni mantener filas por cada fecha del cuatrimestre. Un aviso es simplemente `(catedra_id, fecha)`.
*Consecuencia:* no hay manera de marcar feriados o días sin clase (está fuera de alcance).

### Avisos

**T4. El servidor revalida todo en `POST /docente/avisos`.**
No confía en que el cliente mandó una opción de la lista (docstring de `registrar_aviso`).
*Por qué:* la lista es una comodidad de la interfaz; las reglas tienen que valer aunque alguien llame a la API directamente.

**T5. "Un aviso por clase" lo garantiza la base (`uq_ausencia_catedra_fecha`), no una consulta previa.**
Si ya existe, el `commit` lanza `IntegrityError` y `manejar_integridad` lo convierte en `409`.
*Por qué:* la restricción vale incluso si llegan dos requests al mismo tiempo, cosa que una consulta previa no puede asegurar. La lista de clases disponibles igual excluye las que ya tienen aviso.

**T6. Columna `estado` con un único valor (`activo`).**
La respuesta (`AvisoDetalle`) no lo incluye: "un aviso registrado siempre está activo (HU-04 descartada)".

**T7. El aviso guarda el docente que lo dio (`ausencia.docente_id`), en lugar de deducirlo de la cátedra.**
El historial del docente (HU-03), el filtro `docente_id` del admin (HU-09) y el campo `docente` de `AvisoDetalle` usan esa columna. Los avisos del alumno y las notificaciones siguen buscando por cátedra.
*Por qué:* el aviso tiene que quedar a nombre de quien lo dio aunque después se reasigne la cátedra a otro docente. Si se dedujera de `catedra.docente_id`, una reasignación movería el historial al docente nuevo. No hay un `CHECK` que obligue a que coincida con el docente de la cátedra: no puede comparar con otra tabla, y la regla solo vale al crear el aviso (la valida `registrar_aviso`). La migración completó los avisos existentes con el docente que su cátedra tenía en ese momento.

**T8. Orden determinístico en los listados de avisos.**
El orden es fecha, hora de inicio e `id`.
*Por qué:* "así la paginación no repite ni saltea avisos" (comentario en `services/ausencias.py`).

**T9. Carga en lote de cátedra, materia y docente (`selectinload`).**
*Por qué:* "3 consultas en total, no una por aviso" (`_con_detalle`).

### Notificaciones

**T10. Un solo `BackgroundTasks`, sin colas ni Celery.**
La API responde `201` y después envía correos y push.
*Por qué:* el docente no tiene que esperar a SMTP ni a FCM, y el volumen (los alumnos de una cátedra más los preceptores) no justifica sumar infraestructura. Así lo define `CLAUDE.md`: "Sin colas, sin Celery, sin tabla de historial de notificaciones".

**T11. Destinatarios y textos se arman durante el request.**
*Por qué:* "FastAPI cierra la sesión de la base antes de correr los BackgroundTasks" (docstring de `services/notificaciones.py`). Para limpiar tokens inválidos, la tarea abre su propia sesión (`abrir_sesion`).

**T12. Los fallos de notificación nunca anulan el aviso.**
`programar` y `enviar` capturan todas las excepciones y las registran en el log.
*Por qué:* el aviso ya quedó registrado. Que falle un correo no es motivo para hacerle creer al docente que su aviso no se registró.

**T13. Un correo por destinatario.**
*Por qué:* nadie ve los emails de los demás ("nunca todos en Para", `CLAUDE.md`). Se usa una sola conexión SMTP para todos los mensajes, y si falla uno se sigue con el resto.

**T14. `smtplib` de la biblioteca estándar; `firebase-admin` como única dependencia nueva.**
*Por qué:* `CLAUDE.md` pide dependencias nuevas solo si son imprescindibles. El correo no necesita ninguna; el push sí necesita la librería oficial de Firebase.

**T15. Solo se borran los tokens con `UNREGISTERED` o `SENDER_ID_MISMATCH`.**
*Por qué:* "INVALID_ARGUMENT no se incluye: puede venir de un mensaje mal armado y borraría los tokens de todos" (comentario en `core/push.py`).

**T16. Un celular por usuario: columna `usuario.fcm_token`, sin tabla de dispositivos.**
*Por qué:* es el mínimo que pide HU-06. Si un token ya lo tenía otro usuario, se le quita "para que no reciba push ajenos" (docstring de `asignar_token`).

**T17. Si falta la configuración SMTP o Firebase, la app arranca igual.**
Deja un warning al iniciar y saltea ese tipo de envío.
*Por qué:* se puede desarrollar y probar sin credenciales reales.

**T18. El email del preceptor está en `usuario.email`.**
El admin no tiene perfil (como sí tienen docentes y alumnos), así que el email va en `Usuario`, es opcional y se carga con `crear_admin.py`. Un admin sin email no recibe correos.

### Datos y persistencia

**T19. `Usuario` separado de los perfiles `Docente` y `Alumno`.**
`Usuario` tiene las credenciales y el rol de todos; el perfil tiene los datos personales. La relación es 1 a 1 (`usuario_id` único).
*Por qué:* un único login para los tres roles (HU-01). El admin no necesita perfil.

**T20. Bajas lógicas en lugar de `DELETE`.**
- Docentes y alumnos se desactivan con `activo: false`; "así se conserva el historial de sus avisos" (docstring de `endpoints/docentes.py`).
- Las inscripciones se dan de baja con `vigente: false`, "sin perder el registro".

Carreras, materias, cátedras e inscripciones sí tienen `DELETE`, pero falla con `409` si hay datos asociados (las FK no tienen `ON DELETE`).

**T21. `naming_convention` + diccionario `MENSAJES`.**
Las restricciones tienen nombres predecibles (`uq_<tabla>_<columna>`, `fk_...`), y `manejar_integridad` traduce cada una a un mensaje en español con el código HTTP correcto: `409` para unicidad, `422` para FK y CHECK.
*Por qué:* "Alembic los necesita para poder borrarlos" (comentario en `app/models/__init__.py`), y el cliente recibe un mensaje claro en lugar de un error de la base.

**T22. Validación en dos niveles.**
Los schemas validan formato (DNI, largo de la contraseña, email, `dia_semana`, horario) y la base valida integridad (únicos, FK, CHECK).
*Por qué:* el schema da errores tempranos y detallados; la base garantiza la consistencia aunque falle o se saltee la validación del schema (por ejemplo, el `PATCH` de cátedra no valida el horario y lo frena `ck_catedra_horario`).

**T23. Migraciones con Alembic, revisadas a mano.**
Por ejemplo, el enum `estadoausencia` se crea explícitamente antes de `add_column`, y el downgrade de `motivo` usa `server_default`.
*Por qué:* "add_column no crea el tipo enum en PostgreSQL: hay que crearlo antes", y "si ya hay avisos cargados, la columna NOT NULL necesita un valor" (comentarios en las migraciones).

### Seguridad

**T24. JWT sin estado + chequeo de `activo` en cada request.**
El token no se guarda en la base, pero en cada request se busca el usuario y se verifica que esté activo.
*Por qué:* desactivar a alguien corta su acceso al instante, sin lista de tokens revocados.

**T25. Hash ficticio en el login.**
*Por qué:* "si el DNI no existe igual se verifica una contraseña, así la respuesta tarda lo mismo y no revela qué DNIs están registrados" (`services/auth.py`). Por el mismo motivo, el mensaje de error es igual en todos los casos.

**T26. El primer admin se crea por script, no por la API.**
Con `app/scripts/crear_admin.py`, que pide la contraseña por teclado.
*Por qué:* el alcance (HU-08) solo incluye el alta de docentes y estudiantes. Pedirla por teclado hace que "no quede en el historial de la terminal" (docstring del script).

**T27. Secretos fuera de git.**
`.env` y el JSON del service account de Firebase (en `secrets/`) están en `.gitignore`.

**T28. `POST /auth/token` oculto del esquema.**
*Por qué:* existe solo para el botón *Authorize* de `/docs`, que usa el formato OAuth2 (`username` = DNI). Los clientes usan `POST /auth/login` con JSON.

### Tests

**T29. Hora "actual" reemplazable y servicios externos falsos.**
- `ausencias.ahora()` existe para que los tests fijen la hora ("Los tests la reemplazan para fijar la hora").
- SMTP y FCM se reemplazan por fakes en todos los tests.
- `abrir_sesion()` se reemplaza por la sesión del test.

*Por qué:* las reglas de 1 hora y 7 días se prueban en los bordes exactos, y los tests nunca envían correos ni push reales.

**T30. `firebase-admin` fijado en 7.7.0 y el aviso de `MulticastMessage.tokens` silenciado en los tests.**
Esa versión marca como obsoleto `MulticastMessage(tokens=...)` (lo usa `core/push.py`) y sugiere `fids`. El filtro está en `pytest.ini` y apaga solo ese mensaje.
*Por qué:* los `fids` no son el token de `onNewToken` que manda la app; pasarlos cambiaría el destinatario y el push dejaría de llegar. **Si se actualiza `firebase-admin`, revisar este punto**: que `tokens` siga existiendo y que el filtro siga haciendo falta.
