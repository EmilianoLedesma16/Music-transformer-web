# ByteBeat — Guía de Despliegue

## 1. Pre-requisitos locales

| Herramienta | Versión mínima |
|---|---|
| Docker Desktop | 24+ |
| Docker Compose | incluido en Docker Desktop |
| Git | cualquiera |

---

## 2. Cuentas externas que necesitas crear (gratuitas)

### 2a. Supabase Storage (para guardar archivos)
1. Ir a https://app.supabase.com y crear una cuenta
2. Crear un **nuevo proyecto**
3. Ir a **Storage → New Bucket**
   - Name: `bytebeat`
   - Public bucket: ✅ activado
4. Copiar de **Project Settings → API**:
   - `Project URL` → `SUPABASE_URL`
   - `anon public key` → `SUPABASE_KEY`

### 2b. Google OAuth (para "Login con Google")
1. Ir a https://console.cloud.google.com
2. Crear un proyecto o usar uno existente
3. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
4. Copiar `Client ID` y `Client Secret`

*(Si no necesitas Google OAuth de momento, deja esas variables en blanco — el login con email/password funcionará igual)*

---

## 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tus valores reales:

```env
POSTGRES_PASSWORD=una_password_segura
DATABASE_URL=postgresql://mtuser:una_password_segura@db:5432/music_transformer

JWT_SECRET_KEY=<resultado de: openssl rand -hex 32>

GOOGLE_CLIENT_ID=<tu-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<tu-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

SUPABASE_URL=https://<tu-proyecto>.supabase.co
SUPABASE_KEY=<anon-key>
SUPABASE_BUCKET=bytebeat

FRONTEND_URL=http://localhost:8000
```

> **Nota**: `CELERY_BROKER_URL` y `CELERY_RESULT_BACKEND` ya tienen defaults correctos en docker-compose.yml.

---

## 4. Checkpoint del modelo (OBLIGATORIO)

El `generation_worker` necesita el archivo `best_model.pt` entrenado.

```
music-transformer-web/
└── music-transformer/
    └── checkpoints/
        └── best_model.pt   ← colocar aquí
```

Este archivo se monta en el volumen `model_checkpoints` y el worker lo busca en `/app/checkpoints/best_model.pt`.

Si aún no existe el checkpoint, el generation_worker fallará con un error claro en los logs.

---

## 5. Levantar todo localmente

```bash
# Primera vez (construye todas las imágenes)
docker compose up --build

# Siguientes veces
docker compose up
```

> ⚠️ El primer `docker compose up --build` tarda **10-20 minutos** porque descarga:
> - PyTorch (~800 MB) para ml_worker y generation_worker
> - TensorFlow CPU (~500 MB) para transcription_worker
> - CNN14 weights (~325 MB) en el primer request al ml_worker

### Verificar que todo está corriendo:

```bash
docker compose ps
# Todos deben estar "running" o "healthy"
```

### Ver logs de un servicio específico:

```bash
docker compose logs -f api
docker compose logs -f ml_worker
docker compose logs -f transcription_worker
docker compose logs -f generation_worker
```

---

## 6. Probar el sistema

### Frontend
Abre tu navegador en: **http://localhost:8000**

### Flujo completo:
1. Regístrate con email/password (o usa Google)
2. Ve a "Nueva Creación"
3. Sube un archivo `.wav` o `.mp3` con piano, guitarra o bajo
4. Selecciona género, mood e instrumento a generar
5. El panel de progreso muestra cada etapa en tiempo real
6. Al terminar (~30s), descarga el MIDI y la partitura XML

### API directa (Swagger UI):
http://localhost:8000/docs

---

## 7. Arquitectura y flujo de datos

```
Usuario (browser)
    │
    ▼
[api :8000]  ──POST /process──▶  Redis (cola ml_queue)
    │                                    │
    │                                    ▼
    │                           [ml_worker]
    │                           CNN14 classify_instrument()
    │                           Si válido → cola transcription_queue
    │                                    │
    │                                    ▼
    │                           [transcription_worker]
    │                           Basic Pitch: audio → MIDI
    │                           → cola generation_queue
    │                                    │
    │                                    ▼
    │                           [generation_worker]
    │                           MusicTransformer inference
    │                           Sube MIDI + XML → Supabase
    │                           UPDATE creaciones SET status=COMPLETED
    │
    ◀──GET /process/{id}── browser (polling cada 3s)
```

Todos los archivos temporales viajan por el volumen Docker compartido `shared_data` montado en `/app/data`.

---

## 8. Despliegue en producción (Railway)

Railway soporta Docker Compose y tiene tier gratuito.

### Pasos:
1. Crear cuenta en https://railway.app
2. Instalar CLI: `npm install -g @railway/cli`
3. `railway login`
4. En la raíz del proyecto: `railway init`
5. `railway up`
6. En el dashboard de Railway, añadir las variables de entorno del `.env`
7. Cambiar `GOOGLE_REDIRECT_URI` y `FRONTEND_URL` al dominio asignado por Railway
8. Para la base de datos: usar **Supabase PostgreSQL** (gratis 500 MB)
   - Crear proyecto en app.supabase.com → Settings → Database → Connection string
   - Pegar esa URL en `DATABASE_URL`

### Limitaciones del tier gratuito Railway:
- 500 horas/mes de CPU (suficiente para desarrollo/demo)
- Sin GPU — la inferencia corre en CPU (~45-60s en lugar de ~25s)
- Para GPU en producción: Vast.ai o RunPod (~0.20 USD/hora)

---

## 9. Solución de problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ml_worker` muere al clasificar | CNN14 no descargó | Ver logs: `docker compose logs ml_worker`. Necesita acceso a internet en el primer arranque |
| `generation_worker` error "Checkpoint no encontrado" | Falta best_model.pt | Colocar el archivo en `music-transformer/checkpoints/` |
| `pretty_midi` ImportError | setuptools versión alta | El Dockerfile ya lo pinna; reconstruir con `docker compose build --no-cache transcription_worker` |
| Error 401 en todas las rutas | JWT_SECRET_KEY no configurado | Verificar que `.env` tiene la variable correctamente |
| Supabase upload falla | Credenciales o bucket incorrecto | El sistema continúa sin URLs de Supabase; verificar logs del worker |
| `basic_pitch` error TF | TensorFlow no instalado | Reconstruir: `docker compose build --no-cache transcription_worker` |

---

## 10. Resumen de puertos y servicios

| Servicio | Puerto | Descripción |
|---|---|---|
| api | 8000 | FastAPI + frontend estático |
| db | 5432 | PostgreSQL (solo acceso local) |
| redis | 6379 | Broker Celery (solo acceso local) |
| ml_worker | — | Cola ml_queue (CNN14) |
| transcription_worker | — | Cola transcription_queue (Basic Pitch) |
| generation_worker | — | Cola generation_queue (MusicTransformer) |
