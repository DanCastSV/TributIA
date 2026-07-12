# Diagnóstico Técnico — Semana 1

**Proyecto:** TributIA
**Módulo:** Módulo 4 — Desarrollo de Aplicaciones con IA
**Fecha:** 11 de julio de 2026

---

## 1. Estado actual del proyecto

TributIA es una plataforma web construida en **Django 6.0.3 / Python 3.13** que permite a contribuyentes salvadoreños subir documentos tributarios (facturas, constancias, comprobantes), analizarlos automáticamente con IA, y gestionar su información fiscal desde un dashboard.

El proyecto se encuentra en etapa de **prototipo funcional**: corre localmente, tiene autenticación de usuarios, flujo completo de análisis de documentos, y un asistente conversacional. No está desplegado en un entorno de producción ni cuenta con pruebas automatizadas, CI/CD, ni contenedores.

## 2. Qué partes funcionan actualmente

- Registro, login, logout y recuperación de contraseña por email.
- Subida de documentos (PDF, PNG, JPG, JPEG) y pipeline de análisis: OCR → extracción regex → spaCy → Gemini → guardado en BD.
- Rechazo automático de documentos no tributarios (`DocumentoNoTributarioError`).
- Dashboard con KPIs financieros, consejo inteligente y próximos eventos.
- Centro de Análisis con métricas y ahorro estimado de ISR.
- Calendario fiscal con eventos manuales y auto-generados al detectar fechas en documentos.
- Asistente IA multi-turno con contexto del perfil y documentos del usuario.
- Perfil tributario con barra de progreso de completitud.
- Cálculo real (no hardcodeado) de confianza de clasificación por documento.
- Variables sensibles movidas a `.env`.

## 3. Qué partes son manuales, incompletas o frágiles

- **Pipeline de análisis síncrono y bloqueante**: OCR + spaCy + llamada a Gemini se ejecutan en el mismo request HTTP, sin cola de tareas (ej. Celery). Documentos grandes o Gemini lento pueden causar timeouts.
- **Modelo de Gemini fijo por restricción de billing**: solo `gemini-2.5-flash-lite` está disponible sin cargos; `gemini-2.5-flash` tiene tope de 20 solicitudes/día y `gemini-2.0-flash` requiere billing habilitado. Esto limita pruebas y escalabilidad.
- **Manejo de errores incompleto**: no todos los fallos de OCR, spaCy o la API de Gemini están cubiertos con try/except específicos ni con mensajes claros al usuario.
- **Carga de modelos en tiempo de import**: spaCy y el cliente de Gemini se inicializan al importar el módulo, lo que incrementa el tiempo de arranque del servidor y complica pruebas unitarias aisladas.
- **Código muerto**: existen funciones/rutas de versiones anteriores del análisis que ya no se usan pero siguen en el repositorio.
- **Sin pruebas automatizadas**: no hay suite de tests (`tests/` vacío o inexistente) que valide el pipeline de análisis ni las vistas.
- **Sin CI/CD ni contenedor**: el proyecto se ejecuta manualmente con `manage.py runserver`, sin Docker ni pipeline de integración continua.

## 4. Dependencias técnicas

| Categoría | Dependencia |
|---|---|
| Backend | Django 6.0.3, Python 3.13 |
| IA generativa | `google-generativeai` 0.8.6 (Gemini `gemini-2.5-flash-lite`) |
| OCR | `pytesseract`, `pdf2image` (requiere Tesseract instalado en el sistema operativo) |
| NLP | spaCy + modelo `es_core_news_sm` |
| PDF | PyMuPDF (`fitz`) para texto embebido |
| Base de datos | SQLite (desarrollo) |
| Email | Gmail SMTP con App Password |
| Config | `python-dotenv` |

## 5. Datos, archivos, servicios o credenciales necesarios

- **API Key de Google Gemini** (variable de entorno, con cuota limitada por billing).
- **Credenciales SMTP de Gmail** (App Password) para envío de correos de recuperación.
- **Tesseract OCR** instalado a nivel de sistema operativo (no es un paquete pip).
- Archivo `.env` con variables como `GEMINI_API_KEY`, `EMAIL_HOST_PASSWORD`, `SECRET_KEY`, etc. (ver `.env.example`).
- Almacenamiento local de archivos subidos vía `MEDIA_ROOT` (no hay almacenamiento en la nube configurado).

## 6. Cómo se ejecuta actualmente

```bash
cd tributia_project
..\venv\Scripts\python.exe manage.py runserver
```

Accesible en `http://127.0.0.1:8000/`. Requiere entorno virtual activado, dependencias instaladas (`requirements.txt`), Tesseract disponible en el PATH del sistema, y `.env` configurado.

## 7. Evidencia de que el prototipo funciona

- Flujo completo probado manualmente: registro → login → subida de documento → análisis con IA → visualización de resultados en `detalle_documento.html`.
- Dashboard muestra KPIs calculados a partir de documentos reales analizados.
- Asistente IA responde con contexto del perfil y documentos del usuario.
- Capturas de pantalla del flujo (agregar en el PDF de evidencia adicional para Canvas).

---

*Este diagnóstico refleja el estado real del proyecto sin ocultar limitaciones, como base para el plan de mejora de las semanas 2 a 6.*
