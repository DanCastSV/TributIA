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

- [ ] Crear `Dockerfile` que incluya Tesseract y dependencias de spaCy.
- [ ] Crear `docker-compose.yml` (app + PostgreSQL + Redis para cola de tareas).
- [ ] Migrar la base de datos de SQLite a PostgreSQL para el entorno de staging.
- [ ] Mover el pipeline de análisis a ejecución asíncrona (Celery/RQ) en vez de bloquear el request.

## Semana 5 — Observabilidad, rendimiento y escalabilidad

- [ ] Agregar logging estructurado por etapa del pipeline (OCR, spaCy, Gemini) con tiempos de ejecución.
- [ ] Crear endpoint `/health/` que valide conexión a BD, disponibilidad de Gemini y Tesseract.
- [ ] Agregar métrica de consumo diario de la cuota de Gemini.
- [ ] Evaluar cacheo de resultados de análisis por hash de documento para reducir llamadas repetidas a Gemini.

## Semana 6 — Seguridad, documentación final y defensa técnica

- [ ] Auditar y eliminar cualquier credencial hardcodeada remanente fuera de `.env`.
- [ ] Agregar validaciones de permisos para que cada usuario solo acceda a sus propios documentos/eventos.
- [ ] Consolidar README y `docs/` con el estado final del proyecto.
- [ ] Preparar demo en vivo: identificar puntos frágiles del pipeline (ej. límite de cuota de Gemini) y tener un plan B si falla durante la defensa (documento de respaldo ya analizado, capturas de pantalla).
