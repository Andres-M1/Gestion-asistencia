# Diagramas

Diagramas en Mermaid hechos a partir del código (`app/models`, `app/schemas`, `app/services`, `app/core`) y del esquema real de la base (migraciones de `alembic/versions`).

## Índice

1. [Diagrama entidad-relación (DER)](#1-diagrama-entidad-relación-der)
2. [Diagrama de clases](#2-diagrama-de-clases)
3. [Secuencia: login](#3-secuencia-login)
4. [Secuencia: el docente registra un aviso](#4-secuencia-el-docente-registra-un-aviso)
5. [Componentes](#5-componentes)

---

## 1. Diagrama entidad-relación (DER)

Tipos de PostgreSQL. `PK` es clave primaria, `FK` clave foránea y `UK` único de una sola columna. Todas las columnas son `NOT NULL`, salvo las marcadas como "nullable".

```mermaid
erDiagram
    USUARIO ||--o| DOCENTE : "tiene perfil"
    USUARIO ||--o| ALUMNO : "tiene perfil"
    CARRERA ||--o{ MATERIA : "tiene"
    CARRERA ||--o{ ALUMNO : "cursa"
    MATERIA ||--o{ CATEDRA : "se dicta en"
    DOCENTE ||--o{ CATEDRA : "dicta"
    ALUMNO ||--o{ INSCRIPCION : "se inscribe"
    CATEDRA ||--o{ INSCRIPCION : "tiene"
    CATEDRA ||--o{ AUSENCIA : "tiene avisos"
    DOCENTE ||--o{ AUSENCIA : "da"

    USUARIO {
        integer id PK
        varchar dni UK "ix_usuario_dni (índice único)"
        varchar password_hash "Argon2"
        rol rol "enum: admin, docente, estudiante"
        boolean activo
        varchar email "nullable, solo lo usa el admin"
        varchar fcm_token "nullable, celular para push"
    }
    DOCENTE {
        integer id PK
        integer usuario_id FK,UK
        varchar nombre
        varchar apellido
        varchar email UK
    }
    ALUMNO {
        integer id PK
        integer usuario_id FK,UK
        integer carrera_id FK
        varchar nombre
        varchar apellido
        varchar email UK
    }
    CARRERA {
        integer id PK
        varchar nombre UK
    }
    MATERIA {
        integer id PK
        integer carrera_id FK
        varchar nombre
    }
    CATEDRA {
        integer id PK
        integer materia_id FK "UK compuesta con comision"
        integer docente_id FK
        varchar comision "ej. 1K1"
        integer dia_semana "CHECK 1 a 7"
        time hora_inicio "hora de Argentina"
        time hora_fin "CHECK hora_fin > hora_inicio"
    }
    INSCRIPCION {
        integer id PK
        integer alumno_id FK "UK compuesta con catedra_id"
        integer catedra_id FK
        boolean vigente
    }
    AUSENCIA {
        integer id PK
        integer catedra_id FK "UK compuesta con fecha"
        integer docente_id FK "quien dio el aviso"
        date fecha
        estadoausencia estado "enum: activo"
        timestamptz creado_en "UTC"
    }
```

### Restricciones

Nombres tal como están en la base. Los generan las `naming_convention` de `app/models/__init__.py`.

| Tabla | Restricción | Tipo | Definición |
|-------|-------------|------|------------|
| todas | `pk_<tabla>` | PRIMARY KEY | `(id)`, entero autoincremental |
| `usuario` | `ix_usuario_dni` | UNIQUE INDEX | `(dni)` |
| `docente` | `uq_docente_usuario_id` | UNIQUE | `(usuario_id)`: relación 1 a 1 con `usuario` |
| `docente` | `uq_docente_email` | UNIQUE | `(email)` |
| `docente` | `fk_docente_usuario_id_usuario` | FOREIGN KEY | `usuario_id → usuario.id` |
| `alumno` | `uq_alumno_usuario_id` | UNIQUE | `(usuario_id)`: relación 1 a 1 con `usuario` |
| `alumno` | `uq_alumno_email` | UNIQUE | `(email)` |
| `alumno` | `fk_alumno_usuario_id_usuario` | FOREIGN KEY | `usuario_id → usuario.id` |
| `alumno` | `fk_alumno_carrera_id_carrera` | FOREIGN KEY | `carrera_id → carrera.id` |
| `carrera` | `uq_carrera_nombre` | UNIQUE | `(nombre)` |
| `materia` | `fk_materia_carrera_id_carrera` | FOREIGN KEY | `carrera_id → carrera.id` |
| `catedra` | `uq_catedra_materia_comision` | UNIQUE | `(materia_id, comision)` |
| `catedra` | `ck_catedra_dia_semana` | CHECK | `dia_semana BETWEEN 1 AND 7` (1 = lunes … 7 = domingo) |
| `catedra` | `ck_catedra_horario` | CHECK | `hora_fin > hora_inicio` |
| `catedra` | `fk_catedra_materia_id_materia` | FOREIGN KEY | `materia_id → materia.id` |
| `catedra` | `fk_catedra_docente_id_docente` | FOREIGN KEY | `docente_id → docente.id` |
| `inscripcion` | `uq_inscripcion_alumno_catedra` | UNIQUE | `(alumno_id, catedra_id)` |
| `inscripcion` | `fk_inscripcion_alumno_id_alumno` | FOREIGN KEY | `alumno_id → alumno.id` |
| `inscripcion` | `fk_inscripcion_catedra_id_catedra` | FOREIGN KEY | `catedra_id → catedra.id` |
| `ausencia` | `uq_ausencia_catedra_fecha` | UNIQUE | `(catedra_id, fecha)`: un aviso por clase |
| `ausencia` | `fk_ausencia_catedra_id_catedra` | FOREIGN KEY | `catedra_id → catedra.id` |
| `ausencia` | `fk_ausencia_docente_id_docente` | FOREIGN KEY | `docente_id → docente.id`: quien dio el aviso. No cambia si la cátedra se reasigna. |

- Las claves foráneas no tienen `ON DELETE`: borrar una fila referenciada falla, y la API responde `409`.
- Los valores por defecto (`activo = true`, `vigente = true`, `estado = 'activo'`, `creado_en = ahora en UTC`) los pone la aplicación, no la base.

### Tipos enumerados

| Tipo PostgreSQL | Valores | Enum de Python |
|-----------------|---------|----------------|
| `rol` | `admin`, `docente`, `estudiante` | `app.models.usuario.Rol` |
| `estadoausencia` | `activo` | `app.models.ausencia.EstadoAusencia` |

---

## 2. Diagrama de clases

Modelos (tablas), schemas principales (entrada y salida de la API) y services y módulos de `core` con sus funciones públicas. Los services son módulos de Python, no clases: se muestran con el estereotipo `«service»`.

```mermaid
classDiagram
    direction LR

    %% ---------- Modelos (app/models) ----------
    class Rol {
        <<enumeration>>
        admin
        docente
        estudiante
    }
    class EstadoAusencia {
        <<enumeration>>
        activo
    }
    class Usuario {
        <<table>>
        +int id
        +str dni
        +str password_hash
        +Rol rol
        +bool activo
        +Optional~str~ email
        +Optional~str~ fcm_token
    }
    class Docente {
        <<table>>
        +int id
        +int usuario_id
        +str nombre
        +str apellido
        +str email
    }
    class Alumno {
        <<table>>
        +int id
        +int usuario_id
        +int carrera_id
        +str nombre
        +str apellido
        +str email
    }
    class Carrera {
        <<table>>
        +int id
        +str nombre
    }
    class Materia {
        <<table>>
        +int id
        +int carrera_id
        +str nombre
    }
    class Catedra {
        <<table>>
        +int id
        +int materia_id
        +int docente_id
        +str comision
        +int dia_semana
        +time hora_inicio
        +time hora_fin
    }
    class Inscripcion {
        <<table>>
        +int id
        +int alumno_id
        +int catedra_id
        +bool vigente
    }
    class Ausencia {
        <<table>>
        +int id
        +int catedra_id
        +int docente_id
        +date fecha
        +EstadoAusencia estado
        +datetime creado_en
    }

    Usuario --> Rol
    Ausencia --> EstadoAusencia
    Usuario "1" -- "0..1" Docente : docente / usuario
    Usuario "1" -- "0..1" Alumno : alumno / usuario
    Carrera "1" -- "*" Materia : materias / carrera
    Carrera "1" -- "*" Alumno : alumnos / carrera
    Materia "1" -- "*" Catedra : catedras / materia
    Docente "1" -- "*" Catedra : catedras / docente
    Alumno "1" -- "*" Inscripcion : inscripciones / alumno
    Catedra "1" -- "*" Inscripcion : inscripciones / catedra
    Catedra "1" -- "*" Ausencia : ausencias / catedra
    Docente "1" -- "*" Ausencia : ausencias / docente

    %% ---------- Schemas (app/schemas) ----------
    class LoginRequest {
        <<schema>>
        +str dni
        +str password
    }
    class Token {
        <<schema>>
        +str access_token
        +str token_type
    }
    class UsuarioMe {
        <<schema>>
        +int id
        +str dni
        +Rol rol
        +Optional~PerfilRead~ perfil
    }
    class PerfilRead {
        <<schema>>
        +int id
        +str nombre
        +str apellido
        +str email
    }
    class FcmTokenUpdate {
        <<schema>>
        +str token
    }
    class ClaseDisponible {
        <<schema>>
        +int catedra_id
        +date fecha
        +str materia
        +str comision
        +int dia_semana
        +time hora_inicio
        +time hora_fin
    }
    class AvisoCreate {
        <<schema>>
        +int catedra_id
        +date fecha
    }
    class AvisoDetalle {
        <<schema>>
        +int id
        +date fecha
        +str materia
        +str comision
        +int dia_semana
        +time hora_inicio
        +time hora_fin
        +DocenteResumen docente
        +datetime creado_en
    }
    class DocenteResumen {
        <<schema>>
        +str nombre
        +str apellido
    }
    class MiInscripcion {
        <<schema>>
        +int catedra_id
        +str materia
        +str comision
        +int dia_semana
        +time hora_inicio
        +time hora_fin
        +DocenteResumen docente
    }
    class PersonaCreate {
        <<schema>>
        +str dni
        +str password
        +str nombre
        +str apellido
        +EmailStr email
    }
    class DocenteCreate {
        <<schema>>
    }
    class AlumnoCreate {
        <<schema>>
        +int carrera_id
    }
    class PersonaRead {
        <<schema>>
        +int id
        +str dni
        +str nombre
        +str apellido
        +str email
        +bool activo
    }
    class DocenteRead {
        <<schema>>
    }
    class AlumnoRead {
        <<schema>>
        +int carrera_id
    }

    UsuarioMe --> PerfilRead
    AvisoDetalle --> DocenteResumen
    MiInscripcion --> DocenteResumen
    PersonaCreate <|-- DocenteCreate
    PersonaCreate <|-- AlumnoCreate
    PersonaRead <|-- DocenteRead
    PersonaRead <|-- AlumnoRead

    %% ---------- Services y core ----------
    class auth {
        <<service>>
        +autenticar(session, dni, password) Optional~Usuario~
    }
    class ausencias {
        <<service>>
        +ZONA = America/Argentina/Buenos_Aires
        +ANTICIPACION_MINIMA = 1 hora
        +VENTANA = 7 días
        +ahora() datetime
        +clases_disponibles(session, docente) list~ClaseDisponible~
        +registrar_aviso(session, docente, catedra_id, fecha) Ausencia
        +a_detalle(aviso) AvisoDetalle
        +avisos_del_docente(session, docente, offset, limit) list~AvisoDetalle~
        +avisos_del_alumno(session, alumno, catedra_id, offset, limit) list~AvisoDetalle~
        +avisos_filtrados(session, filtros, offset, limit) list~AvisoDetalle~
    }
    class notificaciones {
        <<service>>
        +programar(session, aviso, detalle, background_tasks) None
        +enviar(notificacion) None
        +asignar_token(session, usuario, token) None
        +advertir_si_falta_configuracion() None
        +abrir_sesion() Session
    }
    class Notificacion {
        <<dataclass>>
        +list~str~ emails
        +list~str~ tokens
        +str asunto
        +str texto
        +str titulo_push
        +str cuerpo_push
    }
    class inscripciones {
        <<service>>
        +inscripciones_vigentes(session, alumno) list~MiInscripcion~
    }
    class personas {
        <<service>>
        +crear(session, modelo, rol, data) Docente o Alumno
        +actualizar(session, perfil, data) Docente o Alumno
        +a_dict(perfil) dict
    }
    class correo {
        <<core>>
        +configurado() bool
        +enviar(destinatarios, asunto, texto) None
    }
    class push {
        <<core>>
        +TANDA = 500
        +configurado() bool
        +enviar(tokens, titulo, cuerpo) list~str~
    }

    auth ..> Usuario : busca por DNI
    ausencias ..> Ausencia : crea y consulta
    ausencias ..> Catedra : consulta
    ausencias ..> ClaseDisponible : devuelve
    ausencias ..> AvisoDetalle : devuelve
    inscripciones ..> MiInscripcion : devuelve
    personas ..> Usuario : crea
    personas ..> PersonaCreate : recibe
    notificaciones ..> Notificacion : arma
    notificaciones ..> correo : usa
    notificaciones ..> push : usa
    notificaciones ..> Usuario : actualiza fcm_token
```

`avisos_filtrados` recibe como parámetros keyword `carrera_id`, `materia_id`, `comision`, `docente_id`, `fecha_desde` y `fecha_hasta`, todos opcionales.

---

## 3. Secuencia: login

`POST /api/v1/auth/login` y después `GET /api/v1/auth/me` (HU-01).

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant C as Cliente (app Android o web)
    participant E as endpoints/auth.py
    participant S as services/auth.py
    participant SEC as core/security.py
    participant DB as PostgreSQL

    U->>C: DNI y contraseña
    C->>E: POST /auth/login {dni, password}
    E->>S: autenticar(session, dni, password)
    S->>DB: SELECT usuario WHERE dni = ?
    DB-->>S: usuario o nada
    alt el DNI no existe
        S->>SEC: verify_password(password, hash ficticio)
        Note right of S: misma demora que un DNI real
        S-->>E: None
    else el DNI existe
        S->>SEC: verify_password(password, usuario.password_hash)
        SEC-->>S: True / False
        S-->>E: usuario si la contraseña es correcta y está activo, si no None
    end
    alt None
        E-->>C: 401 "DNI o contraseña incorrectos"
    else usuario
        E->>SEC: create_access_token(usuario.id, rol)
        SEC-->>E: JWT HS256 {sub, rol, exp}
        E-->>C: 200 {access_token, token_type: "bearer"}
    end

    C->>E: GET /auth/me (Authorization: Bearer)
    E->>SEC: decode_access_token(token)
    alt token inválido o vencido
        E-->>C: 401 "Token inválido o expirado"
    else token válido
        E->>DB: SELECT usuario WHERE id = sub
        alt no existe o inactivo
            E-->>C: 401 "Token inválido o expirado"
        else activo
            E-->>C: 200 {id, dni, rol, perfil}
        end
    end
```

---

## 4. Secuencia: el docente registra un aviso

`POST /api/v1/docente/avisos` (HU-02) con las notificaciones de HU-06. La autenticación (paso 2) es la misma del diagrama anterior: `get_current_user` y `requiere_rol(Rol.docente)`.

```mermaid
sequenceDiagram
    autonumber
    actor D as Docente
    participant APP as App Android
    participant E as endpoints/docente.py
    participant A as services/ausencias.py
    participant N as services/notificaciones.py
    participant DB as PostgreSQL
    participant BT as BackgroundTasks
    participant SMTP as Servidor SMTP (Gmail)
    participant FCM as Firebase (FCM)

    D->>APP: elige una clase de la lista
    APP->>E: POST /docente/avisos {catedra_id, fecha}
    Note over E: token + rol docente + perfil de docente (401/403)
    E->>A: registrar_aviso(session, docente, catedra_id, fecha)
    A->>DB: SELECT catedra WHERE id = catedra_id
    alt no existe o es de otro docente
        A-->>E: CatedraNoEncontrada
        E-->>APP: 404 "Cátedra no encontrada"
    else la fecha no es el dia_semana de la cátedra
        A-->>E: AvisoInvalido
        E-->>APP: 422 "La fecha no corresponde al día de cursada..."
    else fecha + hora_inicio (Argentina) < ahora + 1 h
        A-->>E: AvisoInvalido
        E-->>APP: 422 "Solo se puede avisar hasta 1 hora antes..."
    else fecha + hora_inicio > ahora + 7 días
        A-->>E: AvisoInvalido
        E-->>APP: 422 "Solo se puede avisar sobre clases de los próximos 7 días"
    else válida
        A->>DB: INSERT ausencia (docente_id del docente logueado, estado activo, creado_en UTC) + COMMIT
        alt ya hay aviso (uq_ausencia_catedra_fecha)
            DB-->>A: IntegrityError
            Note over E: manejar_integridad hace rollback
            E-->>APP: 409 "Ya hay un aviso para esa cátedra en esa fecha"
        else guardado
            DB-->>A: ausencia
            A-->>E: ausencia
            E->>A: a_detalle(ausencia)
            A-->>E: AvisoDetalle
            E->>N: programar(session, aviso, detalle, background_tasks)
            N->>DB: alumnos activos con inscripción vigente + admins activos con email
            DB-->>N: emails y fcm_tokens
            N->>BT: add_task(enviar, Notificacion)
            E-->>APP: 201 AvisoDetalle
        end
    end

    Note over BT,FCM: después de enviar la respuesta
    BT->>N: enviar(notificacion)
    N->>SMTP: STARTTLS + login (una conexión)
    loop un mensaje por destinatario
        N->>SMTP: send_message (To: destinatario)
        Note right of SMTP: si falla uno: log y sigue
    end
    loop tandas de hasta 500 tokens
        N->>FCM: send_each_for_multicast(tanda)
        FCM-->>N: resultado por token
    end
    opt hubo tokens UNREGISTERED o SENDER_ID_MISMATCH
        N->>DB: UPDATE usuario SET fcm_token = NULL WHERE fcm_token IN (...)
    end
    FCM-->>APP: push a los celulares de los alumnos
```

Si falla la preparación (`programar`) o cualquier envío (`enviar`), el error se registra en el log y el aviso queda creado igual. Si no hay SMTP o Firebase configurados, ese envío se saltea con un warning.

---

## 5. Componentes

```mermaid
flowchart LR
    subgraph clientes["Clientes (proyectos aparte)"]
        android["📱 App Android<br/>docentes y alumnos"]
        web["🖥️ Frontend web<br/>administrador / preceptor"]
    end

    subgraph docker["Docker Compose"]
        subgraph api["Servicio web: API FastAPI (puerto 8000)"]
            endpoints["endpoints/<br/>HTTP, permisos con requiere_rol"]
            services["services/<br/>reglas de negocio"]
            crud["crud/<br/>acceso a datos"]
            models["models/<br/>SQLModel"]
            core["core/<br/>config, security, correo, push"]
            bg["BackgroundTasks"]
        end
        db[("Servicio db: PostgreSQL 17<br/>puerto 5432, en tu máquina 5433")]
    end

    smtp["✉️ Servidor SMTP (Gmail)<br/>smtplib, STARTTLS, puerto 587"]
    fcm["🔔 Firebase Cloud Messaging<br/>firebase-admin"]

    android -- "HTTP/JSON + JWT<br/>/api/v1/auth, /docente, /alumno" --> endpoints
    web -- "HTTP/JSON + JWT, CORS_ORIGINS<br/>/api/v1/auth, /admin, /docentes, ..." --> endpoints
    endpoints --> services --> crud --> models
    services --> core
    crud -- "Session de core/database.py (psycopg)" --> db
    services -- "programar()" --> bg
    bg --> core
    core -- "correo a alumnos y preceptores" --> smtp
    core -- "push a alumnos (tandas de 500)" --> fcm
    fcm -- "notificación push" --> android
    android -- "PUT /auth/me/fcm-token" --> endpoints
```

| Componente | Tecnología | Notas |
|------------|------------|-------|
| API | FastAPI + SQLModel, Python | Servicio `web` de `docker-compose.yml`. Al arrancar corre `alembic upgrade head`. |
| Base de datos | PostgreSQL 17 | Servicio `db`. Datos en el volumen `pgdata`. |
| App Android | Proyecto aparte | Docentes y alumnos. Recibe push por FCM. |
| Frontend web | Proyecto aparte | Solo `admin`. Su origen va en `CORS_ORIGINS`. |
| Servidor SMTP | `smtplib` (biblioteca estándar) | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. |
| Firebase | `firebase-admin` | `FIREBASE_CREDENTIALS`: ruta al JSON del service account dentro de `secrets/`, fuera de git. |
