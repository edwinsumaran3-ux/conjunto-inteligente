# Root context is 00_ERP_Enterprise_v5; no source code is copied from outside it. (.dockerignore excluye node_modules/vendor/dist)
# --- etapa 1: compila el dashboard y el visor BIM ---
FROM node:22-slim AS frontend
WORKDIR /f
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build && npm run build:bim

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.lock /app/requirements.lock
# solo ruedas binarias: sin compiladores ni libpq en la imagen final (menos superficie de ataque)
RUN pip install --no-cache-dir --only-binary=:all: -r /app/requirements.lock
COPY backend /app/backend
COPY migrations /app/migrations
COPY scripts /app/scripts
COPY alembic.ini /app/alembic.ini
COPY --from=frontend /f/dist /app/frontend/dist
ENV BIM_STATIC_DIR=/app/frontend/dist/bim
ENV FRONTEND_STATIC_DIR=/app/frontend/dist
RUN useradd --system --uid 10001 --no-create-home erp && chown -R erp /app
USER erp
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2).status==200 else 1)"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
