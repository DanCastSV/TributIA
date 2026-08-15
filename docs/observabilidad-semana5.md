# Observabilidad, Rendimiento y Escalabilidad — Semana 5

**Proyecto:** TributIA
**Fecha:** 8 de agosto de 2026

---

## 1. Servicio y flujo crítico seleccionado

Flujo crítico: **`POST /api/v1/analizar-documento/`**, el pipeline completo de análisis de documentos tributarios (extracción de texto → regex → spaCy → Gemini → persistencia), documentado en `docs/api.md`. Es el flujo que hace todo el trabajo pesado del sistema y el más propenso a errores, timeouts y variabilidad de latencia (depende de Tesseract/OCR, spaCy y una llamada externa a la API de Gemini).

Como línea base de rendimiento (sección 7) se usa además `GET /api/v1/health/` — no porque sea el flujo crítico, sino porque permite correr las ≥20 solicitudes que pide la rúbrica sin consumir cuota real de Gemini (riesgo #1/#2 en `riesgos-tecnicos.md`); el endpoint de análisis se mide aparte con una muestra más pequeña de llamadas reales (justificado en la sección 7).

## 2. Preguntas de observabilidad

- ¿Cuánto tarda cada etapa del pipeline de análisis (extracción de texto, spaCy, Gemini) por separado, no solo el total?
- ¿Qué proporción de solicitudes al endpoint principal terminan en error, y de qué tipo (archivo inválido, no autenticado, documento no tributario, error interno)?
- ¿Con qué versión/modelo de Gemini se generó un análisis dado, para poder correlacionar cambios de comportamiento con cambios de modelo?
- ¿Se puede rastrear una solicitud específica de principio a fin (correlación entre el log de la request HTTP y los logs internos del pipeline)?
- ¿Cuál es la latencia normal del servicio bajo carga baja, para tener una referencia y poder notar degradación más adelante?

### Campos registrados

**Por cada request HTTP** (`core/middleware.py`, logger `tributia.requests`):

| Campo | Descripción |
|---|---|
| `request_id` | UUID único por solicitud, también devuelto en el header `X-Request-ID` de la respuesta |
| `metodo` | Método HTTP |
| `ruta` | Path solicitado |
| `status` | Código de respuesta HTTP |
| `duracion_ms` | Duración total de la request |

**Por cada etapa del pipeline de IA** (`core/services/analizador.py`, logger `core.services.analizador`), correlacionado automáticamente con el mismo `request_id` de la request que lo disparó:

| Campo | Descripción |
|---|---|
| `documento_id` | ID interno del documento (no el nombre de archivo ni su contenido) |
| `etapa` | `extraccion_texto`, `spacy` o `gemini` |
| `duracion_ms` | Duración de esa etapa específica |
| `modelo` | Nombre del modelo Gemini usado (solo en la etapa `gemini`) |
| `caracteres_extraidos` | Cantidad de caracteres de texto extraídos (solo en `extraccion_texto`; nunca el texto en sí) |
| `tipo_error` | Motivo de rechazo/error (`archivo_invalido`, `no_autenticado`, `documento_no_tributario`, o el nombre de la excepción de Python si fue un error inesperado) |
| `confianza_clasificacion` | Score 0.0–1.0 calculado por `calcular_confianza()` |

## 3. Código de instrumentación

**Correlación por request_id** (`core/logging_context.py`): usa `contextvars` para que cualquier log emitido durante una request (incluso dentro de `analizador.py`, varias funciones más abajo en la pila) quede automáticamente etiquetado con el mismo `request_id`, sin tener que pasarlo como parámetro por cada función.

**Formato JSON** (`core/logging_utils.py`): un `Formatter` que serializa cada línea de log como un objeto JSON, tomando cualquier campo pasado vía `extra={...}` — así los logs son legibles tanto por humanos como por herramientas (`grep`, `jq`).

**Middleware** (`core/middleware.py`): mide la duración total de cada request y registra el evento `request_completada` al finalizar.

**`LOGGING` en `tributia_project/settings.py`**: reemplaza la configuración implícita de Django, que por defecto solo activa el handler de consola cuando `DEBUG=True` — ese fue exactamente el motivo por el que, en Semana 4, un error real (`InvalidStorageError`) no dejó ningún rastro en `docker compose logs` dentro del contenedor (`DEBUG=False`). Ahora los logs siempre van a `stdout` en JSON, sin importar `DEBUG`.

**Pipeline instrumentado** (`core/services/analizador.py`): cada etapa (`extraccion_texto`, `spacy`, `gemini`) se cronometra por separado y se loguea con `logger.info(...)`; el rechazo por documento no tributario y los errores inesperados (`core/api_views.py`) se loguean con `tipo_error`.

### Evidencia de una solicitud exitosa

Solicitud real: login por curl + subida de una factura PDF real a `POST /api/v1/analizar-documento/`.

```bash
$ curl -s -b cookies.txt -X POST \
    -F "archivo=@media/documentos/2026/07/30/BF651ADF-CB6B-4210-B639-D4FC3B0227F0.pdf" \
    -w "\nHTTP_STATUS:%{http_code}\n" \
    http://localhost:8000/api/v1/analizar-documento/
HTTP_STATUS:201
X-Request-ID: 00dae09b-13bc-4990-9e76-956e1e5cb3e5
```

**Logs correlacionados por `request_id` (`docker compose logs web | grep 00dae09b`):**

```json
{"timestamp": "2026-08-15T10:33:14", "nivel": "INFO", "logger": "core.services.analizador", "mensaje": "analisis_iniciado", "documento_id": 2, "request_id": "00dae09b-13bc-4990-9e76-956e1e5cb3e5"}
{"timestamp": "2026-08-15T10:33:15", "nivel": "INFO", "logger": "core.services.analizador", "mensaje": "etapa_completada", "documento_id": 2, "etapa": "extraccion_texto", "duracion_ms": 67.3, "caracteres_extraidos": 2129, "request_id": "00dae09b-13bc-4990-9e76-956e1e5cb3e5"}
{"timestamp": "2026-08-15T10:33:15", "nivel": "INFO", "logger": "core.services.analizador", "mensaje": "etapa_completada", "documento_id": 2, "etapa": "spacy", "duracion_ms": 58.8, "request_id": "00dae09b-13bc-4990-9e76-956e1e5cb3e5"}
{"timestamp": "2026-08-15T10:33:17", "nivel": "INFO", "logger": "core.services.analizador", "mensaje": "etapa_completada", "documento_id": 2, "etapa": "gemini", "modelo": "models/gemini-2.5-flash-lite", "duracion_ms": 2312.6, "request_id": "00dae09b-13bc-4990-9e76-956e1e5cb3e5"}
{"timestamp": "2026-08-15T10:33:17", "nivel": "INFO", "logger": "core.services.analizador", "mensaje": "analisis_completado", "documento_id": 2, "duracion_total_ms": 2470.0, "confianza_clasificacion": 0.94, "request_id": "00dae09b-13bc-4990-9e76-956e1e5cb3e5"}
{"timestamp": "2026-08-15T10:33:17", "nivel": "INFO", "logger": "tributia.requests", "mensaje": "request_completada", "request_id": "00dae09b-13bc-4990-9e76-956e1e5cb3e5", "metodo": "POST", "ruta": "/api/v1/analizar-documento/", "status": 201, "duracion_ms": 4043.7}
```

**Interpretación:** el `request_id` correlaciona los 6 eventos de esta única solicitud, desde el inicio del pipeline hasta la respuesta HTTP. Se ve claramente que la etapa `gemini` (2312.6 ms) domina el tiempo total del pipeline (2470.0 ms) — extracción de texto y spaCy juntas suman menos de 130 ms.

### Evidencia de una entrada inválida / error controlado

Mismo flujo, pero enviando un archivo `.txt` (extensión no permitida):

```bash
$ curl -s -b cookies.txt -X POST -F "archivo=@prueba.txt" \
    -w "\nHTTP_STATUS:%{http_code}\n" \
    http://localhost:8000/api/v1/analizar-documento/
{"error": "archivo_invalido", "detalle": "Extensión no permitida. Use: pdf, png, jpg, jpeg"}
HTTP_STATUS:400
X-Request-ID: f716d205-ea3d-4f70-bf04-4e31c1f12110
```

**Logs correlacionados:**

```json
{"timestamp": "2026-08-15T10:33:19", "nivel": "WARNING", "logger": "core.api_views", "mensaje": "solicitud_rechazada", "tipo_error": "archivo_invalido", "request_id": "f716d205-ea3d-4f70-bf04-4e31c1f12110"}
{"timestamp": "2026-08-15T10:33:19", "nivel": "INFO", "logger": "tributia.requests", "mensaje": "request_completada", "request_id": "f716d205-ea3d-4f70-bf04-4e31c1f12110", "metodo": "POST", "ruta": "/api/v1/analizar-documento/", "status": 400, "duracion_ms": 1830.1}
```

**Interpretación:** el `tipo_error` (`archivo_invalido`) queda registrado explícitamente, sin necesidad de inspeccionar el código de status por separado, y correlacionado con el mismo `request_id` que aparece en el header `X-Request-ID` de la respuesta al cliente.

## 4. Datos excluidos por privacidad/seguridad

Los logs de esta entrega **nunca incluyen**:

- Contenido del documento ni el texto extraído por OCR (`texto_extraido` nunca se loguea, solo su longitud en caracteres).
- Datos personales del documento o del usuario: NIT, DUI, nombre de empresa/cliente, dirección, correo, teléfono (todo esto vive en la base de datos, no en los logs).
- Credenciales o secretos: `GEMINI_API_KEY`, `SECRET_KEY`, contraseñas, cookies de sesión, tokens CSRF, encabezados `Authorization`.
- Cuerpo completo de la request/response (el middleware solo registra método, ruta, status y duración — nunca el payload).
- Nombre real del archivo subido por el usuario (podría contener información personal puesta por el usuario en el nombre).

Lo que sí se loguea son identificadores internos (`documento_id`, que es solo un entero autoincremental de la base de datos) y metadatos operativos (duración, etapa, tipo de error, modelo usado).

## 5. Escenario y resultados de la medición de rendimiento

**Ambiente:** contenedor Docker (`docker compose up -d --build`), `web` (Django + gunicorn, 3 workers) + `db` (PostgreSQL 16), igual que en Semana 4. Medido desde el equipo host (Windows) contra `http://localhost:8000` publicado por Docker Desktop.
**Versión del código:** commit `78a35c9` + los cambios de instrumentación de esta entrega (Semana 5, sobre `main`).
**Componente IA:** `gemini-2.5-flash-lite` (`core/ia/gemini_client.py::MODEL_NAME`).
**Herramienta:** `scripts/medir_rendimiento.py` (script propio, sin dependencias nuevas — usa `urllib`/`statistics` de la librería estándar).

### Escenario A — línea base (20 solicitudes reales), `GET /api/v1/health/`

Se eligió `/health/` para la línea base de 20+ solicitudes en vez del endpoint de análisis porque este último consume cuota real y limitada de la API de Gemini (riesgos #1/#2 de `riesgos-tecnicos.md`); 20 llamadas reales a Gemini solo para una medición de rendimiento no es un uso justificable de esa cuota compartida entre el equipo. `/health/` sí ejecuta trabajo real (consulta a PostgreSQL + verificación de Tesseract) dentro del mismo contenedor Docker, por lo que sigue siendo una medición válida de la infraestructura real.

```bash
$ python scripts/medir_rendimiento.py --url http://localhost:8000/api/v1/health/ --n 20 --salida docs/medicion_health.json
[1/20] status=200 duracion_ms=86.1
[2/20] status=200 duracion_ms=11.8
[3/20] status=200 duracion_ms=10.6
...
[20/20] status=200 duracion_ms=11.4

=== Resultado ===
{
  "url": "http://localhost:8000/api/v1/health/",
  "metodo": "GET",
  "n": 20,
  "p50_ms": 12.1,
  "p95_ms": 35.6,
  "max_ms": 86.1,
  "min_ms": 10.6,
  "promedio_ms": 17.9,
  "tasa_error_pct": 0.0,
  "errores": 0
}
```

Resultado completo (20 solicitudes individuales) guardado en [`docs/medicion_health.json`](medicion_health.json).

**Interpretación:** 0% de tasa de error en las 20 solicitudes. p50 de 12.1 ms y p95 de 35.6 ms — muy rápido, coherente con un endpoint que solo hace una consulta liviana a PostgreSQL y una verificación de binario en disco. El máximo (86.1 ms, en la primera solicitud) es un efecto de arranque en frío, no representativo del resto de la muestra.

### Escenario B — muestra real del flujo crítico, `POST /api/v1/analizar-documento/`

Muestra más pequeña (3 llamadas reales, no 20, por la razón de cuota explicada arriba) para caracterizar la latencia real del pipeline completo de IA y compararla contra el Escenario A.

| # | `documento_id` | extracción (ms) | spaCy (ms) | Gemini (ms) | **Pipeline total (ms)** | Request HTTP total (ms) | Status |
|---|---|---|---|---|---|---|---|
| 1 | 2 | 67.3 | 58.8 | 2312.6 | **2470.0** | 4043.7 * | 201 |
| 2 | 3 | 73.3 | 63.5 | 2180.7 | **2342.3** | 2396.5 | 201 |
| 3 | 4 | 89.9 | 49.9 | 1562.2 | **1715.3** | 1780.4 | 201 |

\* La solicitud #1 fue la primera tras `docker compose up` (efecto de arranque en frío, ver sección 6). Las solicitudes #2 y #3 muestran que, una vez caliente, la duración del request HTTP prácticamente coincide con la del pipeline interno (diferencia de 50-60 ms, el overhead normal de Django/gunicorn).

**Comparación directa contra el Escenario A:** el endpoint de análisis (~1.7–2.5 s) es **entre 140x y 200x más lento** que `/health/` (p50 12.1 ms) — y en las 3 muestras, la llamada a Gemini por sí sola (1.56–2.31 s) explica entre el 87% y el 94% del tiempo total del pipeline.

## 6. Cuello de botella / riesgo identificado

### Cuello de botella confirmado: la llamada a Gemini domina el pipeline

Los números de la sección 5 confirman con evidencia medida (no solo teórica) el riesgo #4 ya documentado en `riesgos-tecnicos.md`: el pipeline de análisis ejecuta OCR/extracción + spaCy + Gemini de forma **síncrona dentro del mismo request**, y la llamada a Gemini (1.56–2.31 s) explica 87–94% del tiempo total — extracción de texto y spaCy juntas nunca superan los 165 ms. Con gunicorn corriendo 3 workers síncronos (`Dockerfile`), en el peor caso solo 3 análisis pueden procesarse en paralelo; cualquier solicitud adicional simultánea queda en cola esperando a que un worker se libere durante 1.5-2.5 segundos.

### Comportamiento inesperado: latencia elevada y variable en la primera solicitud tras iniciar el contenedor

La primera solicitud medida tras `docker compose up -d --build` (tanto a `/health/` vía `curl` como al endpoint de análisis) mostró una duración de request HTTP notablemente mayor que las siguientes — en el caso del endpoint de análisis, la solicitud #1 tardó 4043.7 ms de request HTTP contra solo 2470.0 ms de pipeline interno (una diferencia de ~1.57 s no explicada por el propio análisis); las solicitudes #2 y #3, ya con el contenedor "caliente", no mostraron esa diferencia. El mismo patrón apareció en las primeras llamadas a `/health/` vía `curl` (~1.7-1.8 s) antes de correr el script de medición, que en cambio mostró un p50 de solo 12.1 ms sobre 20 solicitudes.

**Interpretación:** es consistente con un efecto de "arranque en frío" (cold start) — ya sea de la conexión inicial a PostgreSQL, de imports diferidos de Python en el primer request que atiende cada worker de gunicorn, o de la resolución de `localhost` del lado del cliente en Windows. No se investigó a fondo la causa exacta porque no es parte del alcance de esta entrega, pero queda documentado como comportamiento a vigilar: **la primera solicitud tras un despliegue o reinicio no es representativa de la latencia normal del servicio.**

## 7. Mejora aplicada (con comparación antes/después)

**Antes:** con `DEBUG=False` (configuración real del contenedor Docker), ningún log de la aplicación llegaba a ningún lado — ni a consola ni a archivo. El bug `InvalidStorageError` de Semana 4 solo pudo diagnosticarse levantando manualmente una segunda instancia del contenedor con `DEBUG=True` (ver `docs/despliegue-semana4.md` §9.2).

**Después:** `LOGGING` configurado explícitamente en `settings.py` (sección 3 de este documento) — los logs se ven siempre, en cualquier ambiente, en formato JSON estructurado, correlacionados por `request_id`, sin depender de `DEBUG`. Evidencia real (mismo contenedor, `DEBUG=False`, sección 3 de este documento): las secciones "Evidencia de una solicitud exitosa" y "Evidencia de una entrada inválida" de arriba muestran logs completos, con `request_id`, duración por etapa y `tipo_error`, visibles con un simple `docker compose logs web`.

Bonus de esta entrega: instrumentar el middleware reveló un **segundo bug real** — la primera versión de `core/middleware.py` reseteaba la variable de contexto (`request_id_var.reset(token)`) *antes* de emitir su propio log `request_completada`, así que ese log específico salía con `request_id: null` (verificado en vivo: `{"...", "mensaje": "request_completada", "request_id": null, ...}`). Corregido moviendo el `logger.log(...)` a dentro del bloque `try`, antes del `reset()` en el `finally`. Verificado de nuevo tras el fix: `request_id` aparece correcto en todos los logs mostrados en este documento.

## 8. Plan de escalabilidad

**¿Qué crecimiento se está considerando y cuál es la restricción observada?**
Más usuarios subiendo documentos de forma concurrente. La restricción observada (sección 6) es que el pipeline de análisis corre síncrono dentro del mismo worker de gunicorn que atiende la request HTTP — el número de análisis simultáneos está limitado al número de workers (3 en la configuración actual de `Dockerfile`), no a la capacidad real de CPU/red disponible.

**¿Qué mejora debe realizarse primero?**
Mover el pipeline de análisis a una cola de tareas asíncrona (Celery o RQ + Redis), como ya estaba planeado en `docs/arquitectura-objetivo.md` — la vista devuelve inmediatamente un `202 Accepted` con un ID de tarea, y el análisis corre en un worker separado. Esto es lo que más impacto tendría porque ataca directamente el cuello de botella medido, no una optimización menor.

**¿Cuándo convendría usar caché, workers, colas o más instancias?**
- **Cola de tareas:** en cuanto el volumen de documentos supere lo que 2-3 workers síncronos puedan procesar sin generar timeouts perceptibles para el usuario (ver indicador abajo).
- **Caché:** de resultados de análisis por hash del archivo, para no volver a llamar a Gemini si alguien sube el mismo documento dos veces (reduce consumo de cuota, no solo latencia).
- **Más instancias/workers:** solo tiene sentido después de mover a cola de tareas — agregar más workers síncronos hoy solo movería el cuello de botella a la cuota de Gemini (riesgo #1), no lo resolvería.

**¿Qué impacto tendría en memoria, datos, privacidad y costo?**
- **Memoria:** Redis como broker de la cola agrega un servicio más al `docker-compose.yml` (RAM adicional, aunque modesta para el volumen de un proyecto académico).
- **Datos/privacidad:** la cola tendría que transportar temporalmente el texto extraído del documento (dato potencialmente sensible) entre el proceso web y el worker — hay que definir un TTL corto y borrado del mensaje tras procesarse, no persistirlo en la cola más de lo necesario.
- **Costo:** un servicio (worker) adicional corriendo permanentemente tiene costo de hosting incluso en los momentos sin carga; en los free tiers evaluados en `docs/despliegue-semana4.md` §11 esto probablemente ya no entra gratis.

**¿Qué indicador permitiría decidir cuándo escalar?**
El **p95 de duración** del endpoint `/api/v1/analizar-documento/` sostenido por encima de un umbral (ej. 8-10 segundos) durante varias mediciones seguidas, o una **tasa de error/timeout** creciente en los logs del middleware (`status >= 500` o el proxy cortando la conexión), o el consumo de cuota diaria de Gemini acercándose al límite (métrica pendiente, no implementada todavía — ver limitaciones).

## 9. Limitaciones pendientes

- No se implementó la cola de tareas (Celery/RQ) en esta entrega — se documenta como el paso siguiente más importante (arriba), coherente con el alcance de "no es obligatorio implementar infraestructura adicional" del descriptor de esta semana.
- No hay métrica de consumo de cuota de Gemini todavía (mencionada como pendiente desde Semana 4).
- El CI (`ci.yml`) no corre `scripts/medir_rendimiento.py` automáticamente — la medición de esta entrega fue manual.
- Los logs se escriben a `stdout` del contenedor (visibles con `docker compose logs`) pero no se envían a ningún sistema centralizado de agregación (ej. Loki, ELK) — suficiente para el alcance académico actual, pero no para producción real.

---

## Repositorio actualizado

Repositorio: `https://github.com/DanCastSV/TributIA`
