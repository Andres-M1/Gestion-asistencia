# Historias de usuario

Historias de usuario de **Gestion Asist** tal como quedaron implementadas en la API. Los criterios de aceptación describen el comportamiento del código actual; la mayoría está cubierta por los tests de `tests/`.

Todas las rutas empiezan con `/api/v1`. El detalle de cada endpoint (parámetros, ejemplos y errores) está en [api.md](api.md).

## Índice

- [Glosario](#glosario)
- [Resumen](#resumen)
- [HU-01: Login con DNI y contraseña](#hu-01-login-con-dni-y-contraseña)
- [HU-02: Registrar un aviso de ausencia](#hu-02-registrar-un-aviso-de-ausencia)
- [HU-03: Historial de avisos del docente](#hu-03-historial-de-avisos-del-docente)
- [HU-04: Cancelar o editar un aviso (descartada)](#hu-04-cancelar-o-editar-un-aviso-descartada)
- [HU-05: Avisos del alumno](#hu-05-avisos-del-alumno)
- [HU-06: Notificaciones al registrarse un aviso](#hu-06-notificaciones-al-registrarse-un-aviso)
- [HU-07: Inscripciones vigentes del alumno](#hu-07-inscripciones-vigentes-del-alumno)
- [HU-08: Alta de docentes y estudiantes](#hu-08-alta-de-docentes-y-estudiantes)
- [HU-09: Listado de avisos con filtros](#hu-09-listado-de-avisos-con-filtros)
- [HU-10: Asignar docentes a materias](#hu-10-asignar-docentes-a-materias)
- [Fuera de alcance](#fuera-de-alcance)

## Glosario

| Término | Significado en el sistema |
|---------|---------------------------|
| **Cátedra** | Una materia dictada por un docente en una **comisión** (ej. "1K1"), un día de la semana y un horario. Tabla `catedra`. |
| **Comisión** | Lo que en el instituto se llama "aula". Es un texto de la cátedra (`comision`); no hay aula física en el modelo. |
| **Clase** | Una ocurrencia concreta de una cátedra en una fecha (ej. "Programación I · 1K1 · lunes 02/11/2026 · 18:00 a 20:00"). No es una tabla: se calcula con `dia_semana`, `hora_inicio` y `hora_fin`. |
| **Aviso** | El aviso de que el docente no dará una clase. Modelo `Ausencia`, tabla `ausencia`. |
| **Inscripción vigente** | Fila de `inscripcion` con `vigente = true`. |
| **Roles** | `admin` (preceptor), `docente` y `estudiante` (alumno). |

## Resumen

| HU | Rol | Qué | Endpoints | Estado |
|----|-----|-----|-----------|--------|
| HU-01 | Todos | Login con DNI y contraseña | `POST /auth/login`, `GET /auth/me` | ✅ Implementada |
| HU-02 | Docente | Registrar aviso eligiendo una clase de una lista | `GET /docente/clases-disponibles`, `POST /docente/avisos` | ✅ Implementada |
| HU-03 | Docente | Ver el historial de sus avisos | `GET /docente/avisos` | ✅ Implementada |
| HU-04 | — | Cancelar o editar un aviso | — | ❌ Descartada |
| HU-05 | Estudiante | Ver avisos de sus cátedras con inscripción vigente | `GET /alumno/avisos` | ✅ Implementada |
| HU-06 | Estudiante / Preceptor | Push + correo al alumno, correo al preceptor | (dentro de `POST /docente/avisos`), `PUT`/`DELETE /auth/me/fcm-token` | ✅ Implementada |
| HU-07 | Estudiante | Ver sus inscripciones vigentes y sus avisos | `GET /alumno/inscripciones`, `GET /alumno/avisos?catedra_id=` | ✅ Implementada |
| HU-08 | Admin | Alta de docentes y estudiantes | `/docentes/`, `/alumnos/` | ✅ Implementada |
| HU-09 | Admin | Listar avisos con filtros | `GET /admin/avisos` | ✅ Implementada |
| HU-10 | Admin | Asignar docentes a materias (cátedras) | `/catedras/` | ✅ Implementada |

Carreras, materias e inscripciones también tienen ABM para el admin, porque hacen falta para cargar los datos. No tienen una HU propia.

---

## HU-01: Login con DNI y contraseña

**Como** docente, alumno o preceptor, **quiero** ingresar con mi DNI y mi contraseña **para** usar las funciones de mi rol.

**Endpoints:** `POST /auth/login`, `GET /auth/me` · **Estado:** ✅ Implementada

### Criterios de aceptación

1. **Dado** un usuario activo con DNI y contraseña correctos, **cuando** hace `POST /auth/login`, **entonces** recibe `200` con `access_token` (JWT) y `token_type: "bearer"`. El token vence a los `ACCESS_TOKEN_EXPIRE_MINUTES` minutos (480 por defecto).
2. **Dado** un DNI inexistente, una contraseña incorrecta o un usuario desactivado (`activo = false`), **cuando** hace login, **entonces** recibe `401` con el mismo mensaje en los tres casos: `"DNI o contraseña incorrectos"`.
3. **Dado** un DNI que no existe, **cuando** hace login, **entonces** igual se verifica una contraseña contra un hash ficticio, para que la respuesta tarde lo mismo y no revele qué DNIs están registrados.
4. **Dado** un token válido, **cuando** pide `GET /auth/me`, **entonces** recibe `id`, `dni`, `rol` y `perfil` (nombre, apellido y email de su perfil de docente o alumno). Para el admin, `perfil` es `null`.
5. **Dado** un request sin token, **entonces** recibe `401` (`"Not authenticated"`). **Dado** un token inválido, vencido o de un usuario desactivado o inexistente, **entonces** recibe `401` (`"Token inválido o expirado"`).
6. **Dado** un usuario logueado, **cuando** llama a un endpoint de otro rol, **entonces** recibe `403` (`"No tenés permiso para esta acción"`).

---

## HU-02: Registrar un aviso de ausencia

**Como** docente, **quiero** elegir de una lista una clase concreta que no voy a dar y registrar el aviso **para** que mis alumnos y los preceptores se enteren.

**Endpoints:** `GET /docente/clases-disponibles`, `POST /docente/avisos` · **Estado:** ✅ Implementada

El aviso no tiene motivo, y el docente no elige una fecha libre: elige una opción de la lista.

### Criterios de aceptación

**Lista de clases disponibles**

1. **Dado** un docente logueado, **cuando** pide `GET /docente/clases-disponibles`, **entonces** recibe las clases de **sus** cátedras que empiezan entre **ahora + 1 hora** y **ahora + 7 días**, en hora de Argentina, ambos extremos incluidos.
2. Cada opción trae `catedra_id`, `fecha`, `materia`, `comision`, `dia_semana`, `hora_inicio` y `hora_fin`.
3. La lista viene ordenada por fecha y hora de inicio.
4. **Dado** que faltan exactamente 60 minutos para una clase, **entonces** la clase todavía aparece. **Dado** que faltan menos de 60 minutos, **entonces** ya no aparece.
5. **Dada** una clase que empieza exactamente dentro de 7 días, **entonces** aparece.
6. **Dada** una clase que ya tiene aviso, **entonces** no aparece.
7. **Dado** un docente sin cátedras, **entonces** recibe `[]`.

**Registro del aviso**

8. **Dada** una clase válida, **cuando** hace `POST /docente/avisos` con `{catedra_id, fecha}`, **entonces** recibe `201` con el detalle del aviso: `id`, `fecha`, `materia`, `comision`, `dia_semana`, horario, `docente` y `creado_en`. El aviso queda guardado con estado `activo`, a nombre del docente logueado, y se disparan las notificaciones de [HU-06](#hu-06-notificaciones-al-registrarse-un-aviso).
9. El servidor **vuelve a validar todo**, sin confiar en que el cliente mandó una opción de la lista:
   - **Dada** una cátedra que no existe o que no es del docente, **entonces** `404` (`"Cátedra no encontrada"`).
   - **Dada** una fecha que no cae en el día de cursada de la cátedra, **entonces** `422` (`"La fecha no corresponde al día de cursada de la cátedra"`).
   - **Dada** una clase que empieza en menos de 1 hora o que ya pasó, **entonces** `422` (`"Solo se puede avisar hasta 1 hora antes del inicio de la clase"`).
   - **Dada** una clase que empieza dentro de más de 7 días, **entonces** `422` (`"Solo se puede avisar sobre clases de los próximos 7 días"`).
   - **Dada** una clase que ya tiene aviso, **entonces** `409` (`"Ya hay un aviso para esa cátedra en esa fecha"`).
10. Las comparaciones se hacen en `America/Argentina/Buenos_Aires`, aunque el servidor esté en UTC.
11. Solo el rol `docente` puede usar estos endpoints; otro rol recibe `403`. Un usuario docente sin perfil de docente recibe `403` (`"El usuario no tiene perfil de docente"`).

---

## HU-03: Historial de avisos del docente

**Como** docente, **quiero** ver los avisos que registré **para** saber qué clases ya avisé.

**Endpoint:** `GET /docente/avisos` · **Estado:** ✅ Implementada

### Criterios de aceptación

1. **Dado** un docente logueado, **cuando** pide `GET /docente/avisos`, **entonces** recibe los avisos que **dio él**, **pasados y futuros**, del más nuevo al más viejo (fecha descendente, después hora de inicio descendente, después `id` descendente).
2. **Dado** otro docente con avisos, **entonces** sus avisos no aparecen.
3. **Dada** una cátedra que se reasignó a otro docente, **entonces** los avisos que dio el docente anterior siguen en su historial y a su nombre, y el docente nuevo no los ve.
4. Cada aviso trae el mismo detalle que en HU-02 y **no** incluye `estado`.
5. Se pagina con `offset` y `limit` (máximo 100, por defecto 100).
6. **Dado** un docente sin avisos, **entonces** recibe `[]`.
7. Sin token: `401`. Otro rol, o un docente sin perfil: `403`.

---

## HU-04: Cancelar o editar un aviso (descartada)

**Estado:** ❌ **Descartada**

**Motivo:** una vez dado el aviso, no hay vuelta atrás. Ya se notificó a los alumnos y a los preceptores, así que un aviso registrado no se cancela ni se edita.

Cómo se refleja en el código:

- No hay endpoints `PATCH` ni `DELETE` para avisos.
- El enum `EstadoAusencia` tiene un único valor, `activo`.
- La respuesta `AvisoDetalle` no incluye `estado`.

---

## HU-05: Avisos del alumno

**Como** alumno, **quiero** ver los avisos de las cátedras en las que estoy inscripto **para** saber qué clases no se van a dictar.

**Endpoint:** `GET /alumno/avisos` · **Estado:** ✅ Implementada

### Criterios de aceptación

1. **Dado** un alumno logueado, **cuando** pide `GET /alumno/avisos`, **entonces** recibe solo los avisos de las cátedras donde tiene **inscripción vigente**.
2. Solo aparecen los avisos **de hoy en adelante**, en hora de Argentina. El aviso de hoy aparece aunque la clase ya haya terminado.
3. Vienen ordenados del más próximo al más lejano: fecha, hora de inicio e `id`, ascendentes.
4. **Dada** una inscripción con `vigente = false`, o una cátedra donde no está inscripto, **entonces** sus avisos no aparecen.
5. Cada aviso trae el mismo detalle que en HU-02.
6. Se pagina con `offset` y `limit` (máximo 100).
7. Sin token: `401`. Otro rol, o un estudiante sin perfil de alumno: `403`.

---

## HU-06: Notificaciones al registrarse un aviso

**Como** alumno, **quiero** recibir una notificación push y un correo cuando un docente avisa que no va a dar una clase de mi cátedra **para** enterarme a tiempo.

**Como** preceptor, **quiero** recibir un correo con cada aviso **para** estar al tanto de las clases que no se dictan.

**Endpoints:** el envío ocurre dentro de `POST /docente/avisos`. Token del celular: `PUT /auth/me/fcm-token` y `DELETE /auth/me/fcm-token` · **Estado:** ✅ Implementada

### Criterios de aceptación

**Destinatarios**

1. **Dado** un aviso nuevo, **entonces** reciben **correo**:
   - cada alumno **activo** con inscripción **vigente** en esa cátedra, en el email de su perfil;
   - cada usuario `admin` **activo** que tenga `email`, sin filtrar por carrera.
2. **Dado** un aviso nuevo, **entonces** reciben **push** los mismos alumnos que tengan `fcm_token` registrado.
3. **Dados** alumnos con inscripción no vigente, alumnos de otras cátedras o usuarios inactivos, **entonces** no reciben nada.
4. **Dado** que no hay destinatarios, **entonces** no se envía nada.

**Envío**

5. Se envía **un correo por destinatario**: nadie ve los emails de los demás.
6. El correo y el push incluyen materia, comisión, fecha (día de la semana y dd/mm/aaaa), horario y docente.
7. El push se envía con Firebase Cloud Messaging en tandas de hasta 500 tokens.
8. Los envíos corren en **segundo plano**: la respuesta `201` no espera a que terminen.

**Fallos**

9. **Dado** que falla un correo, **entonces** se registra en el log y se siguen enviando los demás.
10. **Dado** que falla la conexión SMTP, el envío a FCM o el armado de los destinatarios, **entonces** se registra en el log y **el aviso queda creado igual**.
11. **Dado** que FCM responde `UNREGISTERED` o `SENDER_ID_MISMATCH` para un token, **entonces** ese `fcm_token` queda en `null`. Otros errores solo se registran en el log.
12. **Dado** que faltan `SMTP_HOST` o `FIREBASE_CREDENTIALS`, **entonces** la app arranca igual, deja un warning en el log y saltea ese tipo de envío.

**Token del celular**

13. **Dado** un docente o alumno logueado, **cuando** hace `PUT /auth/me/fcm-token` con `{"token": "..."}`, **entonces** recibe `204` y el token queda guardado. Si otro usuario tenía ese mismo token (mismo celular), se le quita.
14. **Cuando** hace `DELETE /auth/me/fcm-token`, **entonces** recibe `204` y su token queda en `null`.
15. **Dado** un token vacío, **entonces** `422`. **Dado** un admin, **entonces** `403`. **Dado** que no hay sesión, **entonces** `401`.

**Email del preceptor**

16. El email del preceptor se carga al crearlo con `python -m app.scripts.crear_admin --dni ... --email ...`, o por teclado si no se pasa `--email`. Si se omite, ese preceptor no recibe correos.

---

## HU-07: Inscripciones vigentes del alumno

**Como** alumno, **quiero** ver las cátedras en las que estoy inscripto, con su materia, comisión, horario y docente, **para** consultar los avisos de cada una.

**Endpoints:** `GET /alumno/inscripciones`, `GET /alumno/avisos?catedra_id=` · **Estado:** ✅ Implementada

### Criterios de aceptación

1. **Dado** un alumno logueado, **cuando** pide `GET /alumno/inscripciones`, **entonces** recibe solo sus inscripciones **vigentes**, en el orden de la semana (día, hora de inicio e `id` de la cátedra).
2. Cada ítem trae `catedra_id`, `materia`, `comision`, `dia_semana`, `hora_inicio`, `hora_fin` y `docente` (nombre y apellido). La lista no se pagina.
3. **Dado** un alumno sin inscripciones vigentes, **entonces** recibe `[]`.
4. **Dada** una de sus cátedras, **cuando** pide `GET /alumno/avisos?catedra_id={id}`, **entonces** recibe los avisos de hoy en adelante de esa cátedra.
5. **Dada** una cátedra donde no tiene inscripción vigente, o que no existe, **entonces** `404` (`"No tenés una inscripción vigente en esa cátedra"`).
6. No ve inscripciones de otros alumnos. Otro rol: `403`. Sin token: `401`.

---

## HU-08: Alta de docentes y estudiantes

**Como** administrador, **quiero** dar de alta docentes y estudiantes con DNI y contraseña **para** que puedan usar la app.

**Endpoints:** `POST/GET /docentes/`, `GET/PATCH /docentes/{id}`, `POST/GET /alumnos/`, `GET/PATCH /alumnos/{id}` · **Estado:** ✅ Implementada

### Criterios de aceptación

1. **Dados** DNI, contraseña, nombre, apellido y email válidos (y `carrera_id` para un alumno), **cuando** el admin hace `POST`, **entonces** recibe `201`. En una sola transacción se crean el `Usuario` (con rol `docente` o `estudiante` y la contraseña hasheada) y su perfil.
2. Validaciones (`422`):
   - DNI de 6 a 10 dígitos, solo números;
   - contraseña de al menos 8 caracteres;
   - email válido;
   - nombre y apellido no vacíos;
   - para un alumno, `carrera_id` existente (`"La carrera indicada no existe"`).
3. **Dado** un DNI ya registrado, **entonces** `409` (`"Ya existe un usuario con ese DNI"`). **Dado** un email repetido, **entonces** `409` (`"Ya existe un docente con ese email"` o `"Ya existe un alumno con ese email"`).
4. Con `PATCH` el admin puede cambiar nombre, apellido, email, carrera (alumno), asignar una contraseña nueva o desactivar (`activo: false`). El DNI no se edita.
5. **No hay `DELETE`**: para que alguien no pueda entrar más, se lo desactiva. Un usuario inactivo no puede loguearse, sus tokens dejan de servir y no recibe notificaciones.
6. El listado se pagina (`offset`, `limit` ≤ 100) y se ordena por `id`. Los alumnos se pueden filtrar por `carrera_id`.
7. Si no existe el `id` pedido, `404`. Si no es admin, `403`.

---

## HU-09: Listado de avisos con filtros

**Como** administrador, **quiero** listar los avisos filtrando por carrera, materia, comisión, docente y fecha **para** hacer el seguimiento de las clases no dictadas.

**Endpoint:** `GET /admin/avisos` · **Estado:** ✅ Implementada

### Criterios de aceptación

1. **Dado** un admin, **cuando** pide `GET /admin/avisos`, **entonces** recibe todos los avisos, pasados y futuros, del más nuevo al más viejo (fecha, hora de inicio e `id`, descendentes).
2. Filtros opcionales y combinables entre sí:
   - `carrera_id`;
   - `materia_id`;
   - `comision`: texto exacto sin distinguir mayúsculas, así que `"1k1"` encuentra `"1K1"`, pero `"1K"` no encuentra `"1K1"`;
   - `docente_id`: el docente que dio el aviso, aunque la cátedra se haya reasignado después;
   - `fecha_desde` y `fecha_hasta`, ambas inclusive.
3. **Dado** `fecha_desde` posterior a `fecha_hasta`, **entonces** `422` (`"fecha_desde no puede ser posterior a fecha_hasta"`).
4. **Dados** ids que no existen, **entonces** `[]` (no `404`).
5. Cada aviso trae el mismo detalle que en HU-02.
6. Se pagina con `offset` y `limit` (máximo 100).
7. Docente o alumno: `403`. Sin token: `401`.

---

## HU-10: Asignar docentes a materias

**Como** administrador, **quiero** asignar un docente a una materia en una comisión, día y horario (crear la cátedra) **para** que el docente pueda avisar sus ausencias y los alumnos inscribirse.

**Endpoints:** `POST/GET /catedras/`, `GET/PATCH/DELETE /catedras/{id}` · **Estado:** ✅ Implementada

### Criterios de aceptación

1. **Dados** `materia_id`, `docente_id`, `comision`, `dia_semana`, `hora_inicio` y `hora_fin` válidos, **cuando** el admin hace `POST /catedras/`, **entonces** recibe `201` con la cátedra creada.
2. Validaciones (`422`):
   - `dia_semana` entre 1 (lunes) y 7 (domingo);
   - `hora_fin` posterior a `hora_inicio`;
   - comisión no vacía;
   - materia y docente existentes (`"La materia indicada no existe"`, `"El docente indicado no existe"`).
3. **Dada** una materia que ya tiene una cátedra con esa comisión, **entonces** `409` (`"Esa materia ya tiene una cátedra con esa comisión"`).
4. Con `PATCH` se puede cambiar cualquier campo, incluido `docente_id`, para reasignar la cátedra a otro docente.
5. **Dada** una cátedra con inscripciones o avisos, **cuando** se la borra, **entonces** `409` (`"No se puede borrar: tiene registros asociados"`).
6. El listado se filtra por `materia_id` y `docente_id`, se pagina y se ordena por `id`.
7. Si no existe el `id` pedido, `404`. Si no es admin, `403`.

---

## Fuera de alcance

No están implementadas en esta versión:

| Funcionalidad | Situación actual |
|---------------|------------------|
| **Cambio o recuperación de contraseña** | No hay endpoint para que el usuario cambie su contraseña. Solo el admin puede asignar una nueva con `PATCH /docentes/{id}` o `PATCH /alumnos/{id}`. |
| **Cancelar o editar avisos** | HU-04 descartada. |
| **Motivo del aviso** | `ausencia` no tiene columna `motivo`: se quitó con una migración. |
| **Push en la web** | Los preceptores reciben solo correo. Solo docentes y alumnos registran un token FCM; el admin recibe `403`. |
| **Feriados o días sin clase** | La lista de clases disponibles no considera feriados: toda fecha que cae en el `dia_semana` de la cátedra es una clase. |
