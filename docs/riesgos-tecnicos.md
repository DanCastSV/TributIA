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
| 10 | Seguridad | ~~Sin validación explícita de que un usuario solo pueda acceder a sus propios documentos/eventos vía URL directa~~ — **Mitigado, verificado en Semana 4**: se auditó `core/views.py` y las 5 vistas que acceden a un recurso por ID (`detalle_documento`, `eliminar_documento`, `eliminar_evento`, envío y eliminación de conversación) filtran consistentemente por `usuario=request.user`, y las vistas de creación (`crear_evento`, etc.) asignan el dueño correcto. No se encontró ningún `.objects.all()` ni `get_object_or_404` sin filtrar por usuario. | ~~Media~~ Baja | ~~Alta~~ Baja | Mantener la convención (`usuario=request.user`) al agregar vistas nuevas; cubrir con un test de regresión en Semana 5-6 (ej. usuario A no puede ver/borrar recurso de usuario B) para que quede garantizado por CI y no solo por auditoría manual |
| 11 | Equipo | Dependencia de una sola cuenta/API key de Gemini compartida entre los 3 integrantes del equipo | Media | Media | Documentar proceso de rotación de key; considerar variables de entorno por entorno (dev/prod) |
| 12 | Despliegue | ~~Proyecto solo se ejecuta localmente (`manage.py runserver`), sin contenedor ni entorno de staging~~ — **Mitigado en Semana 4**: `Dockerfile` + `docker-compose.yml` funcionales, probados de punta a punta (build, `/health`, endpoint principal). Pendiente: entorno de staging real en un proveedor (PaaS/cloud), hoy solo corre localmente vía Docker. | ~~Alta~~ Media | Alta | Definir entorno de staging en un proveedor cloud antes de Semana 6 (ver plan de infraestructura en `docs/despliegue-semana4.md`) |
| 13 | Datos | ~~Base de datos SQLite no apta para concurrencia real en producción~~ — **Mitigado en Semana 4**: el contenedor Docker usa PostgreSQL (servicio `db` en `docker-compose.yml`); `settings.py` elige el motor según el entorno. Pendiente: apuntar a una instancia PostgreSQL *administrada* (no el contenedor local) para un despliegue real. | ~~Media~~ Baja | ~~Media~~ Baja | Apuntar `POSTGRES_HOST`/credenciales a un proveedor administrado al definir el entorno de staging |

## Deuda técnica adicional a vigilar

- ~~Ausencia total de pruebas automatizadas~~ — **resuelto en Semana 3**: 22 tests (unitarios + integración) con CI en GitHub Actions (`tests/`, `.github/workflows/ci.yml`).
- ~~No hay versión de la API interna (`/api/v1/`)~~ — **resuelto en Semana 2**: `/api/v1/health/`, `/api/v1/metadata/`, `/api/v1/analizar-documento/`, documentados en `docs/api.md`.
- **Falta de logging estructurado** que dificulta depurar fallos del pipeline de IA en producción — sigue pendiente, y se confirmó de forma concreta en Semana 4: con `DEBUG=False` dentro del contenedor Docker, un error real (`InvalidStorageError`) no dejó ningún rastro en `docker compose logs` porque el logger raíz de Django solo escribe a consola cuando `DEBUG=True`. Prioridad alta para Semana 5.
- El CI de Semana 3 corre `manage.py test` contra SQLite en memoria; no construye ni prueba la imagen Docker ni corre contra PostgreSQL — el build/pruebas de Docker de Semana 4 fueron manuales, no automatizadas en CI todavía.
