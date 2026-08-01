FROM python:3.13-slim

# tesseract-ocr: motor de OCR usado por core/ocr_utils.py (el paquete de
# idioma español se toma del tessdata/ empaquetado en el repo, no del
# sistema). poppler-utils: requerido por pdf2image para convertir PDF a
# imagen. build-essential: por si alguna dependencia de spaCy no trae
# wheel prebuilt para esta versión de Python y necesita compilar.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# migrate + collectstatic corren al iniciar el contenedor (no en build)
# porque settings.py exige SECRET_KEY/GEMINI_API_KEY vía os.environ[...],
# que solo están disponibles en runtime a través de .env / env_file.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn tributia_project.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
