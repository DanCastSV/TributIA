"""
Script de línea base de rendimiento (Semana 5): hace N solicitudes GET a
un endpoint y calcula p50, p95, máximo y tasa de error.

No agrega dependencias nuevas al proyecto a propósito (usa solo
urllib/statistics de la librería estándar), para poder correrlo sin
tocar requirements.txt ni el entorno de producción.

Uso:
    python scripts/medir_rendimiento.py --url http://localhost:8000/api/v1/health/
    python scripts/medir_rendimiento.py --url http://localhost:8000/api/v1/health/ --n 30 --salida docs/medicion_health.json
"""

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request


def _percentil(datos_ordenados, p):
    if not datos_ordenados:
        return None
    k = (len(datos_ordenados) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(datos_ordenados) - 1)
    if f == c:
        return datos_ordenados[f]
    return datos_ordenados[f] + (datos_ordenados[c] - datos_ordenados[f]) * (k - f)


def medir(url, n, metodo="GET", timeout=60):
    duraciones_ms = []
    detalles = []
    errores = 0

    for i in range(1, n + 1):
        inicio = time.perf_counter()
        status = None
        try:
            req = urllib.request.Request(url, method=metodo)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception as e:
            status = None
            print(f"[{i}/{n}] ERROR de conexión: {e}")

        duracion_ms = round((time.perf_counter() - inicio) * 1000, 1)
        duraciones_ms.append(duracion_ms)

        es_error = status is None or status >= 400
        if es_error:
            errores += 1

        detalles.append({"n": i, "status": status, "duracion_ms": duracion_ms})
        print(f"[{i}/{n}] status={status} duracion_ms={duracion_ms}")

    ordenadas = sorted(duraciones_ms)

    resultado = {
        "url": url,
        "metodo": metodo,
        "n": n,
        "p50_ms": round(_percentil(ordenadas, 50), 1),
        "p95_ms": round(_percentil(ordenadas, 95), 1),
        "max_ms": round(max(duraciones_ms), 1),
        "min_ms": round(min(duraciones_ms), 1),
        "promedio_ms": round(statistics.mean(duraciones_ms), 1),
        "tasa_error_pct": round(errores / n * 100, 1),
        "errores": errores,
    }
    return resultado, detalles


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Mide p50/p95/máximo/tasa de error de un endpoint GET (línea base Semana 5)."
    )
    parser.add_argument("--url", required=True, help="URL completa del endpoint a medir")
    parser.add_argument("--n", type=int, default=20, help="Cantidad de solicitudes (mínimo 20 según rúbrica)")
    parser.add_argument("--metodo", default="GET")
    parser.add_argument("--salida", help="Ruta opcional para guardar el resultado en JSON")
    args = parser.parse_args()

    resultado, detalles = medir(args.url, args.n, metodo=args.metodo)

    print("\n=== Resultado ===")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as f:
            json.dump({"resultado": resultado, "detalles": detalles}, f, indent=2, ensure_ascii=False)
        print(f"\nGuardado en {args.salida}")
