FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml requirements.txt ./
# CORRECCIÓN: antes solo se instalaban 6 paquetes, pero app.main importa en el arranque
# fitz/cv2/numpy/trimesh/shapely (floorplan3d); la imagen no podía iniciar. Versiones fijadas.
# tesseract-ocr: binario requerido por pytesseract.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests
RUN mkdir -p /tmp/floorplan3d/uploads /tmp/floorplan3d/outputs

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
