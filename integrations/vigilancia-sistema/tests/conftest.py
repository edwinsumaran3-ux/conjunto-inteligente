"""Rutas comunes para las pruebas de vigilancia (compatible con pytest y con run_all.py)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in ("services/agent-orchestrator/src", "infrastructure/postgres", "edge-gateway/src", "shared/libs"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)
