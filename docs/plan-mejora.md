# Plan de Mejora — Semanas 2 a 6

**Proyecto:** TributIA

## Semana 2 — API inteligente y contratos de entrada/salida

- [ ] Definir y documentar el contrato de `POST /api/v1/analizar-documento/` (entrada: archivo + metadatos; salida: JSON estandarizado).
- [ ] Extraer la lógica de `analizador.py` a una capa de servicio reutilizable, invocable desde la vista web y desde la API.
- [ ] Agregar versionado de API (`/api/v1/`) para no romper el frontend actual con cambios futuros.
- [ ] Documentar el esquema JSON de respuesta (campos, tipos, valores posibles).

## Semana 3 — Pruebas, automatización y CI/CD

- [ ] Escribir tests unitarios para `ia/extractor.py` (regex de montos/NIT) y para el cálculo de `confianza_clasificacion`.
- [ ] Escribir tests de integración del flujo completo de análisis, mockeando Gemini y Tesseract.
- [ ] Configurar GitHub Actions para correr `manage.py test` en cada push/PR.
- [ ] Empezar a retirar código muerto detectado en el diagnóstico.

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
