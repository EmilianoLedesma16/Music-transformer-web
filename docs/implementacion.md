# Implementación del Sistema ByteBeat

## Índice

1. [Visión General de la Arquitectura](#1-visión-general-de-la-arquitectura)
2. [Modelo de Base de Datos](#2-modelo-de-base-de-datos)
3. [API REST](#3-api-rest)
4. [Parser de Lenguaje Natural](#4-parser-de-lenguaje-natural)
5. [Sistema de Autenticación](#5-sistema-de-autenticación)
6. [Pipeline de Procesamiento Asíncrono](#6-pipeline-de-procesamiento-asíncrono)
   - 6.1 [Worker de Clasificación (ml_worker)](#61-worker-de-clasificación-ml_worker)
   - 6.2 [Worker de Transcripción (transcription_worker)](#62-worker-de-transcripción-transcription_worker)
   - 6.3 [Worker de Generación (generation_worker)](#63-worker-de-generación-generation_worker)
7. [Modelo MusicTransformer](#7-modelo-musictransformer)
   - 7.1 [Arquitectura del Transformer](#71-arquitectura-del-transformer)
   - 7.2 [Esquema de Tokenización](#72-esquema-de-tokenización)
   - 7.3 [Inferencia y Muestreo](#73-inferencia-y-muestreo)
8. [Generación de MusicXML](#8-generación-de-musicxml)
9. [Almacenamiento en la Nube](#9-almacenamiento-en-la-nube)
10. [Infraestructura de Contenedores](#10-infraestructura-de-contenedores)

---

## 1. Visión General de la Arquitectura

El sistema ByteBeat implementa una arquitectura de microservicios orientada a eventos. El usuario interactúa exclusivamente con una API REST central; el procesamiento pesado se delega a tres trabajadores especializados que se comunican de forma asíncrona a través de colas de mensajes.

```
Usuario
  │
  ▼
[FastAPI — Puerto 8000]
  │  Guarda el audio en volumen compartido
  │  Crea registro en PostgreSQL (status=PENDING)
  │  Despacha tarea → ml_queue
  │
  ├──► [ml_worker]  ─────────────────────────────────────────────────────────────
  │       Clasificación del instrumento con CNN14 (PANNs)                        │
  │       Valida que sea piano / guitarra / bajo                                 │
  │       Actualiza BD (status=TRANSCRIBING)                                     │
  │       Encadena tarea → transcription_queue                                   │
  │                                                                              │
  │    [transcription_worker]  ──────────────────────────────────────────────────┤
  │       Convierte audio a MIDI con Basic Pitch                                 │
  │       Guarda MIDI en volumen compartido                                      │
  │       Actualiza BD (status=GENERATING)                                       │
  │       Encadena tarea → generation_queue                                      │
  │                                                                              │
  │    [generation_worker]  ─────────────────────────────────────────────────────┘
  │       Parsea MIDI con pretty_midi
  │       Tokeniza melodía (encoder)
  │       Carga checkpoint MusicTransformer
  │       Inferencia autoregresiva (decoder)
  │       Tokens → MIDI de acompañamiento
  │       Tokens → MusicXML (dos pentagramas)
  │       Sube MIDI y XML a Supabase Storage
  │       Actualiza BD (status=COMPLETED, urls)
  │
  ▼
[Frontend estático — servido por FastAPI]
  Polling de /process/{job_id} cada 3 s
  Descarga MIDI/XML desde URLs de Supabase
```

**Componentes de infraestructura:**

| Componente | Tecnología | Rol |
|---|---|---|
| API | FastAPI 0.111 + Uvicorn | Punto de entrada REST, sirve el frontend |
| Cola de mensajes | Redis 7 | Broker y backend de resultados de Celery |
| Base de datos | PostgreSQL 15 | Persistencia de usuarios y creaciones |
| Almacenamiento | Supabase Storage | Archivos de audio, MIDI y MusicXML |
| Workers | Celery 5.4 | Procesamiento asíncrono distribuido |
| Contenedores | Docker + Docker Compose | Orquestación local y en producción |

---

## 2. Modelo de Base de Datos

La base de datos contiene dos entidades principales: `users` y `creaciones`. El esquema se define mediante SQLAlchemy ORM y se crea automáticamente al iniciar la API (`Base.metadata.create_all`).

### Tabla `users`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | Identificador único |
| `email` | String(255) UNIQUE | Correo electrónico |
| `name` | String(255) | Nombre para mostrar |
| `password_hash` | String(255) | Hash bcrypt; NULL para usuarios Google OAuth |
| `google_id` | String(128) UNIQUE | ID de Google; NULL para usuarios con contraseña |
| `avatar_url` | String(512) | URL de foto de perfil (Google OAuth) |
| `role` | String(16) | `"user"` o `"admin"` |
| `created_at` | DateTime | Timestamp de registro |

El diseño de la tabla `users` soporta dos métodos de autenticación en paralelo: credenciales propias y Google OAuth. Un usuario puede tener uno o ambos métodos activos.

### Tabla `creaciones`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | Identificador único |
| `user_id` | Integer FK → users | Propietario de la creación |
| `created_at` | DateTime | Timestamp de creación |
| `updated_at` | DateTime | Última actualización automática |
| `original_filename` | String(255) | Nombre original del archivo subido |
| `audio_path` | String(512) | Ruta local en el volumen compartido |
| `audio_input_url` | String(512) | URL pública en Supabase |
| `genre` | String(32) | Género musical solicitado |
| `mood` | String(32) | Estado de ánimo solicitado |
| `energy` | String(8) | Nivel de energía (`LOW`, `MED`, `HIGH`) |
| `instrument` | String(32) | Instrumento de acompañamiento |
| `temperature` | Float | Temperatura de muestreo del decoder (0.0–1.0) |
| `top_p` | Float | Parámetro nucleus sampling (0.0–1.0) |
| `status` | Enum | Estado actual del procesamiento |
| `celery_task_id` | String(128) | ID de la tarea Celery activa |
| `detected_instrument` | String(64) | Instrumento detectado por CNN14 |
| `midi_path` | String(512) | Ruta local del MIDI transcrito |
| `midi_output_url` | String(512) | URL pública del MIDI generado en Supabase |
| `xml_output_url` | String(512) | URL pública del MusicXML en Supabase |
| `notes_generated` | Integer | Número de notas en el acompañamiento |
| `duration_seconds` | Float | Duración del acompañamiento en segundos |
| `error_message` | Text | Mensaje de error si `status = FAILED` |
| `progress_detail` | Text | Descripción del paso actual del pipeline |

### Estados del procesamiento

El campo `status` refleja el progreso a lo largo del pipeline:

```
PENDING → VALIDATING → TRANSCRIBING → GENERATING → COMPLETED
                                                  ↘ FAILED
```

El campo `progress_detail` complementa `status` con descripciones en lenguaje natural del paso específico que se está ejecutando (por ejemplo, `"Tokenizando melodía de entrada…"`), permitiendo mostrar retroalimentación granular al usuario sin definir un mayor número de estados en el enum.

---

## 3. API REST

La API se implementa con FastAPI y expone los siguientes endpoints:

### Endpoints de autenticación

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/register` | Registro con email y contraseña |
| POST | `/auth/login` | Login con email y contraseña |
| GET | `/auth/google` | Inicia flujo Google OAuth 2.0 |
| GET | `/auth/google/callback` | Callback de Google OAuth |

### Endpoints de usuario

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/me` | Perfil del usuario autenticado |

### Endpoints de procesamiento

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/parse-prompt` | Texto libre → parámetros musicales (NLP) |
| POST | `/process` | Sube audio e inicia el pipeline |
| GET | `/process/{job_id}` | Polling de estado de una creación |
| GET | `/creaciones` | Lista todas las creaciones del usuario |
| DELETE | `/creaciones/{id}` | Elimina creación y sus archivos de Supabase |

### Endpoints de administración

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/admin/users` | Lista todos los usuarios (requiere rol `admin`) |
| PATCH | `/admin/users/{id}/role` | Cambia el rol de un usuario |

### Flujo del endpoint `/process`

El endpoint principal recibe un archivo de audio junto con los parámetros musicales como datos de formulario multipart. El procesamiento sigue estos pasos:

1. **Validación de parámetros:** Se verifican los valores de `genre`, `mood`, `energy` e `instrument` contra conjuntos de valores válidos predefinidos. El formato del archivo se valida por extensión (`.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`).

2. **Persistencia del audio:** El archivo se guarda en el volumen compartido Docker con un UUID como nombre, garantizando la unicidad sin colisiones.

3. **Registro en base de datos:** Se crea un registro `Creacion` con todos los parámetros y `status = PENDING`.

4. **Despacho asíncrono:** Se envía una tarea a `ml_queue` usando `celery_app.send_task()`. El ID de la tarea Celery se almacena en la base de datos.

5. **Respuesta inmediata:** El endpoint retorna el objeto `Creacion` con `status = VALIDATING`, sin esperar el resultado del procesamiento. El cliente realiza polling sobre `/process/{job_id}`.

Los valores de temperatura (`temperature`) y `top_p` permiten al usuario controlar el nivel de aleatoriedad del muestreo durante la generación. Valores de temperatura cercanos a 1.0 producen resultados más variados; valores bajos hacen el muestreo más determinista.

---

## 4. Parser de Lenguaje Natural

El módulo `prompt_parser.py` implementa un analizador léxico basado en diccionarios de palabras clave que convierte texto libre en cuatro parámetros musicales estructurados: género, estado de ánimo, nivel de energía e instrumento.

### Normalización del texto

Antes del análisis, el texto se normaliza eliminando acentos y diacríticos mediante NFKD, convirtiéndolo a minúsculas y eliminando caracteres no alfanuméricos. Esta normalización permite reconocer tanto "clásico" como "clasico" sin duplicar entradas en el diccionario.

### Detección de negación

El parser implementa una ventana deslizante de negación de tres palabras. Cuando detecta una palabra negadora (`no`, `sin`, `without`, `not`, entre otras), marca las tres palabras siguientes como negadas. Esto permite interpretar correctamente frases como "sin guitarra" o "no oscuro", donde el término negado disminuye la puntuación de esa categoría en lugar de aumentarla.

### Diccionarios de palabras clave

Se definen cuatro dimensiones con sus respectivos mapeos:

- **Género** (7 categorías): `ROCK`, `POP`, `FUNK`, `JAZZ`, `LATIN`, `CLASSICAL`, `ELECTRONIC`. Cada categoría incluye términos en español e inglés, así como subgéneros relacionados (por ejemplo, "bossa nova" y "bebop" mapean a `JAZZ`).

- **Estado de ánimo** (5 categorías): `HAPPY`, `SAD`, `DARK`, `RELAXED`, `TENSE`. Los diccionarios incluyen sinónimos emocionales y adjetivos asociados en ambos idiomas.

- **Nivel de energía** (3 categorías): `LOW`, `MED`, `HIGH`. Los diccionarios excluyen deliberadamente nombres de instrumentos para evitar la colisión con el término "bajo" (que en español puede referirse tanto al instrumento como a una energía baja).

- **Instrumento** (3 categorías): `PIANO`, `BASS`, `GUITAR`. Solo se incluyen sustantivos inequívocos para minimizar falsos positivos.

### Sistema de puntuación

Para cada dimensión, el parser calcula una puntuación acumulada por etiqueta. Las frases de múltiples palabras (como "bossa nova") reciben un peso de 1.5× respecto a palabras individuales, ya que son señales más específicas. La etiqueta con mayor puntuación positiva gana; si ninguna supera cero, se usa el valor predeterminado de la dimensión.

### Puntuación de confianza

El resultado incluye un valor de confianza entre 0.0 y 1.0 calculado como la proporción de dimensiones efectivamente detectadas. Una confianza de 1.0 indica que el texto contenía señales para las cuatro dimensiones; 0.0 indica que no se encontró ninguna señal musical y todos los valores son predeterminados.

**Ejemplo de uso:**

```
Entrada: "quiero algo jazz con mucho piano, relajado y suave"
Salida:  genre=JAZZ, mood=RELAXED, energy=LOW, instrument=PIANO, confidence=1.0
```

---

## 5. Sistema de Autenticación

La autenticación se implementa con dos mecanismos complementarios.

### Autenticación con email y contraseña

El registro genera un hash bcrypt de la contraseña usando sal aleatoria por `bcrypt.hashpw()`. La contraseña en texto plano nunca se almacena ni se registra. La verificación usa `bcrypt.checkpw()`, que es resistente a ataques de temporización.

Al autenticarse, el servidor genera un JWT firmado con HMAC-SHA256 usando una clave secreta configurable por variable de entorno. El token incluye el `user_id` como sujeto y tiene una expiración de 7 días. El frontend almacena el token y lo incluye en el header `Authorization: Bearer <token>` en cada solicitud.

### Autenticación con Google OAuth 2.0

El flujo implementado es OAuth 2.0 Authorization Code:

1. El usuario accede a `/auth/google`, que redirige a Google con los scopes `openid`, `email` y `profile`.
2. Google autentica al usuario y redirige a `/auth/google/callback` con un código de autorización.
3. El servidor intercambia el código por un token de acceso usando el endpoint de token de Google.
4. Se recupera el perfil del usuario (email, nombre, foto, ID de Google).
5. Si el email ya existe en la base de datos, se vincula el `google_id`. Si no existe, se crea un nuevo usuario.
6. Se genera un JWT y se redirige al frontend con el token en la URL.

### Control de acceso

La dependencia `get_current_user` valida el JWT en cada solicitud protegida y recupera el usuario de la base de datos. Una dependencia adicional `require_admin` verifica el campo `role` para los endpoints de administración.

---

## 6. Pipeline de Procesamiento Asíncrono

El procesamiento se implementa mediante tres workers Celery independientes, cada uno suscrito a su propia cola. La comunicación entre workers se realiza encadenando tareas (send_task al finalizar), no mediante dependencias directas entre contenedores, lo que permite escalar o reemplazar cada worker de forma independiente.

### Configuración de Celery

```python
CELERY_BROKER_URL    → redis://redis:6379/0
CELERY_RESULT_BACKEND → redis://redis:6379/0

Colas:
  ml_queue           → ml_worker
  transcription_queue → transcription_worker
  generation_queue   → generation_worker
```

### 6.1 Worker de Clasificación (ml_worker)

El `ml_worker` realiza la validación del instrumento mediante un clasificador de audio neuronal. Su función es garantizar que el audio de entrada corresponda a uno de los instrumentos soportados antes de continuar el pipeline.

**Clasificador CNN14 (PANNs):**

Se utiliza el modelo CNN14 preentrenado del framework PANNs (*Pretrained Audio Neural Networks*), entrenado sobre AudioSet con 527 etiquetas de clases de audio. El modelo acepta audio mono a 32 kHz y produce una distribución de probabilidad sobre las 527 clases.

El proceso de clasificación:
1. Carga el audio y lo resamplea a 32 kHz mono.
2. Ejecuta inferencia con el CNN14.
3. Busca dinámicamente los índices correspondientes a las clases "Guitar", "Bass guitar" y "Piano" en las etiquetas de AudioSet.
4. Retorna el instrumento con mayor probabilidad y un booleano indicando si es uno de los tres soportados.

Si el instrumento detectado no es válido, la creación se marca como `FAILED` con un mensaje descriptivo y el pipeline termina. Si es válido, actualiza `detected_instrument` en la base de datos y despacha la siguiente tarea a `transcription_queue`.

### 6.2 Worker de Transcripción (transcription_worker)

El `transcription_worker` convierte el archivo de audio en una representación MIDI usando **Basic Pitch**, la librería de transcripción automática de Spotify.

Basic Pitch emplea una red neuronal convolucional entrenada para detectar notas (pitch, onset, offset) directamente en el espectrograma del audio. Produce archivos MIDI que preservan el contenido melódico y armónico del audio original, con múltiples pistas cuando detecta polifonía.

El worker:
1. Ejecuta la inferencia de Basic Pitch sobre el archivo de audio.
2. Guarda el MIDI resultante en el volumen compartido Docker.
3. Actualiza `midi_path` en la base de datos.
4. Encadena la tarea al `generation_worker` pasando la ruta del MIDI y todos los parámetros musicales originales.

### 6.3 Worker de Generación (generation_worker)

El `generation_worker` es el componente central del sistema. Recibe el MIDI transcrito y produce el acompañamiento musical mediante el modelo MusicTransformer. Su ejecución se detalla en la sección [7. Modelo MusicTransformer](#7-modelo-musictransformer).

El pipeline interno del worker sigue los pasos:

1. **Parseo del MIDI de entrada** con `pretty_midi`. Selecciona la pista melódica principal y estima el tempo. Si el tempo estimado está fuera del rango [30, 300] BPM, se usa 120 BPM como valor predeterminado.

2. **Tokenización de la melodía** (encoder) usando el esquema posicional descrito en la sección 7.2.

3. **Carga del modelo** desde el checkpoint `best_model.pt`. El modelo se almacena en caché en memoria del proceso para evitar recargas en solicitudes subsecuentes.

4. **Inferencia autoregresiva** (decoder) generando hasta 1,024 tokens nuevos.

5. **Conversión de tokens a MIDI** de acompañamiento usando `tokens_to_midi()`.

6. **Conversión a MusicXML** de dos pentagramas (melodía + acompañamiento) usando `tokens_to_musicxml()`.

7. **Subida a Supabase Storage** de ambos archivos.

8. **Actualización de la base de datos** con las URLs públicas, el número de notas y la duración.

---

## 7. Modelo MusicTransformer

### 7.1 Arquitectura del Transformer

El modelo sigue la arquitectura Transformer encoder-decoder estándar. Los parámetros de configuración son:

| Parámetro | Valor | Descripción |
|---|---|---|
| `vocab_size` | 525 | Tamaño del vocabulario de tokens |
| `max_seq_len` | 1536 | Longitud máxima de secuencia |
| `d_model` | 512 | Dimensión del espacio de embeddings |
| `n_heads` | 8 | Número de cabezas de atención |
| `n_enc_layers` | 6 | Capas del encoder |
| `n_dec_layers` | 6 | Capas del decoder |
| `d_ff` | 2048 | Dimensión de la capa feed-forward interna |
| `dropout` | 0.15 | Tasa de dropout durante entrenamiento |

**Codificación posicional:** Se usa codificación sinusoidal estándar, sumada a los embeddings de tokens antes de cada bloque de atención.

**Atadura de pesos:** El embedding de entrada y la proyección de salida (logits) comparten la misma matriz de parámetros (*weight tying*), reduciendo el número de parámetros y mejorando la generalización.

**Inicialización:** Los pesos se inicializan con la distribución de Xavier, lo que estabiliza el entrenamiento de redes profundas con función de activación lineal.

### Función de pérdida ponderada

Durante el entrenamiento se aplican pesos diferenciados por tipo de token para compensar el desbalance natural en las secuencias musicales:

| Tipo de token | Peso |
|---|---|
| `NOTE_ON` | 2.0 |
| `VELOCITY` | 2.0 |
| `NOTE_OFF` | 1.5 |
| `TIME_SHIFT` | 0.3 |

Los tokens `NOTE_ON` y `VELOCITY` reciben mayor peso porque son los más informativos para el contenido musical. Los tokens `TIME_SHIFT` reciben menor peso porque son muy frecuentes y su predicción correcta aporta menos información por unidad de pérdida.

### 7.2 Esquema de Tokenización

El sistema utiliza dos esquemas de tokenización complementarios: uno para la entrada del encoder (melodía) y otro para la salida del decoder (acompañamiento). El vocabulario total de 525 tokens incluye tokens de ambos esquemas más tokens especiales y de metadatos.

#### Encoder — Representación Posicional

La melodía de entrada se tokeniza en formato posicional, que especifica la ubicación de cada nota dentro de la estructura métrica:

```
<BAR_i>     : número de compás (1 a N)
<POS_j>     : posición dentro del compás en ticks (0 a 31, PPQ=8)
<PITCH_p>   : altura MIDI de la nota (28 a 108)
<DUR_d>     : duración en ticks (1, 2, 3, 4, 6, 8, 12, 16)
<VEL_v>     : velocidad en bins de 8 niveles (16, 24, …, 127)
```

Cada nota se representa como la secuencia `<BAR_i> <POS_j> <PITCH_p> <DUR_d> <VEL_v>`. Este formato preserva la estructura métrica de la melodía y permite al encoder razonar sobre la posición relativa de las notas dentro de cada compás.

El proceso de tokenización incluye:
1. Detección de la tonalidad con `detect_key()` usando la distribución de clases de pitch (Krumhansl-Schmuckler).
2. Detección de acordes por compás con `detect_chord()`.
3. Cuantización de posiciones y duraciones a la grilla de PPQ=8.
4. Inserción de tokens de metadatos: `<TEMPO_x>`, `<TIMESIG_4_4>`, `<KEY_x>`, `<GENRE_x>`, `<MOOD_x>`, `<ENERGY_x>`, `<INST_x>`, `<CHORD_x>`.

#### Decoder — Representación Basada en Eventos

El acompañamiento se genera en formato basado en eventos, inspirado en la representación MIDI-like:

```
<NOTE_ON_p>     : inicio de nota con pitch p
<NOTE_OFF_p>    : fin de nota con pitch p
<TIME_SHIFT_i>  : avance de tiempo en ticks
<VELOCITY_v>    : cambio de velocidad (8 niveles)
```

Este formato elimina la necesidad de cuantización estricta a una grilla métrica, permitiendo al modelo generar ritmos más fluidos y naturales. El tiempo se acumula mediante tokens `TIME_SHIFT` consecutivos.

#### Vocabulario completo

El vocabulario de 525 tokens se distribuye aproximadamente así:

| Categoría | Tokens |
|---|---|
| Tokens especiales (`<SOS>`, `<EOS>`, `<PAD>`, `<UNK>`, `<SEP>`, `<MASK>`) | 6 |
| Metadatos de contexto (genre, mood, energy, instrument, key, tempo, timesig) | ~50 |
| Encoder posicional (BAR, POS, PITCH, DUR, VEL) | ~220 |
| Decoder event-based (NOTE_ON, NOTE_OFF, TIME_SHIFT, VELOCITY) | ~250 |

El vocabulario se construye una sola vez durante el preprocesamiento y se serializa en `vocabulary.json`, del cual se cargan los diccionarios `TOKEN2ID` e `ID2TOKEN` en tiempo de ejecución.

### 7.3 Inferencia y Muestreo

La generación utiliza decodificación autoregresiva con un conjunto de restricciones para evitar patrones degenerados comunes en generación musical.

#### Preparación de la entrada

Antes de la inferencia:
1. La secuencia del encoder se trunca a `max_seq_len` si es necesario.
2. Se rellena con `<PAD>` hasta `max_seq_len` y se construye una máscara de atención booleana.
3. El prompt inicial del decoder es `[<SOS>, <GENRE_x>, <MOOD_x>, <ENERGY_x>, <INST_x>]`, que condiciona la generación desde el primer token.

#### Estrategia de muestreo

En cada paso de decodificación:

1. **Top-k filtering:** Se conservan solo los `k=50` tokens con mayor logit; el resto se lleva a `-inf`.

2. **Nucleus sampling (top-p):** Se ordenan los tokens por probabilidad descendente y se descartan los que están fuera del núcleo que acumula el `top_p` de probabilidad (por defecto 0.9).

3. **Penalización de repetición:** Se divide el logit de cada token que ya aparece en la secuencia generada por un factor de 1.3, desincentivando la repetición literal.

4. **Temperatura:** Los logits se escalan por `1/temperature` antes del softmax. Una temperatura de 0.9 mantiene diversidad mientras suaviza los picos extremos de la distribución.

#### Restricciones musicales

El módulo de inferencia aplica reglas de dominio durante la generación:

- **Control de silencio:** Si han pasado más de 8 tokens `TIME_SHIFT` consecutivos sin ningún `NOTE_ON`, se aplica un bonus logarítmico a todos los tokens `NOTE_ON` para incentivar la reanudación de notas.

- **Límite de polifonía:** Se mantiene un contador de notas activas (abiertas con `NOTE_ON` pero sin su correspondiente `NOTE_OFF`). Si hay 3 o más notas activas simultáneamente, los tokens `NOTE_ON` se penalizan multiplicando su probabilidad por 0.1.

- **Cierre automático de notas:** Si una nota lleva activa más de un tiempo definido (medido en tokens `TIME_SHIFT` acumulados), se fuerza la inserción de su `NOTE_OFF` correspondiente para evitar notas infinitamente sostenidas.

- **Terminación:** La generación se detiene al producir el token `<EOS>` o al alcanzar el límite de `max_new_tokens=1024`.

---

## 8. Generación de MusicXML

El módulo `tokens_to_musicxml.py` convierte la representación tokenizada en una partitura de dos pentagramas (melodía y acompañamiento) en formato MusicXML, usando la librería `music21`.

### Estructura de la partitura

El MusicXML generado contiene un `Score` con dos `Part`:

1. **Pentagrama superior (melodía):** Construido desde los tokens del encoder con representación posicional. Usa clave de sol (treble clef) por defecto, excepto para bajo eléctrico que usa clave de fa (bass clef). Incluye la marca de metrónomo.

2. **Pentagrama inferior (acompañamiento):** Construido desde los IDs del decoder con representación basada en eventos. El instrumento (piano, guitarra o bajo) se detecta del token `<INST_x>` en la secuencia generada.

Ambos pentagramas incluyen:
- Armadura de clave derivada del token `<KEY_x>`.
- Compás derivado del token `<TIMESIG_x>`.
- Símbolos de acordes sobre el pentagrama de melodía.
- Indicaciones de dinámica (`ppp` a `fff`) derivadas de los niveles de velocidad MIDI.

### Conversión de eventos a notas

La función `events_to_part()` convierte la lista de eventos estructurados en un `stream.Part` de music21. Para cada evento:

1. **Posición absoluta:** Se calcula como `(bar - 1) × bar_dur + pos_ticks / ppq` en quarter lengths.

2. **Cuantización a grilla:** Tanto la posición como la duración se ajustan a la grilla de `0.0625` quarter lengths (una semicorchea de dieciseisavo) mediante la función `_snap_ql()`. Esto garantiza que las duraciones sean valores representables en notación musical estándar.

3. **Creación de la nota:** Se instancia un `note.Note` con el pitch MIDI y la duración calculada.

4. **Dinámica:** La velocidad MIDI se mapea al símbolo de dinámica más cercano (`ppp`, `pp`, `p`, `mp`, `mf`, `f`, `ff`, `fff`) y se inserta como un objeto `dynamics.Dynamic`. Los cambios de dinámica se insertan solo cuando el símbolo cambia respecto al anterior.

### Corrección del error de corrupción en MusicXML

Durante el desarrollo se identificó un problema crítico: los archivos MusicXML generados aparecían corrompidos al abrirse en editores de partituras como MuseScore o Sibelius. El análisis del XML producido reveló la presencia del atributo `dynamics="XX.XX"` directamente en los elementos `<note>`, lo cual no es parte del estándar MusicXML y causaba el rechazo del archivo por parte de los editores.

**Causa raíz:** La asignación `n.volume.velocity = valor` en music21 serializa la velocidad MIDI como el atributo no estándar `dynamics` dentro del elemento `<note>` del XML. Este comportamiento es un artefacto de la implementación interna de music21 y no produce XML válido según el esquema MusicXML.

**Solución implementada:** Se eliminó la línea `n.volume.velocity = max(1, min(127, ev["velocity"]))` de la función de construcción de partes. En su lugar, las indicaciones de dinámica se expresan mediante objetos `dynamics.Dynamic` de music21, que sí producen XML estándar usando los elementos `<direction>` y `<dynamics>` correctos de la especificación MusicXML.

Adicionalmente, se eliminó la llamada a `p.makeNotation(inPlace=True)`, que introducía errores adicionales al intentar reescribir duraciones no estándar producidas por la tokenización.

La función `_snap_ql()` —que ya estaba definida en el módulo pero no se aplicaba— se integró activamente para cuantizar posiciones y duraciones antes de construir los objetos `Duration`, eliminando valores fuera de grilla que causaban advertencias en music21.

**Manejo de errores en la exportación:** La exportación a MusicXML se realiza en dos intentos. El primero usa el método estándar `score.write("musicxml")`. Si falla (por ejemplo, por problemas de beaming en compases con duraciones irregulares), el segundo intento usa el exportador interno `ScoreExporter` con `makeBeams=False`, y serializa el XML directamente con `xml.etree.ElementTree` en caso de que el exportador también falle.

---

## 9. Almacenamiento en la Nube

Se utiliza Supabase Storage como sistema de almacenamiento de objetos. Supabase provee una API compatible con el estándar de S3 y expone URLs públicas para los archivos almacenados.

### Estructura de rutas en el bucket

```
bytebeat/
├── users/{user_id}/audio/{job_id}.{ext}    # Audio original subido
├── midis/{creacion_id}/transcribed.mid      # MIDI transcrito (intermedio)
└── outputs/{creacion_id}/
    ├── accompaniment.mid                    # MIDI de acompañamiento
    └── partitura.xml                        # MusicXML de dos pentagramas
```

### Operaciones implementadas

- **`upload_file(local_path, storage_path, content_type)`:** Lee el archivo local y lo sube al bucket usando la API de Supabase. Retorna la URL pública o `None` si no está configurado Supabase o si ocurre un error. La subida usa la opción `upsert=true` para sobreescribir si el archivo ya existe.

- **`download_file(url, local_path)`:** Descarga un archivo desde una URL HTTP al sistema de archivos local, usando la librería `requests`. Se usa en el `generation_worker` para obtener el MIDI cuando este fue subido por el `transcription_worker`.

- **`delete_file(storage_path)`:** Elimina un archivo del bucket. Se invoca al borrar una creación para liberar almacenamiento.

- **`path_from_url(url)`:** Extrae la ruta relativa dentro del bucket a partir de una URL pública completa de Supabase.

El cliente de Supabase se instancia de forma perezosa (*lazy*) la primera vez que se necesita, usando las variables de entorno `SUPABASE_URL` y `SUPABASE_KEY`. El código de almacenamiento está duplicado intencionalmente en cada worker (`services/api/storage/supabase_client.py` y `services/generation_worker/storage.py`) ya que los contenedores Docker no comparten código fuente.

---

## 10. Infraestructura de Contenedores

El sistema se orquesta con Docker Compose. El archivo `docker-compose.yml` define los seis servicios principales y sus dependencias.

### Servicios

| Servicio | Imagen base | Puerto expuesto | Volúmenes |
|---|---|---|---|
| `db` | postgres:15 | 5432 | `postgres_data` |
| `redis` | redis:7-alpine | 6379 | — |
| `api` | python:3.11-slim | 8000 | `shared_data`, `./frontend` |
| `ml_worker` | python:3.11-slim | — | `shared_data`, `panns_data` |
| `transcription_worker` | python:3.11-slim | — | `shared_data`, `./music-transformer/src` |
| `generation_worker` | python:3.11-slim | — | `shared_data`, `./music-transformer/checkpoints`, `./music-transformer/src` |

### Dependencias y healthchecks

Los workers y la API declaran dependencia de `db` y `redis` con la condición `service_healthy`. PostgreSQL se declara saludable cuando `pg_isready` responde correctamente; Redis cuando `redis-cli ping` retorna `PONG`. Esto garantiza que ningún worker intente conectarse antes de que los servicios de infraestructura estén listos.

### Volúmenes compartidos

- **`postgres_data`:** Persiste los datos de PostgreSQL entre reinicios del contenedor.
- **`shared_data`:** Volumen compartido entre la API y todos los workers. Contiene los archivos de audio subidos y los MIDIs generados. Permite que la API guarde un archivo y el `ml_worker` lo lea sin transferencia de red.
- **`panns_data`:** Persiste el checkpoint del modelo CNN14 (~325 MB) para evitar descargarlo en cada inicio del contenedor.

### Soporte GPU

El archivo `docker-compose.gpu.yml` es un overlay que agrega la configuración de runtime NVIDIA al servicio `generation_worker`:

```yaml
services:
  generation_worker:
    runtime: nvidia
    environment:
      NVIDIA_VISIBLE_DEVICES: all
```

Se aplica al levantar los servicios con:
```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Esto permite que PyTorch detecte la GPU mediante CUDA y ejecute la inferencia del MusicTransformer en GPU cuando esté disponible, cayendo a CPU en caso contrario gracias a `torch.device("cuda" if torch.cuda.is_available() else "cpu")`.

### Variables de entorno

Todas las variables de configuración sensible se definen en un archivo `.env` en la raíz del repositorio:

| Variable | Descripción |
|---|---|
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL |
| `DATABASE_URL` | Cadena de conexión SQLAlchemy |
| `CELERY_BROKER_URL` | URL de Redis como broker de Celery |
| `CELERY_RESULT_BACKEND` | URL de Redis como backend de resultados |
| `JWT_SECRET_KEY` | Clave secreta para firmar tokens JWT |
| `GOOGLE_CLIENT_ID` | ID de cliente para Google OAuth |
| `GOOGLE_CLIENT_SECRET` | Secreto de cliente para Google OAuth |
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_KEY` | Clave service_role de Supabase |
| `SUPABASE_BUCKET` | Nombre del bucket en Supabase Storage |
| `FRONTEND_URL` | URL base del frontend (usada en redirects OAuth y CORS) |
