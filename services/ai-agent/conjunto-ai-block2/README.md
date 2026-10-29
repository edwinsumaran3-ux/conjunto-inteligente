# Conjunto AI Orchestrator — Bloque 2

Servicio FastAPI para orquestación de agentes, políticas, herramientas y proveedores LLM.

## Incluye

- FastAPI
- configuración por variables de entorno
- health/readiness
- CoreClient con retries y clasificación de errores
- Tool Registry
- herramientas Core
- Policy Engine
- proveedor determinista para pruebas
- endpoints de recepción, diagnóstico y procurement
- schemas con request_id / trace_id
- pruebas unitarias y de integración ligera
- Dockerfile

## Ejecución local

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[test]"
uvicorn app.main:app --reload --port 8000
```

## Pruebas

```bash
pytest -q
```

## Endpoints

- GET /health
- GET /ready
- POST /analyze/reception
- POST /analyze/diagnostic
- POST /procurement/prepare

El proveedor predeterminado es `deterministic`, para que el servicio pueda probarse sin una clave LLM.
