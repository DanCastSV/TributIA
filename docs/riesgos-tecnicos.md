# Riesgos Técnicos y Deuda Técnica

**Proyecto:** TributIA

Probabilidad e Impacto calificados como: **Baja / Media / Alta**

| # | Categoría | Riesgo | Probabilidad | Impacto | Mitigación propuesta |
|---|---|---|---|---|---|
| 1 | Modelo (IA) | Cuota de la API de Gemini agotada (429) al usar `gemini-2.5-flash-lite` bajo carga | Media | Alta | Cachear resultados por hash de documento; agregar cola con reintentos y backoff; monitorear consumo diario |
| 2 | Modelo (IA) | Solo `gemini-2.5-flash-lite` disponible sin billing; modelos más precisos (`gemini-2.5-flash`, `gemini-2.0-flash`) limitados o con costo | Alta | Media | Evaluar presupuesto para billing antes de escalar; documentar el trade-off precisión/costo |
| 3 | Datos | Documentos escaneados de baja calidad reducen precisión del OCR (Tesseract) y por tanto de la extracción posterior | Media | Media | Validar calidad de imagen antes de procesar; permitir corrección manual de campos extraídos |
| 4 | Código | Pipeline de análisis síncrono y bloqueante dentro del request HTTP | Alta | Alta | Mover a cola de tareas (Celery/RQ) en Semana 2–4 |
| 5 | Código | Manejo de errores incompleto en OCR / spaCy / Gemini (fallos silenciosos o mensajes poco claros) | Media | Media | Agregar try/except específicos por etapa con mensajes claros al usuario y logging |
| 6 | Código | Carga de modelos (spaCy, cliente Gemini) en tiempo de import, acoplando arranque del servidor a esos recursos | Baja | Media | Mover a inicialización perezosa (lazy loading) |
| 7 | Código | Código muerto de versiones anteriores del pipeline de análisis | Baja | Baja | Limpieza incremental durante refactor de Semana 2–3 |
| 8 | Dependencias | Tesseract OCR requiere instalación manual a nivel de sistema operativo, no gestionado por pip | Media | Media | Incluir instalación de Tesseract en el `Dockerfile` (Semana 4) |
| 9 | Configuración | Posibles credenciales o valores sensibles aún hardcodeados fuera de `.env` en módulos secundarios | Media | Alta | Auditoría de todo el repo con búsqueda de strings sensibles; migrar todo a `.env` / gestor de secretos |
| 10 | Seguridad | Sin validación explícita de que un usuario solo pueda acceder a sus propios documentos/eventos vía URL directa | Media | Alta | Agregar checks de permisos (`request.user == documento.usuario`) en todas las vistas sensibles |
| 11 | Equipo | Dependencia de una sola cuenta/API key de Gemini compartida entre los 3 integrantes del equipo | Media | Media | Documentar proceso de rotación de key; considerar variables de entorno por entorno (dev/prod) |
| 12 | Despliegue | Proyecto solo se ejecuta localmente (`manage.py runserver`), sin contenedor ni entorno de staging | Alta | Alta | Dockerizar en Semana 4; definir entorno de staging antes de Semana 6 |
| 13 | Datos | Base de datos SQLite no apta para concurrencia real en producción | Media | Media | Migrar a PostgreSQL antes de un despliegue con múltiples usuarios simultáneos |

## Deuda técnica adicional a vigilar

- Ausencia total de pruebas automatizadas (`tests/`) — prioridad alta para Semana 3.
- Falta de logging estructurado que dificulta depurar fallos del pipeline de IA en producción.
- No hay versión de la API interna (`/api/v1/`) — cualquier cambio en el pipeline puede romper el frontend sin aviso.
