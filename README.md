# ByteBeat — Generador de Acompañamiento Musical con IA

Plataforma web que permite subir una melodía en audio, describirla con texto libre y recibir un acompañamiento musical generado por un Transformer encoder-decoder. Exporta en formato MIDI y MusicXML.

---

## Estado actual del proyecto

### ✅ Funciona completamente
- Registro e inicio de sesión con email/contraseña
- Autenticación JWT (7 días)
- Dashboard con lista de creaciones y polling de estado en tiempo real
- Wizard de 3 pasos para nueva creación (audio → parámetros → estado)
- Prompt de personalización en texto libre (NLP con detección de negación y confianza)
- Clasificación de instrumento con CNN14 (PANNs — descarga ~325 MB en el primer job)
- Transcripción audio → MIDI con Basic Pitch
- Almacenamiento de audios en Supabase Storage
- Panel de administración (`/admin.html`) con manejo de roles (admin/usuario)
- API REST completa con Swagger en `/docs`

### ⚠️ Hardcodeado (stub temporal)
- **Generación musical**: el pipeline completo corre (CNN14 + Basic Pitch) pero la inferencia del Transformer está bypasada con `STUB_GENERATION=true`. El job termina como COMPLETED sin generar MIDI/XML de salida. Esto es intencional hasta que el checkpoint del modelo v2 esté disponible.

### ❌ Pendiente antes de producción
- [ ] CORS middleware en el API (necesario si frontend y API están en dominios distintos)
- [ ] Migraciones de DB con Alembic (actualmente `create_all()` no migra tablas existentes)
- [ ] Checkpoint v2 del modelo (`best_model.pt`) — lo genera el compañero ML
- [ ] Despliegue en Railway (o similar) con DB y Redis administrados
- [ ] Deshabilitar `STUB_GENERATION` una vez que el modelo esté disponible
- [ ] Google OAuth en producción (requiere credenciales de Google Cloud Console)

---

## Arquitectura

```
Browser
  └── FastAPI (puerto 8000)
        ├── Sirve el frontend estático (frontend/)
        ├── REST API con JWT
        └── Despacha tareas a Celery

Celery Workers (3 en cadena):
  ml_worker          → Clasifica instrumento con CNN14
  transcription_worker → Convierte audio a MIDI con Basic Pitch
  generation_worker  → Genera acompañamiento con MusicTransformer (stub activo)

Infraestructura:
  PostgreSQL  → Base de datos (usuarios, creaciones, estado)
  Redis       → Broker de mensajes para Celery
  Supabase    → Almacenamiento de archivos (audio input, MIDI, XML)
```

### Servicios Docker
| Servicio | Puerto | Descripción |
|---|---|---|
| `api` | 8000 | FastAPI + frontend estático |
| `db` | 5432 | PostgreSQL 15 |
| `redis` | 6379 | Redis 7 |
| `ml_worker` | — | Celery worker (CNN14) |
| `transcription_worker` | — | Celery worker (Basic Pitch) |
| `generation_worker` | — | Celery worker (MusicTransformer, stub) |

---

## Prerrequisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac/Linux)
- Git
- Cuenta en [Supabase](https://supabase.com) (para storage de archivos)

No se necesita Python local para correr el proyecto — todo corre dentro de Docker.

---

## Instalación desde cero

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/bytebeat.git
cd bytebeat
```

### 2. Configurar variables de entorno

```bash
# Copiar la plantilla
cp .env.example .env
```

Editar `.env` con tus valores reales (ver sección [Variables de entorno](#variables-de-entorno)).

Lo mínimo para levantar localmente:
- `JWT_SECRET_KEY` → generar con `openssl rand -hex 32`
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_BUCKET` → de tu proyecto Supabase

### 3. Crear el bucket en Supabase

1. Ir a [app.supabase.com](https://app.supabase.com) → tu proyecto → **Storage**
2. Crear bucket llamado `bytebeat` → marcarlo como **Public**
3. Copiar la URL del proyecto y el `service_role` key al `.env`

### 4. Buildear las imágenes Docker

> **IMPORTANTE:** buildear una por una para no saturar la RAM.

```bash
docker compose build --no-cache api
docker compose build --no-cache ml_worker
docker compose build --no-cache transcription_worker
docker compose build --no-cache generation_worker
```

Cada build tarda entre 2 y 10 minutos dependiendo de la conexión. El `ml_worker` es el más pesado (descarga librerías de ML).

### 5. Levantar el proyecto

```bash
docker compose up -d
```

### 6. Verificar que todo esté corriendo

```bash
docker compose ps
```

Deben aparecer 6 contenedores en estado `running` o `healthy`:
`db`, `redis`, `api`, `ml_worker`, `transcription_worker`, `generation_worker`

### 7. Abrir en el browser

```
http://localhost:8000
```

### 8. Crear el primer usuario administrador

1. Registrarse en `/register.html`
2. Ir a `http://localhost:8000/docs` (Swagger UI)
3. Autenticarse con el token JWT que se recibió al registrarse
4. Ejecutar `PATCH /admin/users/1/role` con body `{"role": "admin"}`
5. Recargar el dashboard → aparece el botón **Admin**

---

## Variables de entorno

| Variable | Descripción | Ejemplo |
|---|---|---|
| `POSTGRES_PASSWORD` | Contraseña de la DB local | `changeme_local` |
| `DATABASE_URL` | URL completa de conexión a PostgreSQL | `postgresql://mtuser:pass@db:5432/music_transformer` |
| `CELERY_BROKER_URL` | URL de Redis para Celery | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | URL de Redis para resultados | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | Clave secreta para firmar tokens | *(generar con `openssl rand -hex 32`)* |
| `JWT_EXPIRE_MINUTES` | Duración del token en minutos | `10080` (7 días) |
| `GOOGLE_CLIENT_ID` | ID de app Google OAuth | *(opcional)* |
| `GOOGLE_CLIENT_SECRET` | Secret de app Google OAuth | *(opcional)* |
| `GOOGLE_REDIRECT_URI` | Callback de Google OAuth | `http://localhost:8000/auth/google/callback` |
| `SUPABASE_URL` | URL del proyecto Supabase | `https://xxxxx.supabase.co` |
| `SUPABASE_KEY` | Service role key de Supabase | *(desde Settings → API)* |
| `SUPABASE_BUCKET` | Nombre del bucket de storage | `bytebeat` |
| `FRONTEND_URL` | URL base del frontend | `http://localhost:8000` |
| `STUB_GENERATION` | Activa/desactiva el stub del modelo | `true` (hasta tener el checkpoint) |

---

## Comandos útiles

```bash
# Ver logs de un servicio
docker compose logs api --tail=50
docker compose logs ml_worker --tail=50
docker compose logs generation_worker --tail=50

# Reiniciar un servicio sin rebuildar
docker compose restart api

# Parar todo (conserva la DB)
docker compose down

# Parar todo y BORRAR la DB (reset completo)
docker compose down -v

# Entrar al contenedor de la API
docker compose exec api bash

# Ver la DB con psql
docker compose exec db psql -U mtuser -d music_transformer
```

---

## Guía para desarrollo del frontend

El frontend está en `frontend/` y se sirve como archivos estáticos desde el API. Está montado como **bind mount** en Docker, lo que significa que **los cambios en los archivos se reflejan inmediatamente** sin necesidad de rebuildar Docker.

### Estructura del frontend

```
frontend/
├── index.html          # Login
├── register.html       # Registro
├── dashboard.html      # Lista de creaciones del usuario
├── create.html         # Wizard de nueva creación (3 pasos)
├── admin.html          # Panel de administración (solo admins)
└── static/
    ├── css/
    │   └── app.css     # Estilos globales (tema oscuro tipo madera)
    ├── js/
    │   ├── auth.js     # Manejo de token JWT en localStorage
    │   ├── api.js      # Cliente HTTP para todos los endpoints
    │   ├── dashboard.js # Lógica del dashboard (cards, polling, delete)
    │   ├── create.js   # Lógica del wizard y parse-prompt
    │   └── piano.js    # Animación del piano decorativo en login/registro
    └── img/
        └── logo.png
```

### Flujo de autenticación

Todos los endpoints del API (excepto `/auth/login` y `/auth/register`) requieren un header `Authorization: Bearer <token>`. El token se guarda en `localStorage` bajo la clave `bb_token`.

- `Auth.requireAuth()` — redirige al login si no hay token
- `Auth.redirectIfLoggedIn()` — redirige al dashboard si ya está logueado
- `Auth.logout()` — borra el token y redirige al login

### API client (`api.js`)

Todos los requests al backend pasan por el objeto `API`:

```javascript
API.login(email, password)
API.register(name, email, password)
API.getMe()                          // GET /me — perfil del usuario autenticado
API.parsePrompt(text)                // POST /parse-prompt — NLP del prompt
API.submitProcess(formData)          // POST /process — subir audio e iniciar job
API.pollJob(jobId)                   // GET /process/{id} — estado del job
API.listCreaciones()                 // GET /creaciones — lista del usuario
API.deleteCreacion(id)               // DELETE /creaciones/{id}
API.adminListUsers()                 // GET /admin/users — solo admins
API.adminSetRole(userId, role)       // PATCH /admin/users/{id}/role — solo admins
```

### Workflow para editar el frontend

1. Con `docker compose up -d` corriendo, editar cualquier archivo en `frontend/`
2. Hacer **hard refresh** en el browser: `Ctrl+Shift+R` (Windows) / `Cmd+Shift+R` (Mac)
3. Los cambios se ven inmediatamente — no hay que rebuildar Docker

### Tecnologías del frontend

- **Bootstrap 5.3** (CDN) — grid, componentes, utilidades
- **Bootstrap Icons 1.11** (CDN) — iconografía
- **Vanilla JS** — sin frameworks, sin bundler
- **CSS custom** — variables `--wood-amber`, clases `.card-glass`, `.btn-wood`, `.navbar-wood`

---

## API Endpoints

La documentación interactiva completa está en `http://localhost:8000/docs` (Swagger UI).

| Método | Endpoint | Descripción | Auth |
|---|---|---|---|
| POST | `/auth/register` | Registro con email+contraseña | No |
| POST | `/auth/login` | Login, devuelve JWT | No |
| GET | `/auth/google` | Iniciar Google OAuth | No |
| GET | `/me` | Perfil del usuario actual | Sí |
| POST | `/parse-prompt` | Texto libre → parámetros musicales | Sí |
| POST | `/process` | Subir audio e iniciar generación | Sí |
| GET | `/process/{id}` | Estado de un job (para polling) | Sí |
| GET | `/creaciones` | Lista de creaciones del usuario | Sí |
| DELETE | `/creaciones/{id}` | Borrar creación y archivos | Sí |
| GET | `/admin/users` | Listar todos los usuarios | Admin |
| PATCH | `/admin/users/{id}/role` | Cambiar rol de usuario | Admin |

---

## Estructura del proyecto

```
bytebeat/
├── docker-compose.yml
├── .env                    # NO se sube a git (en .gitignore)
├── .env.example            # Plantilla con variables vacías
├── frontend/               # Frontend estático (bind mount en Docker)
└── services/
    ├── api/                # FastAPI — API REST + auth + sirve el frontend
    │   ├── main.py
    │   ├── models.py       # SQLAlchemy: User, Creacion
    │   ├── schemas.py      # Pydantic: respuestas de la API
    │   ├── prompt_parser.py # NLP keyword-based con detección de negación
    │   ├── auth/           # JWT + Google OAuth
    │   ├── storage/        # Cliente Supabase
    │   └── Dockerfile
    ├── ml_worker/          # Celery worker — clasificación CNN14
    ├── transcription_worker/ # Celery worker — audio→MIDI (Basic Pitch)
    └── generation_worker/  # Celery worker — MusicTransformer (stub activo)
        └── orchestrator.py # Pipeline de generación (STUB_GENERATION controla el modo)
```

---

## Integración del modelo de generación (pendiente)

Cuando el checkpoint v2 esté disponible (`best_model.pt`), los pasos son:

1. Copiar los archivos del modelo al directorio `music-transformer/src/` (se monta como volumen)
2. Copiar el checkpoint a `music-transformer/checkpoints/best_model.pt`
3. Restaurar dependencias ML en `services/generation_worker/requirements.txt`:
   ```
   torch==2.3.0
   torchaudio==2.3.0
   pretty_midi==0.2.10
   music21==9.3.0
   numpy==1.26.4
   tqdm
   ```
4. En `docker-compose.yml`, cambiar `STUB_GENERATION: "true"` → `STUB_GENERATION: "false"`
5. Rebuildar solo el generation_worker: `docker compose build --no-cache generation_worker`
6. `docker compose up -d`

El resto de la plataforma no requiere cambios.

---

## Solución de problemas frecuentes

**El build se interrumpe o reinicia la PC**
→ Buildear los servicios uno por uno (ver paso 4 de instalación). No usar `docker compose build` sin especificar servicio.

**"parent snapshot does not exist" al buildear**
→ Caché de Docker corrompido. Ejecutar `docker builder prune -f` y reintentar.

**"Failed to fetch" en el browser**
→ Hacer hard refresh: `Ctrl+Shift+R`. Los archivos JS se cachean en el browser.

**El primer job tarda mucho (5-10 min)**
→ El `ml_worker` descarga el checkpoint CNN14 (~325 MB) la primera vez. Los jobs siguientes son rápidos.

**La columna "role" o "energy" no existe en la DB**
→ La DB fue creada con una versión anterior del schema. Ejecutar `docker compose down -v` y volver a levantar (esto borra todos los datos).
