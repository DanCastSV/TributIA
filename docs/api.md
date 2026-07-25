# API Interna — TributIA (`/api/v1/`)

**Objetivo:** exponer la capacidad de IA del proyecto (OCR + spaCy + Gemini) como una API consumible desde clientes externos (curl, Postman, Swagger, etc.), sin duplicar lógica: los tres endpoints reutilizan directamente `core/services/analizador.py`, el mismo pipeline que usa la vista web de subida de documentos (`core/views.py::documentos`).

**Base URL (desarrollo local):** `http://127.0.0.1:8000/api/v1/`

**Herramienta usada para probar:** `curl` desde línea de comandos (Git Bash en Windows), contra el servidor de desarrollo (`python manage.py runserver`).

---

## 1. `GET /api/v1/health/`

Verifica que el servicio y sus dependencias externas estén disponibles: conexión a la base de datos, binario de Tesseract encontrado en el sistema, y `GEMINI_API_KEY` configurada. No autenticado (endpoint informativo).

No hace una llamada real a Gemini en cada chequeo (para no consumir cuota); solo confirma que la API key está presente en la configuración.

**Respuesta exitosa — `200 OK`:**

```json
{
  "status": "ok",
  "checks": {
    "base_datos": "ok",
    "tesseract": "ok",
    "gemini_api_key": "configurada"
  }
}
```

Si alguna dependencia falla, responde `503 Service Unavailable` con `"status": "degraded"` y el detalle de qué check falló (`"error"`, `"no_encontrado"` o `"faltante"` según el caso).

**Evidencia de prueba (curl real, capturada en desarrollo):**

```bash
$ curl -s http://127.0.0.1:8000/api/v1/health/
{"status": "ok", "checks": {"base_datos": "ok", "tesseract": "ok", "gemini_api_key": "configurada"}}
```

---

## 2. `GET /api/v1/metadata/`

Informa propósito, versión y tecnología del servicio de IA. No autenticado.

**Respuesta exitosa — `200 OK`:**

```json
{
  "nombre": "TributIA - Analizador de Documentos Tributarios",
  "version": "1.0.0",
  "descripcion": "Analiza documentos tributarios (facturas, constancias, comprobantes) en PDF/PNG/JPG: extrae texto (OCR), identifica entidades y montos, clasifica si es tributario/deducible, y genera un resumen y una recomendación en lenguaje natural.",
  "tecnologia": {
    "ocr": "Tesseract OCR (pytesseract) + PyMuPDF (texto embebido en PDF)",
    "nlp": "spaCy (es_core_news_sm)",
    "llm": "Google Gemini (gemini-2.5-flash-lite)"
  },
  "endpoint_principal": { "ruta": "/api/v1/analizar-documento/", "metodo": "POST" },
  "formatos_soportados": ["pdf", "png", "jpg", "jpeg"],
  "tamano_maximo_mb": 20,
  "autenticacion": "Sesión de Django (login requerido)"
}
```

**Evidencia de prueba (curl real):**

```bash
$ curl -s http://127.0.0.1:8000/api/v1/metadata/
{"nombre": "TributIA - Analizador de Documentos Tributarios", "version": "1.0.0", ...}
```

---

## 3. `POST /api/v1/analizar-documento/`

Endpoint principal de IA. Sube un documento tributario y ejecuta el pipeline completo: extracción de texto (PyMuPDF si el PDF trae texto digital, o Tesseract OCR si es un escaneo/imagen) → extracción de montos e identificadores por regex → reconocimiento de entidades con spaCy → clasificación, corrección de entidades y generación de resumen/recomendación con Gemini. El resultado se guarda como `AnalisisDocumento` asociado al usuario autenticado, igual que si se subiera desde la interfaz web.

### Autenticación

Requiere **sesión de Django autenticada** (el mismo login que usa la interfaz web en `/login/`). El endpoint asocia el documento al usuario de la sesión (`request.user`), por lo que no acepta llamadas anónimas.

Por ser una API pensada para clientes externos (curl/Postman), la vista está marcada `@csrf_exempt` — el login inicial sí requiere CSRF token (es un formulario normal de Django), pero las llamadas subsecuentes a la API dentro de esa sesión no lo requieren. Esta es una decisión consciente de alcance para Semana 2; en Semana 6 (seguridad) se evaluará reemplazar la autenticación por sesión con un esquema de token dedicado para la API.

**Cómo obtener una sesión con curl:**

```bash
# 1. Obtener cookie CSRF inicial
curl -s -c cookies.txt http://127.0.0.1:8000/login/ -o /dev/null
CSRF=$(grep csrftoken cookies.txt | awk '{print $7}')

# 2. Iniciar sesión (guarda la cookie de sesión en cookies.txt)
curl -s -b cookies.txt -c cookies.txt -X POST \
  -d "username=TU_USUARIO&password=TU_PASSWORD&csrfmiddlewaretoken=$CSRF" \
  -e "http://127.0.0.1:8000/login/" \
  http://127.0.0.1:8000/login/
```

### Payload de entrada (`multipart/form-data`)

| Campo     | Tipo   | Obligatorio | Descripción                                              |
|-----------|--------|:-----------:|-----------------------------------------------------------|
| `archivo` | file   | Sí          | PDF, PNG, JPG o JPEG. Máximo 20MB.                        |
| `nombre`  | string | No          | Nombre a mostrar. Si se omite, se usa el nombre del archivo. |

### Validaciones aplicadas

- Debe existir el campo `archivo` en la petición.
- Extensión permitida: `pdf`, `png`, `jpg`, `jpeg` (mismas reglas que usa la subida web, vía `core/ocr_utils.py::validar_archivo`).
- Tamaño máximo: 20MB.
- Usuario debe estar autenticado.
- Si Gemini determina que el documento **no es un documento tributario válido** en El Salvador, se rechaza (no se guarda) con un motivo específico.

### Respuesta exitosa — `201 Created`

```json
{
  "documento_id": 60,
  "nombre": "constancia.pdf",
  "estado": "analizado",
  "es_documento_tributario": true,
  "es_deducible": null,
  "confianza_clasificacion": 0.24,
  "tipo_documento_detectado": "Constancia Salarial",
  "entidades": {
    "empresa": null,
    "cliente": "Daniel",
    "fecha_documento": null,
    "numero_documento": null,
    "direccion": "Retención",
    "nit_tradicional": "0614-123456-102-1",
    "identificador_homologado": null,
    "nrc": null,
    "telefono": "0614-1234",
    "correo": null,
    "giro": null
  },
  "montos": {
    "subtotal": null,
    "iva": null,
    "otros_cargos": null,
    "total": null
  },
  "resumen_ia": "Este documento parece ser una constancia salarial para Daniel, que detalla su salario mensual de $1200 y una retención de ISR de $35. No se identifica la empresa emisora ni la fecha.",
  "recomendacion_ia": "Se recomienda solicitar a la empresa emisora la fecha del documento y la identificación completa de la misma (nombre y NIT)...",
  "justificacion_deducible": "El documento en sí no representa un gasto deducible..."
}
```

**Evidencia de prueba exitosa (curl real, capturada en desarrollo):**

```bash
$ curl -s -b cookies.txt -X POST \
    -F "archivo=@media/documentos/constancia.pdf" \
    -w "\nHTTP_STATUS:%{http_code}\n" \
    http://127.0.0.1:8000/api/v1/analizar-documento/

HTTP_STATUS:201
# (respuesta JSON completa arriba)
```

### Respuestas con error

| Caso                                   | Status | Cuerpo                                                                                                   |
|-----------------------------------------|:------:|------------------------------------------------------------------------------------------------------------|
| Sin sesión autenticada                  | `401`  | `{"error": "no_autenticado", "detalle": "Debes iniciar sesión para usar este endpoint."}`                 |
| Sin campo `archivo`                     | `400`  | `{"error": "archivo_faltante", "detalle": "Debes enviar un archivo en el campo \"archivo\" (multipart/form-data)."}` |
| Extensión no permitida / archivo > 20MB | `400`  | `{"error": "archivo_invalido", "detalle": "Extensión no permitida. Use: pdf, png, jpg, jpeg"}`             |
| Gemini rechaza el documento (no tributario) | `422`  | `{"error": "documento_no_tributario", "detalle": "<motivo específico de Gemini>"}`                          |
| Error inesperado en el pipeline (OCR/spaCy/Gemini) | `500`  | `{"error": "error_interno", "detalle": "Ocurrió un error al procesar el documento. Inténtalo de nuevo."}` |

**Evidencia de pruebas de error (curl real, capturadas en desarrollo):**

```bash
# Sin sesión (401)
$ curl -s -X POST -F "archivo=@prueba.txt" -w "\nHTTP_STATUS:%{http_code}\n" \
    http://127.0.0.1:8000/api/v1/analizar-documento/
{"error": "no_autenticado", "detalle": "Debes iniciar sesión para usar este endpoint."}
HTTP_STATUS:401

# Sin archivo (400)
$ curl -s -b cookies.txt -X POST -w "\nHTTP_STATUS:%{http_code}\n" \
    http://127.0.0.1:8000/api/v1/analizar-documento/
{"error": "archivo_faltante", "detalle": "Debes enviar un archivo en el campo \"archivo\" (multipart/form-data)."}
HTTP_STATUS:400

# Extensión inválida (400)
$ curl -s -b cookies.txt -X POST -F "archivo=@prueba.txt" -w "\nHTTP_STATUS:%{http_code}\n" \
    http://127.0.0.1:8000/api/v1/analizar-documento/
{"error": "archivo_invalido", "detalle": "Extensión no permitida. Use: pdf, png, jpg, jpeg"}
HTTP_STATUS:400

# Documento real rechazado por Gemini por no ser tributario (422)
$ curl -s -b cookies.txt -X POST -F "archivo=@media/documentos/factura_medica_ejemplo.pdf" \
    -w "\nHTTP_STATUS:%{http_code}\n" http://127.0.0.1:8000/api/v1/analizar-documento/
{"error": "documento_no_tributario", "detalle": "El documento explícitamente indica ser una 'Factura Médica' y que 'NO VALIDO COMO COMPROBANTE FISCAL'. Por lo tanto, no cumple los requisitos para ser un documento tributario deducible en El Salvador."}
HTTP_STATUS:422
```

---

## Limitaciones conocidas

- La API comparte la cuota de Google Gemini (`gemini-2.5-flash-lite`) con la interfaz web; llamadas frecuentes pueden agotarla (ver `docs/riesgos-tecnicos.md`).
- El pipeline se ejecuta de forma síncrona dentro del request (sin cola de tareas); documentos grandes o Gemini lento pueden tardar varios segundos en responder.
- La autenticación por sesión + `@csrf_exempt` es una solución pragmática para Semana 2; no es el mecanismo recomendado para una API pública en producción (ver Semana 6 en `docs/plan-mejora.md`).
