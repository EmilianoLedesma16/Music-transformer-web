# ByteBeat — Generador de Acompañamiento Musical con IA

Plataforma web que permite subir una melodía en audio, describirla con texto libre y recibir un acompañamiento musical generado por un Transformer encoder-decoder. Exporta en formato MIDI y MusicXML (partitura de dos pentagramas).

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
- **Generación real de acompañamiento** con MusicTransformer v2 (checkpoint `best_model.pt`)
- Exportación a **MIDI** y **MusicXML** (partitura de dos pentagramas: melodía + acompañamiento)
- Feedback de progreso en tiempo real durante la generación (spinner con mensajes por etapa)
- Almacenamiento de archivos en Supabase Storage
- Panel de administración (`/admin.html`) con manejo de roles (admin/usuario)
- API REST completa con Swagger en `/docs`

### ❌ Pendiente antes de producción

- [ ] **GPU en el servidor** — la generación en CPU tarda 30-60 min; con GPU (T4 o mejor) baja a < 2 min
- [ ] Nginx + HTTPS para producción (reverse proxy frente al API)
- [ ] CORS middleware en el API (necesario si frontend y API están en dominios distintos)
- [ ] Migraciones de DB con Alembic (actualmente `create_all()` no migra tablas existentes)
- [ ] Google OAuth en producción (requiere credenciales de Google Cloud Console)
- [ ] Visor de partitura en el browser (OSMD o Verovio para renderizar MusicXML inline)

---

## Arquitectura

```
Browser
  └── FastAPI (puerto 8000)
        ├── Sirve el frontend estático (frontend/)
        ├── REST API con JWT
        └── Despacha tareas a Celery

Celery Workers (3 en cadena):
  ml_worker            → Clasifica instrumento con CNN14 (PANNs)
  transcription_worker → Convierte audio a MIDI con Basic Pitch
  generation_worker    → Genera acompañamiento con MusicTransformer v2
                         Exporta MIDI + MusicXML y sube a Supabase

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
| `ml_worker` | — | Celery worker — clasificación CNN14 |
| `transcription_worker` | — | Celery worker — audio → MIDI (Basic Pitch) |
| `generation_worker` | — | Celery worker — MusicTransformer v2 (requiere `best_model.pt`) |

---

## Prerrequisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac/Linux)
- Git
- Cuenta en [Supabase](https://supabase.com) (para storage de archivos)
- Checkpoint del modelo: `music-transformer/checkpoints/best_model.pt` (no incluido en el repo — ver abajo)

No se necesita Python local para correr el proyecto — todo corre dentro de Docker.

---

## Instalación desde cero

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/bytebeat.git
cd bytebeat
```

### 2. Configurar el modelo

El directorio `music-transformer/` no está en git (`.gitignore`) porque contiene el checkpoint del modelo (~400 MB). Debe copiarse manualmente:

```
music-transformer/
├── checkpoints/
│   └── best_model.pt          ← copiar aquí el checkpoint v2
└── src/                       ← código fuente del modelo (configurar con el equipo ML)
    ├── model/
    │   ├── config.py
    │   ├── transformer.py
    │   └── inference.py
    ├── data/
    │   └── midi_tokenizer.py
    └── utils/
        └── tokens_to_musicxml.py
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tus valores reales (ver sección [Variables de entorno](#variables-de-entorno)).

Lo mínimo para levantar localmente:
- `JWT_SECRET_KEY` → generar con `openssl rand -hex 32`
- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_BUCKET` → de tu proyecto Supabase

### 4. Crear el bucket en Supabase

1. Ir a [app.supabase.com](https://app.supabase.com) → tu proyecto → **Storage**
2. Crear bucket llamado `bytebeat` → marcarlo como **Public**
3. Copiar la URL del proyecto y el `service_role` key al `.env`

### 5. Buildear las imágenes Docker

> **IMPORTANTE:** buildear una por una para no saturar la RAM.

```bash
docker compose build --no-cache api
docker compose build --no-cache ml_worker
docker compose build --no-cache transcription_worker
docker compose build --no-cache generation_worker
```

Cada build tarda entre 2 y 10 minutos dependiendo de la conexión. El `generation_worker` es el más pesado (instala PyTorch + dependencias ML).

### 6. Levantar el proyecto

```bash
docker compose up -d
```

### 7. Verificar que todo esté corriendo

```bash
docker compose ps
```

Deben aparecer 6 contenedores en estado `running` o `healthy`:
`db`, `redis`, `api`, `ml_worker`, `transcription_worker`, `generation_worker`

### 8. Abrir en el browser

```
http://localhost:8000
```

### Esto lo sigue en prueba creo que funciona parcialmente pero hay un bug en el localStorage
### 9. Crear el primer usuario administrador

1. Registrarse en `/register.html`
2. Ir a `http://localhost:8000/docs` (Swagger UI)
3. Autenticarse con el token JWT recibido al registrarse
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
| `STUB_GENERATION` | Bypasea el modelo (solo para pruebas sin checkpoint) | `false` |

---

## Tiempos de procesamiento esperados

| Etapa | CPU (desarrollo) | GPU recomendado (producción) |
|---|---|---|
| Clasificación CNN14 (1.ª vez) | 10-15 min (descarga 325 MB) | igual |
| Clasificación CNN14 (siguientes) | 5-15 seg | 5-15 seg |
| Transcripción Basic Pitch | 30-60 seg | 30-60 seg |
| Generación MusicTransformer (1024 tokens) | **30-60 min** | **1-2 min** |

La generación es el cuello de botella. Para producción se recomienda una instancia con GPU (NVIDIA T4 o superior). El `generation_worker` es el único contenedor que se beneficia de GPU; el resto puede correr en CPU.

---

## Deploy en producción (con GPU)

La arquitectura de Celery permite separar el `generation_worker` en una máquina distinta con GPU. El resto de servicios (API, workers ligeros, Redis, PostgreSQL) pueden correr en un VPS CPU estándar (~$5-10/mes).

### Opción simple: todo en la máquina GPU

```bash
# En el servidor con GPU:
git clone <repo> && cd bytebeat
cp .env.example .env  # editar con credenciales de producción
docker compose up -d

# Exponer públicamente (sin dominio propio):
ngrok http 8000
```

### Para HTTPS con dominio propio

Agregar Nginx al `docker-compose.yml` como reverse proxy y usar Cloudflare como proxy DNS (HTTPS automático sin Certbot).

### Para el `generation_worker` en GPU cloud (RunPod, Lambda Labs)

El worker solo necesita apuntar al mismo Redis:

```env
CELERY_BROKER_URL=redis://<ip-del-servidor-principal>:6379/0
CELERY_RESULT_BACKEND=redis://<ip-del-servidor-principal>:6379/0
```

---

## Comandos útiles

```bash
# Ver logs de un servicio
docker compose logs api --tail=50
docker compose logs ml_worker --tail=50
docker compose logs generation_worker --tail=50

# Reiniciar un servicio sin rebuildar
docker compose restart generation_worker

# Parar todo (conserva la DB)
docker compose down

# Parar todo y BORRAR la DB (reset completo — necesario al cambiar el schema)
docker compose down -v

# Entrar al contenedor
docker compose exec api bash
docker compose exec generation_worker bash

# Ver la DB con psql
docker compose exec db psql -U mtuser -d music_transformer

# Recuperar archivos generados (cuando Supabase no está configurado)
docker compose cp generation_worker:/app/data/processed/output_midis/ ./output_midis/
docker compose cp generation_worker:/app/data/output/musicxml/ ./output_xml/
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

```javascript
API.login(email, password)
API.register(name, email, password)
API.getMe()                          // GET /me
API.parsePrompt(text)                // POST /parse-prompt — NLP del prompt
API.submitProcess(formData)          // POST /process — subir audio e iniciar job
API.pollJob(jobId)                   // GET /process/{id} — estado del job
API.listCreaciones()                 // GET /creaciones
API.deleteCreacion(id)               // DELETE /creaciones/{id}
API.adminListUsers()                 // GET /admin/users
API.adminSetRole(userId, role)       // PATCH /admin/users/{id}/role
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
├── .env                         # NO se sube a git (en .gitignore)
├── .env.example                 # Plantilla con variables vacías
├── frontend/                    # Frontend estático (bind mount en Docker)
├── music-transformer/           # NO está en git (.gitignore)
│   ├── checkpoints/
│   │   └── best_model.pt        # Checkpoint v2 del modelo (~400 MB)
│   └── src/                     # Código fuente del modelo ML
└── services/
    ├── api/                     # FastAPI — API REST + auth + sirve el frontend
    │   ├── main.py
    │   ├── models.py            # SQLAlchemy: User, Creacion
    │   ├── schemas.py           # Pydantic: respuestas de la API
    │   ├── prompt_parser.py     # NLP keyword-based con detección de negación
    │   ├── auth/                # JWT + Google OAuth
    │   ├── storage/             # Cliente Supabase
    │   └── Dockerfile
    ├── ml_worker/               # Celery worker — clasificación CNN14
    ├── transcription_worker/    # Celery worker — audio → MIDI (Basic Pitch)
    └── generation_worker/       # Celery worker — MusicTransformer v2
        └── orchestrator.py      # Pipeline completo: tokenizar → generar → exportar → subir
```

---

## Solución de problemas frecuentes

**El build se interrumpe o reinicia la PC**
→ Buildear los servicios uno por uno (ver paso 5 de instalación). No usar `docker compose build` sin especificar servicio.

**"parent snapshot does not exist" al buildear**
→ Caché de Docker corrompido. Ejecutar `docker builder prune -f` y reintentar.

**"Failed to fetch" en el browser**
→ Hacer hard refresh: `Ctrl+Shift+R`. Los archivos JS se cachean en el browser.

**El primer job tarda 10-15 min en VALIDATING**
→ El `ml_worker` descarga el checkpoint CNN14 (~325 MB) la primera vez. Los jobs siguientes son rápidos.

**La generación tarda 30-60 minutos**
→ Normal en CPU. Para producción se requiere GPU (ver sección de deploy).

**Columna `progress_detail` o `energy` no existe en la DB**
→ La DB fue creada con una versión anterior del schema. Ejecutar `docker compose down -v` y volver a levantar. Esto borra todos los datos locales.

**Los archivos MIDI/XML se generaron pero no hay links de descarga**
→ Las credenciales de Supabase en `.env` son incorrectas. Los archivos quedan en disco dentro del contenedor. Recuperarlos con `docker compose cp` (ver sección de comandos útiles).

**`FileNotFoundError: best_model.pt`**
→ El checkpoint no está en `music-transformer/checkpoints/best_model.pt`. Ver paso 2 de instalación.


# Para omi 
1. Prerrequisitos del sistema (una sola vez)

Instalar los drivers de NVIDIA y el toolkit para Docker:


# Verificar que la GPU es reconocida
nvidia-smi
Si ese comando funciona, los drivers están bien. Solo falta el nvidia-container-toolkit:


# Ubuntu/Debian
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
2. Clonar y configurar el proyecto


git clone <url-del-repo>
cd music-transformer-web
cp .env.example .env
# editar .env con las credenciales de Supabase y JWT_SECRET_KEY
Luego copiar manualmente el checkpoint y el código del modelo:


music-transformer/checkpoints/best_model.pt
music-transformer/src/  ← archivos del modelo ML
3. Buildear los contenedores


docker compose build --no-cache api
docker compose build --no-cache ml_worker
docker compose build --no-cache transcription_worker
docker compose build --no-cache generation_worker   # este tarda más (~4 GB imagen PyTorch+CUDA)
4. Levantar


docker compose up -d
5. Verificar que el generation_worker ve la GPU


docker compose exec generation_worker python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
Debe imprimir True y el nombre de la GPU, por ejemplo NVIDIA GeForce RTX 3080.

6. Abrir en el browser


http://localhost:8000
A partir de ahí el flujo es el mismo que en CPU pero la generación tarda 1-2 minutos en vez de 30-60.