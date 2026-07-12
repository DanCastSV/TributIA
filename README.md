# TributIA

> Plataforma web de gestión fiscal inteligente para contribuyentes salvadoreños.

## 1. Información General

**Módulo:** Módulo 4 - Desarrollo de Aplicaciones con IA
**Semana:** Semana 1 - Diagnóstico y arquitectura inicial
**Nombre del equipo:** TributIA
**Equipo:** 11
**Integrantes:**

- Integrante 1: Daniel Enrique Zaldaña Castillo
- Integrante 2: Edwin Adony Ulloa Díaz
- Integrante 3: Anthony Enrique Alvarenga Mayen

**Docente:** Ing. Marco Arévalo Zambrano

---

## 2. Descripción del Problema

**Descripción:**

> Muchos contribuyentes salvadoreños —especialmente empleados, freelancers y dueños de pequeños negocios— no tienen claridad sobre sus obligaciones tributarias, ni tiempo o conocimiento técnico para interpretar facturas, comprobantes y constancias fiscales, ni para calcular deducciones o proyectar su ISR. Esto ocurre en un contexto donde la gestión tributaria suele hacerse de forma manual, dispersa (papeles, hojas de cálculo, memoria) y sin acompañamiento experto accesible. Una solución con IA aporta valor porque puede leer y clasificar documentos automáticamente, extraer los datos relevantes, y explicarle al usuario en lenguaje simple qué implica cada documento y qué debe hacer con él, algo que de otra forma requeriría conocimiento contable o fiscal especializado.

---

## 3. Usuarios o Beneficiarios

| Usuario / Beneficiario | Necesidad principal | Cómo ayuda la aplicación |
|---|---|---|
| Empleado asalariado | Entender deducciones de ISR/ISSS/AFP y organizar comprobantes | Analiza documentos automáticamente y muestra KPIs claros en el dashboard |
| Freelance / trabajador independiente | Llevar control de ingresos, gastos deducibles y fechas límite | Clasifica documentos como deducibles o no, y genera recordatorios en el calendario fiscal |
| Dueño de pequeña empresa | Organizar comprobantes y anticipar obligaciones fiscales | Centro de análisis con métricas financieras y ahorro estimado de ISR |

---

## 4. Descripción de la Solución

**Descripción:**

> TributIA permite a un contribuyente subir documentos tributarios (facturas, constancias, comprobantes en PDF, PNG o JPG) y recibir un análisis automático: qué tipo de documento es, si es deducible, montos relevantes (subtotal, IVA, total), y una recomendación en lenguaje simple. Como entrada recibe el archivo del documento; como salida entrega datos estructurados (empresa, cliente, fecha, montos, clasificación) más un resumen y una recomendación generados por IA, además de eventos automáticos en el calendario fiscal cuando detecta fechas relevantes. La aplicación automatiza la lectura y clasificación de documentos —tarea que normalmente haría una persona manualmente— y ofrece además un asistente conversacional con contexto del perfil del usuario para resolver dudas tributarias.

---

## 5. Componente de Inteligencia Artificial

| Elemento | Descripción |
|---|---|
| Tipo de IA utilizada | OCR, procesamiento de lenguaje natural (NLP) y modelo generativo (LLM) |
| Modelo, algoritmo o técnica | Tesseract OCR (extracción de texto en escaneados) + PyMuPDF (texto embebido en PDF) + spaCy `es_core_news_sm` (reconocimiento de entidades) + Google Gemini `gemini-2.5-flash-lite` (clasificación, corrección de entidades, resumen y recomendación) |
| Datos de entrada | Archivo del documento tributario (PDF/PNG/JPG) subido por el usuario, más contexto del perfil tributario en el caso del asistente conversacional |
| Resultado generado por la IA | JSON estructurado: tipo de documento, si es tributario y si es deducible, entidades (empresa, cliente, fecha), montos (subtotal, IVA, total), resumen y recomendación en lenguaje natural |
| Métrica o forma de evaluación | `confianza_clasificacion` (0.0–1.0), calculada según cuántos de los 9 campos clave logró extraer Gemini exitosamente |
| Limitaciones actuales | Solo se puede usar `gemini-2.5-flash-lite` sin costo adicional (billing limitado); la precisión depende de la calidad del OCR en documentos escaneados; pipeline síncrono sin reintentos automáticos ante fallos de la API |

**Explicación breve:**

> La IA participa en dos puntos del sistema: (1) el pipeline de análisis de documentos, que combina OCR + spaCy + Gemini para leer, extraer y clasificar la información fiscal de cada documento subido; y (2) el asistente conversacional, que usa Gemini con el contexto del perfil y documentos del usuario para responder preguntas tributarias en lenguaje natural.

---

## 6. Estado Actual del Proyecto

### Funcionalidades que ya funcionan

- Registro, login, logout y recuperación de contraseña por email.
- Subida y análisis IA de documentos (PDF, PNG, JPG, JPEG), con rechazo automático de documentos no tributarios.
- Dashboard con KPIs financieros, consejo inteligente y próximos eventos.
- Centro de Análisis con métricas y ahorro estimado de ISR.
- Calendario fiscal con eventos manuales y auto-generados al detectar fechas en documentos.
- Asistente IA multi-turno con contexto del perfil y documentos del usuario.
- Perfil tributario con barra de progreso de completitud y cálculo real de confianza de clasificación.

### Funcionalidades incompletas o pendientes

- API interna versionada para desacoplar el pipeline de análisis de las vistas web (Semana 2).
- Pruebas automatizadas y CI/CD (Semana 3).
- Contenedor/despliegue y ejecución asíncrona del pipeline (Semana 4).
- Logs estructurados, healthcheck y métricas de uso de Gemini (Semana 5).

### Evidencias actuales

- Flujo funcional probado manualmente: registro → login → subida de documento → análisis con IA → visualización de resultados.
- Ver PDF de evidencia adicional en la entrega de Canvas (capturas de pantalla del flujo).

---

## 7. Arquitectura Actual

**Archivo:** [`docs/arquitectura-actual.md`](docs/arquitectura-actual.md)

**Componentes actuales:**

| Componente | Descripción | Estado actual |
|---|---|---|
| Interfaz | Templates Django (HTML/CSS/JS vanilla, sin frameworks) | Funcional |
| Backend / lógica principal | Vistas Django (`views.py`) que orquestan todo, sin capa de API separada | Funcional, monolítico |
| Componente IA | Pipeline OCR → regex → spaCy → Gemini (`core/services/analizador.py`) | Funcional, síncrono/bloqueante |
| Datos | SQLite + archivos en `MEDIA_ROOT` | Funcional, sin backup |
| Servicios externos | Google Gemini API, Gmail SMTP | Funcional, con límite de cuota en Gemini |
| Configuración | Variables en `.env` vía `python-dotenv` | Implementado |

**Diagrama:** ver [`docs/arquitectura-actual.md`](docs/arquitectura-actual.md) (incluye diagrama Mermaid del flujo completo).

---

## 8. Arquitectura Objetivo

**Archivo:** [`docs/arquitectura-objetivo.md`](docs/arquitectura-objetivo.md)

**Elementos esperados:**

- API interna versionada (`/api/v1/analizar-documento/`) para el pipeline de IA.
- Separación entre interfaz, backend, IA (ejecutada de forma asíncrona con cola de tareas) y datos.
- Suite de pruebas unitarias e integración, con CI en GitHub Actions.
- Variables de entorno documentadas en `.env.example`, sin credenciales hardcodeadas.
- Contenedor Docker (app + PostgreSQL + Redis) para despliegue.
- Logs estructurados, endpoint `/health/` y métrica de consumo de cuota de Gemini.
- Validación de permisos por usuario en endpoints sensibles.

**Diagrama:** ver [`docs/arquitectura-objetivo.md`](docs/arquitectura-objetivo.md) (incluye diagrama Mermaid de la arquitectura objetivo).

---

## 9. Estructura del Repositorio

```text
tributia_project/
  core/
    models.py
    views.py
    urls.py
    forms.py
    datos_el_salvador.py
    ocr_utils.py
    templatetags/
    services/
      analizador.py
      asistente.py
    ia/
      gemini_client.py
      extractor.py
      spacy_processor.py
    static/css/style.css
    templates/
  tributia_project/
    settings.py
    urls.py
  docs/
    diagnostico-semana-1.md
    arquitectura-actual.md
    arquitectura-objetivo.md
    riesgos-tecnicos.md
    plan-mejora.md
  tests/
  tessdata/
    spa.traineddata
    eng.traineddata
  manage.py
  README.md
  requirements.txt
  .env.example
```

**Notas sobre la estructura:**

> `core/` concentra la app principal de Django: modelos, vistas, formularios, datos de referencia fiscal, y dos subcarpetas clave — `services/` con la orquestación del análisis y el asistente, e `ia/` con los módulos específicos de IA (Gemini, extracción regex, spaCy). `docs/` contiene toda la documentación técnica de esta entrega. `tests/` está reservado para la suite de pruebas que se agregará en la Semana 3. `tessdata/` empaqueta el modelo de idioma español de Tesseract OCR (`spa.traineddata`), ya que la instalación de Tesseract a nivel de sistema operativo normalmente solo trae el paquete de inglés por defecto (ver `core/ocr_utils.py`).

---

## 10. Instalación y Ejecución

### Requisitos previos

- Python 3.13
- pip / entorno virtual (`venv`)
- Tesseract OCR instalado a nivel de sistema operativo (no se instala vía pip)

### Instalación

```bash
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### Ejecución

```bash
cd tributia_project
python manage.py migrate
python manage.py runserver
```

Accesible en `http://127.0.0.1:8000/`.

### Variables de entorno

| Variable | Descripción | Obligatoria |
|---|---|---|
| `SECRET_KEY` | Clave secreta de Django | Sí |
| `DEBUG` | Modo debug (`True`/`False`) | Sí |
| `GEMINI_API_KEY` | API key de Google Gemini para análisis y asistente | Sí |
| `EMAIL_HOST_USER` | Cuenta de Gmail usada para envío de correos | Sí |
| `EMAIL_HOST_PASSWORD` | App Password de Gmail (SMTP) | Sí |

---

## 11. Datos Utilizados

| Fuente de datos | Tipo de datos | Uso dentro del proyecto | Observaciones |
|---|---|---|---|
| Documentos subidos por el usuario | PDF/PNG/JPG de facturas, constancias y comprobantes | Input principal del pipeline de análisis IA | Datos privados del usuario, pueden incluir información sensible (NIT, DUI, montos) |
| `core/datos_el_salvador.py` | Tasas fijas de ISR, IVA, ISSS, AFP | Cálculos de KPIs y recomendaciones | Datos públicos de referencia oficial |
| Base de datos SQLite | Perfiles, documentos analizados, eventos, conversaciones | Persistencia de toda la aplicación | Uso en desarrollo; se evalúa PostgreSQL para producción |

**Consideraciones:**

- Los documentos subidos son datos **privados** del usuario y pueden contener información sensible (NIT, DUI, montos, nombres).
- Los datos de tasas fiscales son **públicos** y de referencia oficial de El Salvador.
- La calidad del OCR depende de la calidad de la imagen/escaneo subido; documentos borrosos reducen la precisión de la extracción.

---

## 12. Riesgos Técnicos y Deuda Técnica

Ver detalle completo en [`docs/riesgos-tecnicos.md`](docs/riesgos-tecnicos.md). Riesgos más relevantes:

| Riesgo | Categoría | Probabilidad | Impacto | Mitigación propuesta |
|---|---|---|---|---|
| Cuota de la API de Gemini agotada bajo carga | Modelo | Media | Alta | Cachear resultados, cola con reintentos, monitorear consumo |
| Pipeline de análisis síncrono y bloqueante | Código | Alta | Alta | Mover a cola de tareas (Celery/RQ) |
| Sin validación de permisos por usuario en URLs directas | Seguridad | Media | Alta | Agregar checks de propiedad en todas las vistas sensibles |
| Proyecto solo corre localmente, sin contenedor | Despliegue | Alta | Alta | Dockerizar en Semana 4 |

---

## 13. Plan de Mejora por Semana

Ver detalle completo en [`docs/plan-mejora.md`](docs/plan-mejora.md).

| Semana | Mejora esperada | Evidencia esperada |
|---|---|---|
| Semana 2 | API inteligente (`/api/v1/analizar-documento/`) y contratos de entrada/salida | Endpoint documentado, prueba manual |
| Semana 3 | Pruebas unitarias/integración y CI/CD | Tests, pipeline de GitHub Actions |
| Semana 4 | Contenedor Docker y pipeline asíncrono | Dockerfile, docker-compose, cola de tareas funcionando |
| Semana 5 | Observabilidad y rendimiento | Logs estructurados, endpoint `/health/`, métrica de cuota Gemini |
| Semana 6 | Seguridad, documentación final y defensa | Validación de permisos, README final, demo |

---

## 14. Limitaciones Actuales

- Solo se puede usar el modelo `gemini-2.5-flash-lite` sin incurrir en costos, lo que limita precisión frente a modelos más recientes.
- El pipeline de análisis es síncrono: documentos grandes o Gemini lento pueden causar timeouts.
- No hay pruebas automatizadas ni CI/CD todavía.
- El proyecto no está contenerizado ni desplegado; solo corre en entorno local.
- Manejo de errores incompleto en algunas etapas del pipeline (OCR, spaCy, Gemini).
- Sin validación explícita de permisos por usuario en todas las rutas sensibles.

---

## 15. Evidencias

| Evidencia | Enlace o ubicación | Descripción |
|---|---|---|
| Diagnóstico técnico | `docs/diagnostico-semana-1.md` | Estado actual detallado del proyecto |
| Diagrama arquitectura actual | `docs/arquitectura-actual.md` | Diagrama Mermaid del flujo actual |
| Diagrama arquitectura objetivo | `docs/arquitectura-objetivo.md` | Diagrama Mermaid de la evolución esperada |
| Capturas de pantalla | PDF de evidencia adicional (Canvas) | Flujo de registro, subida y análisis de documento |

---

## 16. Créditos y Referencias

- [Django](https://www.djangoproject.com/) 6.0.3
- [Google Gemini API](https://ai.google.dev/) (`google-generativeai` 0.8.6, modelo `gemini-2.5-flash-lite`)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) vía `pytesseract`
- [spaCy](https://spacy.io/) con modelo `es_core_news_sm`
- [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/) para extracción de texto embebido en PDF
- Íconos: [Lucide](https://lucide.dev/)
- Datos de referencia fiscal: Ministerio de Hacienda de El Salvador (tasas ISR, IVA, ISSS, AFP)

---

## 17. Checklist de Revisión

- [x] El problema está claramente descrito.
- [x] Se explica quién usará o se beneficiará de la aplicación.
- [x] Se identifica dónde está la IA.
- [x] Se describen entradas y salidas.
- [x] Se documenta el estado actual del proyecto.
- [x] Se incluye arquitectura actual.
- [x] Se incluye arquitectura objetivo.
- [x] Se explica cómo ejecutar el proyecto.
- [x] Se identifican riesgos técnicos.
- [x] Se presenta plan de mejora por semana.
- [x] No se incluyen claves, contraseñas ni tokens privados.
