# Despliegue, Contenedores e Infraestructura Inicial — Semana 4

**Proyecto:** TributIA
**Fecha:** 1 de agosto de 2026

---

## 1. Descripción breve del servicio preparado

TributIA es una plataforma web Django que analiza documentos tributarios (facturas, constancias, comprobantes en PDF/PNG/JPG) mediante un pipeline de OCR (Tesseract) + NLP (spaCy) + LLM (Google Gemini), y expone tanto una interfaz web como una API interna versionada (`/api/v1/`). Para esta entrega se preparó el servicio completo (app Django + dependencias del sistema para OCR) para ejecutarse de forma reproducible dentro de un contenedor Docker, fuera del entorno personal de desarrollo.

## 2. Ruta elegida

**Contenedor Docker**, mediante `Dockerfile` + `docker-compose.yml` en la raíz del repositorio, con dos servicios: `web` (Django + gunicorn) y `db` (PostgreSQL 16). La base de datos del contenedor ya no es SQLite: se migró a PostgreSQL como parte de esta entrega (ver §6b).

Se encontró un bloqueo inicial ("Virtualization support not detected" al abrir Docker Desktop) porque WSL2/Virtual Machine Platform no estaban habilitados en Windows (aunque la virtualización sí estaba activa en el firmware/BIOS). Se resolvió habilitando las características de Windows necesarias y reiniciando — ver detalle en la sección 9.

## 3. Dockerfile

Ver [`Dockerfile`](../Dockerfile) en la raíz del repo. Resumen de decisiones:

- Base `python:3.13-slim` (misma versión de Python que usa el equipo en desarrollo, ver README).
- Se instalan `tesseract-ocr` y `poppler-utils` a nivel de sistema operativo dentro de la imagen, ya que son dependencias nativas que `pytesseract` y `pdf2image` no pueden traer vía pip (ver riesgo #8 en `riesgos-tecnicos.md`). El paquete de idioma español de Tesseract (`spa.traineddata`) no se instala vía `apt`, sino que se copia empaquetado desde `tessdata/` del propio repo, igual que en desarrollo local (ver `core/ocr_utils.py`).
- `build-essential` se incluye por si alguna dependencia de spaCy (`blis`, `thinc`) no trae wheel prebuilt para la versión de Python de la imagen y necesita compilar.
- `migrate` y `collectstatic` se ejecutan al **iniciar** el contenedor (en el `CMD`), no durante el build, porque `settings.py` exige `SECRET_KEY` y `GEMINI_API_KEY` vía `os.environ[...]`, que solo están disponibles en runtime a través de `.env` / `env_file` — no se hornean secretos dentro de las capas de la imagen.
- Servidor de aplicación: `gunicorn` (agregado a `requirements.txt` junto con `whitenoise` para servir archivos estáticos sin depender de un servidor web adicional como nginx).
- Driver de base de datos: `psycopg2-binary` (agregado a `requirements.txt`) para hablar con el servicio `db` (PostgreSQL) desde Django.

## 4. `.dockerignore`

Ver [`.dockerignore`](../.dockerignore). Excluye: `.git`, entornos virtuales, `__pycache__`, `.env` (secretos reales — se inyectan vía `env_file` en runtime, nunca se copian a la imagen), `db.sqlite3` y `media/` del host (datos de desarrollo, no deben quedar horneados en la imagen), `docs/`, `tests/` y archivos `.md` (no se necesitan en runtime, mantiene la imagen más liviana).

## 5. Variables de entorno

Documentadas en [`.env.example`](../.env.example) (sin valores reales):

| Variable | Descripción | Obligatoria | Nueva en Semana 4 |
|---|---|:---:|:---:|
| `SECRET_KEY` | Clave secreta de Django | Sí | |
| `DEBUG` | `True`/`False`. En contenedor se recomienda `False` | Sí | |
| `ALLOWED_HOSTS` | Hosts separados por coma permitidos por Django | Sí | ✔️ |
| `GEMINI_API_KEY` | API key de Google Gemini | Sí | |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Credenciales SMTP de Gmail | Sí | |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Credenciales de la base de datos PostgreSQL usada por el servicio `db` de `docker-compose` | Solo en Docker | ✔️ |

`DEBUG` y `ALLOWED_HOSTS` se agregaron en `tributia_project/settings.py` para que sean configurables por entorno (antes estaban hardcodeados: `DEBUG = True` y `ALLOWED_HOSTS = []`), requisito para poder correr el servicio fuera de `manage.py runserver`. `POSTGRES_*` solo se usan dentro de `docker-compose`: `settings.py` cambia a PostgreSQL automáticamente cuando detecta `POSTGRES_HOST` en el entorno (inyectado por el propio `docker-compose.yml`) y cae a SQLite cuando esa variable no existe, para no romper el flujo de desarrollo local del equipo (`manage.py runserver` sin Docker ni Postgres instalado).

## 6. Evidencia de construcción y ejecución

**Construcción de la imagen (`docker compose build`):**

```text
$ docker compose build
 Image tributia-web Building
#6 [1/6] FROM docker.io/library/python:3.13-slim
#7 [2/6] RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils build-essential
#9 [4/6] COPY requirements.txt .
#10 [5/6] RUN pip install --no-cache-dir -r requirements.txt
#10 72.85 Successfully installed Django-6.0.3 ... gunicorn-23.0.0 ... whitenoise-6.8.2 ... spacy-3.8.14 ... google-generativeai-0.8.6
#11 [6/6] COPY . .
#12 exporting to image
#12 naming to docker.io/library/tributia-web:latest done
 Image tributia-web Built
```

Build exitoso, sin errores de compilación (las dependencias de spaCy —`blis`, `thinc`— sí trajeron wheels prebuilt para Python 3.13, así que `build-essential` terminó no siendo estrictamente necesario, pero se dejó por robustez).

**Ejecución (`docker compose up -d`) y arranque del contenedor:**

```text
$ docker compose up -d
 Network tributia_default Created
 Container tributia-web-1 Created
 Container tributia-web-1 Started

$ docker compose logs web
web-1  | Operations to perform:
web-1  |   Apply all migrations: admin, auth, contenttypes, core, sessions
web-1  | Running migrations:
web-1  |   No migrations to apply.
web-1  | 132 static files copied to '/app/staticfiles', 396 post-processed, 2 skipped due to conflict.
web-1  | [2026-08-01 21:43:20 +0000] [36] [INFO] Starting gunicorn 23.0.0
web-1  | [2026-08-01 21:43:20 +0000] [36] [INFO] Listening at: http://0.0.0.0:8000 (36)
web-1  | [2026-08-01 21:43:20 +0000] [36] [INFO] Using worker: sync
web-1  | [2026-08-01 21:43:20 +0000] [37] [INFO] Booting worker with pid: 37
web-1  | [2026-08-01 21:43:20 +0000] [38] [INFO] Booting worker with pid: 38
web-1  | [2026-08-01 21:43:20 +0000] [39] [INFO] Booting worker with pid: 39

$ docker compose ps
NAME             IMAGE          COMMAND                  STATUS          PORTS
tributia-web-1   tributia-web   "sh -c 'python manag…"   Up              0.0.0.0:8000->8000/tcp
```

El contenedor migró la base de datos, corrió `collectstatic` (whitenoise sirviendo los estáticos, sin nginx) y levantó gunicorn con 3 workers, todo con `DEBUG=False` y `ALLOWED_HOSTS=localhost,127.0.0.1` inyectados por `docker-compose.yml` — es decir, en la misma configuración que tendría un despliegue real, no el `manage.py runserver` de desarrollo.

## 6b. Migración a PostgreSQL

Se agregó un segundo servicio (`db`, imagen `postgres:16-alpine`) a `docker-compose.yml`, con un volumen nombrado (`postgres_data`) para persistencia y un `healthcheck` (`pg_isready`); `web` espera (`depends_on: condition: service_healthy`) a que Postgres esté listo antes de arrancar. `tributia_project/settings.py` se actualizó para elegir el motor de base de datos según el entorno:

```python
if os.environ.get('POSTGRES_HOST'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['POSTGRES_DB'],
            'USER': os.environ['POSTGRES_USER'],
            'PASSWORD': os.environ['POSTGRES_PASSWORD'],
            'HOST': os.environ['POSTGRES_HOST'],
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
```

**Evidencia — reconstrucción con el servicio `db` agregado:**

```text
$ docker compose down
$ docker compose up -d --build
...
#10  Successfully installed ... psycopg2-binary-2.9.10 ...
 Image tributia-web Built
 Network tributia_default Created
 Volume tributia_postgres_data Created
 Container tributia-db-1 Created
 Container tributia-web-1 Created
 Container tributia-db-1 Starting
 Container tributia-db-1 Started
 Container tributia-db-1 Waiting
 Container tributia-db-1 Healthy
 Container tributia-web-1 Starting
 Container tributia-web-1 Started
```

**Evidencia — todas las migraciones se aplicaron limpio contra la base Postgres nueva (vacía):**

```text
$ docker compose logs web
web-1  |   Applying auth.0012_alter_user_first_name_max_length... OK
web-1  |   Applying core.0001_initial... OK
web-1  |   ...
web-1  |   Applying core.0013_eventocalendario... OK
web-1  |   Applying sessions.0001_initial... OK
web-1  | 132 static files copied to '/app/staticfiles', 396 post-processed, 2 skipped due to conflict.
web-1  | [INFO] Starting gunicorn 23.0.0
web-1  | [INFO] Listening at: http://0.0.0.0:8000
```

No se necesitó ningún ajuste a los modelos de `core/models.py` para que las migraciones corrieran en PostgreSQL — el ORM de Django abstrajo la diferencia de motor sin cambios de código.

## 7. Prueba del endpoint `/health`

```bash
$ curl -s -w "\nHTTP_STATUS:%{http_code}\n" http://localhost:8000/api/v1/health/
{"status": "ok", "checks": {"base_datos": "ok", "tesseract": "ok", "gemini_api_key": "configurada"}}
HTTP_STATUS:200
```

Confirma, **desde dentro del contenedor**, que la conexión a la base de datos funciona, que el binario de `tesseract` instalado vía `apt-get` en la imagen se encuentra correctamente, y que `GEMINI_API_KEY` llegó bien inyectada desde `.env`.

También se probó la página principal (`GET /`) para confirmar que whitenoise sirve los estáticos con `DEBUG=False`:

```bash
$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/
200
# El HTML devuelto referencia /static/css/style.5eaec3cdde5d.css
# (hash de cache-busting generado por CompressedManifestStaticFilesStorage de whitenoise)
```

## 8. Prueba del endpoint principal

Endpoint principal de IA: `POST /api/v1/analizar-documento/` (documentado en `docs/api.md`). Requiere sesión autenticada, igual que en desarrollo local; se probó con el flujo completo: login por curl → subida de un documento real (factura PDF) → pipeline completo (extracción de texto, spaCy, Gemini) corriendo dentro del contenedor.

```bash
# 1. Login (obtiene sessionid)
$ curl -s -c cookies.txt http://localhost:8000/login/ -o /dev/null
$ CSRF=$(grep csrftoken cookies.txt | awk '{print $7}')
$ curl -s -b cookies.txt -c cookies.txt -X POST \
    -d "username=demo_docker&password=DemoDocker123!&csrfmiddlewaretoken=$CSRF" \
    -e "http://localhost:8000/login/" \
    -w "HTTP_STATUS_LOGIN:%{http_code}\n" -o /dev/null \
    http://localhost:8000/login/
HTTP_STATUS_LOGIN:302

# 2. Subida y análisis de un documento real
$ curl -s -b cookies.txt -X POST \
    -F "archivo=@media/documentos/2026/07/30/BF651ADF-CB6B-4210-B639-D4FC3B0227F0.pdf" \
    -w "\nHTTP_STATUS:%{http_code}\n" \
    http://localhost:8000/api/v1/analizar-documento/
```

**Respuesta real (`201 Created`), pipeline completo ejecutado dentro del contenedor y persistido en PostgreSQL, incluyendo la llamada real a Gemini:**

```json
{
  "documento_id": 1,
  "nombre": "BF651ADF-CB6B-4210-B639-D4FC3B0227F0.pdf",
  "estado": "analizado",
  "es_documento_tributario": true,
  "es_deducible": true,
  "confianza_clasificacion": 1.0,
  "tipo_documento_detectado": "Factura",
  "entidades": {
    "empresa": "UNIVERSIDAD CAPITAN GENERAL GERARDO BARRIOS",
    "fecha_documento": "29/07/2026",
    "numero_documento": "DTE-01-M001P001-000000000060602"
  },
  "montos": { "subtotal": 143.75, "iva": null, "otros_cargos": null, "total": 143.75 },
  "resumen_ia": "Factura electrónica emitida por la UNIVERSIDAD CAPITAN GENERAL GERARDO BARRIOS ... por concepto de pago de cuota educativa. El monto total de la operación es de $143.75.",
  "recomendacion_ia": "Se recomienda verificar que el monto total declarado por educación no exceda el límite anual de $15,000 para hacer efectiva la deducción...",
  "justificacion_deducible": "El gasto corresponde a educación, que es deducible hasta $15,000 anuales según la legislación fiscal salvadoreña."
}
HTTP_STATUS:201
```

(Entidades sensibles del documento de prueba —nombre del cliente, NIT, dirección— se omitieron de esta tabla resumen por privacidad; la respuesta completa incluye los mismos campos que documenta `docs/api.md`.)

Esta prueba confirma que, dentro del contenedor, funcionan de punta a punta: Tesseract/PyMuPDF (extracción), spaCy (entidades), la llamada real a la API de Gemini (clasificación + resumen + recomendación), y la escritura a la base de datos — no es un mock ni una respuesta simulada.

## 9. Errores, intentos, bloqueos y correcciones realizadas

### 9.1 Bloqueo: Docker Desktop no arrancaba ("Virtualization support not detected")

**Síntoma:** al abrir Docker Desktop, pantalla de error "Virtualization support not detected. Docker Desktop failed to start because virtualisation support wasn't detected", con el motor ("Engine") detenido.

**Diagnóstico:**

```text
> systeminfo | Select-String "Hyper-V" -Context 0,8
Requisitos Hyper-V:  Extensiones de modo de monitor de VM: Sí
                     Se habilitó la virtualización en el firmware: Sí
                     ...
```

La virtualización SÍ estaba habilitada a nivel de firmware/BIOS (equipo físico ASUS Vivobook, no una VM), así que no era un problema de hardware. Al intentar consultar las características de Windows relacionadas:

```text
> Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
Get-WindowsOptionalFeature : La operación requiere elevación.

> wsl.exe --version
(imprime el texto de ayuda de wsl.exe en vez de un número de versión → binario desactualizado, WSL2 no instalado realmente)
```

**Explicación técnica:** las características de Windows "Windows Subsystem for Linux" y "Virtual Machine Platform" (requeridas por el backend WSL2 de Docker Desktop) no estaban habilitadas, aunque el hardware sí soportaba virtualización.

**Ruta de corrección aplicada:**

```powershell
# PowerShell como Administrador
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
# Reinicio de Windows
# Tras reiniciar (PowerShell normal):
wsl --update
wsl --set-default-version 2
```

Después de esto, Docker Desktop inició correctamente (`docker ps` respondió sin error).

### 9.2 Bug real: `InvalidStorageError` al subir un documento dentro del contenedor

**Síntoma:** con el contenedor corriendo (`/health` en `200 OK`), el endpoint principal `POST /api/v1/analizar-documento/` devolvía `500 Internal Server Error` (página genérica, ya que `DEBUG=False` en el contenedor).

**Diagnóstico:** se levantó una segunda instancia temporal del mismo contenedor con `DEBUG=True` (`docker compose run --rm -e DEBUG=True -p 8001:8000 web ...`) para poder ver el traceback completo de Django:

```text
Exception Type: InvalidStorageError at /api/v1/analizar-documento/
Exception Value: Could not find config for 'default' in settings.STORAGES.
```

**Causa raíz:** al agregar `whitenoise` para servir archivos estáticos, se definió en `settings.py`:

```python
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

Desde Django 4.2, `STORAGES` reemplaza por completo la configuración por defecto de storages (no solo agrega la clave indicada) — al no declarar también la clave `"default"` (el storage que usan los `FileField`/`ImageField`, incluyendo la subida de documentos a `MEDIA_ROOT`), Django se quedó sin storage por defecto configurado, y cualquier operación de subida de archivo rompía con `InvalidStorageError`. El bug no se manifestaba en desarrollo local porque ahí `STORAGES` no estaba definido y Django usaba su configuración implícita completa.

**Corrección aplicada** (`tributia_project/settings.py`):

```python
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

**Verificación:** se reconstruyó la imagen (`docker compose up -d --build`) y se repitió la prueba del endpoint principal (sección 8), obteniendo `201 Created` con el pipeline de IA completo funcionando.

### 9.3 Nota sobre observabilidad (relacionada con el bug anterior)

Mientras se investigaba el error 500 original, se confirmó que con `DEBUG=False` y sin una configuración explícita de `LOGGING` en `settings.py`, los `logger.exception(...)` que ya existían en `core/api_views.py` no aparecían en la salida de `docker compose logs` (el logger raíz de Django, por defecto, solo envía al `console` handler cuando `DEBUG=True`). Esto confirma el riesgo ya identificado en `riesgos-tecnicos.md` ("Manejo de errores incompleto...") y refuerza la prioridad de "logging estructurado" planificada para la Semana 5 — sin eso, un error como el de 9.2 sería invisible en un despliegue real sin tener que reproducirlo manualmente con `DEBUG=True`.

## 10. Plan de infraestructura mínima

Componentes mínimos propuestos para un ambiente de staging/producción de bajo costo:

| Componente | Propuesta | Justificación |
|---|---|---|
| Cómputo | 1 contenedor Docker (app Django + gunicorn), 1 vCPU / 1–2 GB RAM | El pipeline de OCR/spaCy es el punto más pesado en CPU/RAM; con carga baja (proyecto académico) alcanza con un solo worker pequeño |
| Base de datos | PostgreSQL — ya migrado dentro del contenedor (servicio `db` en `docker-compose.yml`); para un despliegue real, apuntar `POSTGRES_HOST`/credenciales a un Postgres administrado (plan free/hobby de un PaaS) en vez del contenedor `db` local | SQLite no soportaba escritura concurrente real (riesgo #13 en `riesgos-tecnicos.md`, ya mitigado); falta solo apuntar a una instancia administrada para producción, ya que la app es agnóstica al motor vía `POSTGRES_HOST` |
| Almacenamiento de archivos | Volumen persistente para `MEDIA_ROOT`, o bucket S3-compatible | Los documentos subidos por usuarios deben sobrevivir a reinicios/redeploys del contenedor |
| Cola de tareas (futuro, Semana 4-5 del plan de mejora) | Redis + Celery/RQ | El pipeline de análisis es síncrono y bloqueante (riesgo #4); mover a cola evita timeouts en documentos grandes |
| Servidor de aplicación | gunicorn detrás de un proxy inverso (nginx / el propio proxy del PaaS) | gunicorn no debe exponerse directo a internet en producción |
| Archivos estáticos | whitenoise (ya integrado) | Evita depender de un servidor web adicional solo para CSS/JS en un despliegue de bajo tráfico |
| Variables/secretos | `.env` fuera del control de versiones, o el gestor de secretos del proveedor (ej. variables de entorno de Render/Railway) | Ninguna clave real debe vivir en el repo (`.env.example` documenta solo nombres) |
| Backups | Backup automático diario de la base de datos (según lo ofrezca el proveedor) | Actualmente SQLite no tiene backup (riesgo documentado en README §7) |

## 11. Estimación de costos iniciales (supuestos)

Supuestos: tráfico bajo (proyecto académico, decenas de usuarios concurrentes como máximo), sin SLA de alta disponibilidad, un solo entorno (no staging + producción separados).

| Ítem | Opción de bajo costo | Estimación mensual (USD) | Supuesto |
|---|---|---:|---|
| Hosting del contenedor | Plan free/hobby de un PaaS (ej. Render, Railway) | $0 – $7 | Free tier con "sleep" tras inactividad, o el primer tier pago si se necesita disponibilidad continua |
| Base de datos PostgreSQL | Plan free/starter del mismo proveedor | $0 – $5 | Free tier con límite de almacenamiento (ej. 256MB–1GB), suficiente para el volumen de documentos de un piloto |
| Almacenamiento de archivos | Incluido en el volumen del plan, o bucket free tier (ej. Cloudflare R2 free tier: 10GB) | $0 | Documentos son PDFs/imágenes de pocos MB cada uno |
| Google Gemini API (`gemini-2.5-flash-lite`) | Tier gratuito de Google AI Studio | $0 | Limitado por cuota diaria de requests (riesgo #1 y #2 ya documentados); pasar a un tier con billing sería el primer costo real si el uso crece |
| Dominio (opcional) | Subdominio gratuito del proveedor (`*.onrender.com`, etc.) | $0 | Dominio propio (`.com`) rondaría $10–15/año si se quisiera una URL propia |
| **Total estimado (piloto, sin dominio propio)** | | **$0 – $12/mes** | Válido mientras el tráfico se mantenga dentro de los free tiers |

El mayor riesgo de costo no es la infraestructura sino el consumo de la API de Gemini si el proyecto escalara más allá del tier gratuito (ver riesgo #2 en `riesgos-tecnicos.md`).

## 12. Riesgos técnicos pendientes

Ver detalle completo y priorizado en [`riesgos-tecnicos.md`](riesgos-tecnicos.md). Los más relevantes de cara al despliegue:

1. **Pipeline síncrono y bloqueante** dentro del request HTTP (riesgo #4) — un documento grande o Gemini lento puede provocar timeouts del proxy/PaaS. Mitigación planeada: cola de tareas (Celery/RQ) en Semana 4–5 del plan de mejora.
2. ~~SQLite no apto para concurrencia real en producción~~ (riesgo #13) — **mitigado en esta entrega**: el contenedor ahora corre sobre PostgreSQL (servicio `db`). Pendiente: apuntar a una instancia Postgres *administrada* (no el contenedor local) para un despliegue real con múltiples usuarios simultáneos.
3. **Sin validación de permisos por usuario** en vistas sensibles (riesgo #10) — pendiente para Semana 6.
4. **Cuota de Gemini limitada** (riesgos #1 y #2) — bajo carga real en un ambiente desplegado (accesible por más personas que en desarrollo local), la probabilidad de agotar la cuota diaria sube.
5. **Sin backups automáticos** de la base de datos ni de `MEDIA_ROOT` en el contenedor actual (el volumen `postgres_data` persiste entre reinicios del contenedor, pero no hay backup automático fuera de la máquina host).
6. **Imagen Docker no fue construida/probada dentro de un pipeline de CI** en esta entrega (el CI de Semana 3 solo corre `manage.py test` contra SQLite en memoria, no `docker build` ni pruebas contra Postgres) — queda como mejora para Semana 5.
7. **Pipeline de análisis aún síncrono y bloqueante** también dentro del contenedor — la migración a Postgres no resuelve esto; sigue dependiendo de mover a cola de tareas (Celery/RQ).

---

## Repositorio actualizado

Repositorio: ver enlace en la portada de este PDF / README del repositorio.
