# Respuesta al informe de seguridad de 2026-08-15

**Proyecto:** TributIA

## Origen del informe

Se recibió un PDF ("Sysadmin Operations Report", firmado por "PolarZero", formateado para compartirse en Discord) con hallazgos de seguridad sobre este repositorio, revisado sobre el commit `0181c0a`. El documento afirma que PolarZero desplegó una copia del proyecto (público en GitHub) "en producción" por su cuenta, corrió pruebas y auditorías, y que su propio hosting mitigó parte de lo encontrado (bloqueo de `/media/*`). Nada de eso fue coordinado con el equipo — el repositorio es público, así que cualquiera puede clonarlo y auditarlo, pero no hay forma de verificar la identidad ni las intenciones de quien escribió el informe.

**Por eso, antes de corregir nada, cada hallazgo se verificó de forma independiente contra el código real del repositorio** (no se asumió que el informe fuera exacto). El detalle de esa verificación está más abajo, junto con las correcciones aplicadas.

## Alcance de esta entrega

El informe lista 11 puntos de corrección. Se priorizó el **"primer parche"**: los 4 hallazgos de mayor severidad y menor complejidad, corregidos y verificados hoy. El resto queda documentado como trabajo futuro (sección final).

---

## V-01 — Bypass de CSRF en la API autenticada por sesión

**Verificado:** sí, real. `core/api_views.py` tenía `@csrf_exempt` en `analizar_documento_api`, que autentica por `request.user.is_authenticated` (cookie de sesión) — la combinación permite que un sitio externo fuerce al navegador de un usuario logueado a llamar al endpoint sin su conocimiento.

**Corrección:** se quitó `@csrf_exempt`. El endpoint ahora exige el token CSRF igual que cualquier otra vista autenticada por sesión.

**Pruebas agregadas** (`tests/test_api_seguridad.py`, 5 tests, corridos dentro de Docker):

```text
$ docker compose exec web python manage.py test tests.test_api_seguridad -v 2
test_sesion_valida_sin_token_csrf_devuelve_403 ... ok
test_sesion_valida_con_token_csrf_correcto_pasa_la_proteccion ... ok
test_token_csrf_incorrecto_devuelve_403 ... ok
test_usuario_no_autenticado_con_csrf_valido_devuelve_401 ... ok
test_usuario_no_autenticado_sin_csrf_devuelve_403 ... ok

Ran 5 tests in 2.995s
OK
```

Evidencia real (`docker compose logs`, mismo request correlacionado por `request_id`):

```json
{"nivel": "WARNING", "logger": "django.security.csrf", "mensaje": "Forbidden (CSRF cookie not set.): /api/v1/analizar-documento/", "status_code": 403, "request_id": "..."}
```

**Verificación de que la API real sigue funcionando** con el token correcto (curl real contra el contenedor):

```bash
$ curl -s -b cookies.txt -H "X-CSRFToken: $CSRF" -X POST \
    -F "archivo=@factura.pdf" -w "\nHTTP_STATUS:%{http_code}\n" \
    http://localhost:8000/api/v1/analizar-documento/
HTTP_STATUS:201
```

`docs/api.md` se actualizó con el nuevo contrato (el cliente debe incluir el token CSRF).

---

## V-02 — Documentos accesibles por URL directa sin autorización

**Verificado, con un matiz que el informe no explicaba:** los templates (`detalle_documento.html`, `documentos.html`) sí enlazaban `documento.archivo.url` directo. Pero en `core/urls.py`, Django solo sirve `/media/` cuando `DEBUG=True` — con `DEBUG=False` (nuestro Docker real), Django no expone `/media/` en absoluto. Es decir: la ruta de explotación que describe el informe probablemente pasó por el mismo hallazgo V-05 (el `DEBUG` fail-open) — si su copia corrió con `DEBUG=True` por no definir la variable, ahí sí quedó expuesto.

De cualquier forma, depender únicamente de que `DEBUG` esté bien configurado es seguridad frágil (un solo punto de falla). Se corrigió en el código, no solo en la configuración.

**Corrección:** nueva vista `core/views.py::descargar_documento` (ruta `/documento/<id>/descargar/`), con `@login_required` y `get_object_or_404(..., usuario=request.user)` — la misma convención de autorización que ya usan `detalle_documento` y `eliminar_documento`. Sirve el archivo con `FileResponse` + header `X-Content-Type-Options: nosniff` y `Cache-Control: private`. Los dos templates se actualizaron para usar esta vista en vez de `archivo.url`.

**Prueba obligatoria del informe, verificada en vivo contra el contenedor real** (dos usuarios distintos, `usuario_a` sube un documento, `usuario_b` intenta descargarlo):

```bash
$ curl -s -b cookies_b.txt -o /dev/null -w "HTTP_STATUS:%{http_code}\n" \
    http://localhost:8000/documento/5/descargar/
HTTP_STATUS:404

$ curl -s -b cookies_a.txt -o descarga.pdf -w "HTTP_STATUS:%{http_code}\n" \
    http://localhost:8000/documento/5/descargar/
HTTP_STATUS:200
$ file descarga.pdf
descarga.pdf: PDF document, version 1.4, 1 page(s)
```

`usuario_b` recibe `404` (no `200` con el archivo de otro usuario); `usuario_a` descarga su propio documento correctamente. También se confirmó que `/media/...` directo devuelve `404` en el contenedor real (`DEBUG=False`).

---

## V-03 — Dependencias vulnerables (Django, Pillow)

**Verificado:** `requirements.txt` fijaba `Django==6.0.3` y `Pillow==12.2.0`.

**Corrección:** actualizado a `Django==6.0.7` y `Pillow==12.3.0` (mínimos parcheados al 2026-08-15, según el informe). Se reconstruyó la imagen Docker desde cero:

```text
$ docker compose up -d --build
...
Successfully installed Django-6.0.7 ... Pillow-12.3.0 ...
Image tributia-web Built
```

**Verificación post-actualización:** suite completa de tests corrida dentro del contenedor reconstruido:

```text
$ docker compose exec web python manage.py test
Ran 29 tests in 3.243s
OK
```

(24 tests previos + 5 nuevos de CSRF, todos pasando con las versiones actualizadas — no hubo regresiones por el upgrade.)

**Pendiente:** no se corrió `pip-audit` en esta entrega (no está instalado ni en CI todavía); el informe original es la única fuente de los CVEs. Agregar `pip-audit` al workflow de CI queda como mejora futura (sección final).

---

## V-05 — `DEBUG` fail-open por defecto

Aunque no estaba en el "primer parche" original de 4 puntos, se corrigió junto con V-02 porque es su causa raíz.

**Verificado:** `tributia_project/settings.py` tenía `DEBUG = os.environ.get('DEBUG', 'True') == 'True'` — si la variable de entorno no existía (por ejemplo, un despliegue nuevo que olvida definirla), el valor por defecto era el inseguro.

**Corrección:** `DEBUG = os.environ.get('DEBUG', 'False') == 'True'` — fail-closed. Verificado en el contenedor real:

```text
$ docker compose exec web python manage.py shell -c "from django.conf import settings; print(settings.DEBUG)"
False
```

`.env.example` y `.env` de desarrollo local siguen definiendo `DEBUG=True` explícitamente, así que el flujo de trabajo local no cambia — el fail-closed solo protege el caso de que alguien olvide definir la variable en un entorno nuevo.

---

## No abordado en esta entrega (queda como plan)

Del resto de los 11 puntos del informe, lo que no se implementó como código en esta entrega:

| # | Hallazgo | Motivo para no abordarlo ahora |
|---|---|---|
| V-04 | Validación profunda de archivos (magic bytes, límite de páginas/megapíxeles) | Requiere agregar lógica de validación de contenido real, no solo extensión — alcance mayor al "primer parche" acordado |
| V-05 (resto) | Antivirus/CDR, imagen Docker no-root/multi-stage | Cambios de infraestructura más profundos; el `Dockerfile` actual sigue corriendo como root |
| V-06 | Rate limiting / cuotas antiabuso | No hay solución nativa en Django; requiere una librería nueva o Redis, cambio de mayor alcance |
| R-01 | Validación estructurada de la salida de Gemini / defensa contra prompt injection | Requiere JSON Schema/Pydantic y pruebas adversarias nuevas |
| R-02 | Revisión profesional de las reglas fiscales (`core/datos_el_salvador.py`) | No es una corrección de código — requiere a un contador/abogado salvadoreño real, fuera del alcance de este equipo |
| R-03 | Cola de tareas para el pipeline síncrono | Ya documentado como pendiente desde `docs/observabilidad-semana5.md` |
| R-04 | Migrar de `google-generativeai` a `google-genai` | Cambio de SDK con superficie amplia (dos módulos lo usan); requiere pruebas de regresión completas |
| R-06 | Reemplazar `except Exception: pass` por logging con tipo de error | Mejora menor, priorizable en una próxima iteración junto con V-04 |

## Repositorio actualizado

`https://github.com/DanCastSV/TributIA`