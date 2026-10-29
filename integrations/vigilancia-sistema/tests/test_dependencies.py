import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pins(path):
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        m = re.match(r"^([A-Za-z0-9_.-]+)(\[[^\]]*\])?==([\w.]+)$", line)
        if m: out[m.group(1).lower().replace("_", "-")] = m.group(3)
    return out


def test_every_requirement_is_exactly_pinned():
    for f in ROOT.rglob("requirements*.txt"):
        if "node_modules" in f.parts: continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if line and not line.startswith(("-r", "-c")):
                assert "==" in line, f"{f.relative_to(ROOT)}: «{line}» no está fijado con =="


def test_no_service_contradicts_constraints():
    cons = _pins(ROOT / "constraints.txt")
    for f in ROOT.rglob("requirements.txt"):
        for name, ver in _pins(f).items():
            if name in cons: assert cons[name] == ver, f"{f.relative_to(ROOT)}: {name}=={ver} != constraints {cons[name]}"


def test_dockerfiles_install_from_requirements_not_inline():
    for d in (ROOT / "services").glob("*/Dockerfile"):
        text = d.read_text(encoding="utf-8")
        assert "-r requirements.txt" in text, f"{d.parent.name}: Dockerfile sin requirements.txt"
        assert (d.parent / "requirements.txt").exists(), d.parent.name


def test_services_import_only_declared_third_party_packages():
    declared_map = {"aio_pika": "aio-pika", "asyncpg": "asyncpg", "redis": "redis", "prometheus_client": "prometheus-client",
                    "httpx": "httpx", "fastapi": "fastapi", "pydantic": "pydantic", "paho": "paho-mqtt", "cryptography": "cryptography"}
    for svc in (ROOT / "services").iterdir():
        req = svc / "requirements.txt"
        if not req.exists(): continue
        declared = set(_pins(req))
        for py in (svc / "src").rglob("*.py"):
            for mod in re.findall(r"^\s*(?:import|from)\s+([A-Za-z_]\w*)", py.read_text(encoding="utf-8"), re.M):
                pkg = declared_map.get(mod)
                if pkg: assert pkg in declared, f"{svc.name}/{py.name} importa {mod} pero requirements.txt no declara {pkg}"
