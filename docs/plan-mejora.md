# Plan de Mejora — Semanas 2 a 6

**Proyecto:** TributIA

## Semana 2 — API inteligente y contratos de entrada/salida

- [x] Definir y documentar el contrato de `POST /api/v1/analizar-documento/` (entrada: archivo + metadatos; salida: JSON estandarizado). Ver `docs/api.md`.
- [x] Extraer la lógica de `analizador.py` a una capa de servicio reutilizable, invocable desde la vista web y desde la API. (`core/services/analizador.py` ya era esa capa; ahora también la invoca `core/api_views.py`).
- [x] Agregar versionado de API (`/api/v1/`) para no romper el frontend actual con cambios futuros. Endpoints: `/api/v1/health/`, `/api/v1/metadata/`, `/api/v1/analizar-documento/`.
- [x] Documentar el esquema JSON de respuesta (campos, tipos, valores posibles). Ver `docs/api.md`.
- [x] Endpoints `/health/` y `/metadata/` con evidencia de prueba (curl).
- [x] Validación básica de entrada (extensión, tamaño, autenticación) y manejo de errores (400/401/422/500) con evidencia de prueba exitosa y de error controlado.

## Semana 3 — Pruebas, automatización y CI/CD

- [x] Escribir tests unitarios para `ia/extractor.py` (regex de montos/NIT) y para el cálculo de `confianza_clasificacion`. Ver `tests/test_extractor.py` y `tests/test_analizador.py::CalcularConfianzaTests`. Se extrajo `calcular_confianza()` de `analizador.py` a una función pura para poder testearla de forma aislada.
- [x] Escribir tests de integración del flujo completo de análisis, mockeando Gemini y Tesseract. Ver `tests/test_analizador.py::AnalizarDocumentoIntegracionTests` (caso exitoso y caso de rechazo por documento no tributario).
- [x] Configurar GitHub Actions para correr `manage.py test` en cada push/PR. Ver `.github/workflows/ci.yml`.
- [ ] Empezar a retirar código muerto detectado en el diagnóstico. (Pendiente para Semana 4-5; no se tocó en esta entrega para no ampliar el alcance).

### Errores detectados y corregidos en esta entrega

- **Bug real encontrado por los tests** en `core/ia/extractor.py::extraer_resumen_fiscal`: el regex de `TOTAL` (`TOTAL[:\s\$]*([\d,]+\.\d{2})`) no distinguía "TOTAL" de "SUBTOTAL", así que en cualquier documento con ambas líneas (la gran mayoría de facturas reales), el campo `total` capturaba por error el valor del **subtotal**. Corregido agregando un lookbehind negativo (`(?<!SUB)TOTAL...`) en `extraer_resumen_fiscal`. Cubierto por `tests/test_extractor.py::ExtraerResumenFiscalTests::test_extrae_subtotal_iva_y_total`, que falló antes del fix y pasa después.
- Dos fallas iniciales de test resultaron ser expectativas incorrectas en los tests (no bugs de producción): `extraer_montos` sí incluye el signo `$` en los montos devueltos (correcto, ya que solo se usa para mostrar `montos_detectados`, no para cálculos). Se ajustaron las aserciones.

## Semana 4 — Contenedor o despliegue

- [x] Crear `Dockerfile` que incluya Tesseract y dependencias de spaCy. Ver `Dockerfile` y `docs/despliegue-semana4.md`.
- [x] Crear `docker-compose.yml` con servicios `web` + `db` (PostgreSQL). Redis para cola de tareas queda pendiente (ver ítem de abajo), ya que depende de mover primero el pipeline a async — agregarlo antes sería un servicio sin usar.
- [x] Migrar la base de datos de SQLite a PostgreSQL para el entorno del contenedor. `settings.py` usa PostgreSQL automáticamente cuando existe `POSTGRES_HOST` en el entorno (dentro de `docker-compose`) y cae a SQLite en desarrollo local sin Docker, para no romper el flujo de trabajo actual del equipo. Ver `docs/despliegue-semana4.md` §6b.
- [ ] Mover el pipeline de análisis a ejecución asíncrona (Celery/RQ) en vez de bloquear el request. (Pendiente, sigue síncrono también dentro del contenedor).

### Errores detectados y corregidos en esta entrega

- **Bug real encontrado al probar el contenedor**: al agregar `whitenoise` para servir estáticos se definió `STORAGES` en `settings.py` con solo la clave `"staticfiles"`, lo que sobrescribió por completo la configuración de storages de Django y dejó sin `"default"` (el storage usado por la subida de documentos a `MEDIA_ROOT`). Cualquier subida de documento fallaba con `InvalidStorageError: Could not find config for 'default' in settings.STORAGES.`. No se detectó en desarrollo local porque ahí `STORAGES` no estaba definido. Corregido agregando explícitamente la clave `"default"` con `FileSystemStorage`. Ver detalle completo en `docs/despliegue-semana4.md` §9.2.
- **Bloqueo de entorno**: Docker Desktop no arrancaba ("Virtualization support not detected") porque las características de Windows WSL2/Virtual Machine Platform no estaban habilitadas (el hardware sí soportaba virtualización). Resuelto habilitando ambas características vía `dism.exe` y reiniciando Windows. Ver `docs/despliegue-semana4.md` §9.1.

## Semana 5 — Observabilidad, rendimiento y escalabilidad

- [x] Agregar logging estructurado por etapa del pipeline (OCR, spaCy, Gemini) con tiempos de ejecución. `core/middleware.py` (por request, con `request_id`) + instrumentación de `core/services/analizador.py` (por etapa) + `LOGGING` en JSON en `settings.py`, correlacionados y visibles con cualquier valor de `DEBUG`. Ver `docs/observabilidad-semana5.md`.
- [x] ~~Crear endpoint `/health/`~~ — ya existía desde Semana 2 (`/api/v1/health/`, valida BD/Tesseract/`GEMINI_API_KEY`); esta línea del plan estaba desactualizada.
- [ ] Agregar métrica de consumo diario de la cuota de Gemini. Sigue pendiente.
- [x] Medir línea base de rendimiento (`scripts/medir_rendimiento.py`, p50/p95/máximo/tasa de error) y documentar cuello de botella + plan de escalabilidad. Ver `docs/observabilidad-semana5.md`.
- [ ] Evaluar cacheo de resultados de análisis por hash de documento para reducir llamadas repetidas a Gemini.

## Semana 6 — Seguridad, documentación final y defensa técnica

- [ ] Auditar y eliminar cualquier credencial hardcodeada remanente fuera de `.env`.
- [ ] Agregar validaciones de permisos para que cada usuario solo acceda a sus propios documentos/eventos.
- [ ] Consolidar README y `docs/` con el estado final del proyecto.
- [ ] Preparar demo en vivo: identificar puntos frágiles del pipeline (ej. límite de cuota de Gemini) y tener un plan B si falla durante la defensa (documento de respaldo ya analizado, capturas de pantalla).
