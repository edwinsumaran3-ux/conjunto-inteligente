# ==========================================================
# Conjunto Inteligente · Makefile raíz · Bloque 10
# Portable: GNU make 4.3+ / BSD make / Git Bash
# ==========================================================

.DEFAULT:
	@$(MAKE) help

# ---------- Configuración ----------
SERVICE ?=
PROFILE ?=
TIMEOUT ?= 300
TENANT_CODE ?= ABC001
TENANT_NAME ?= Conjunto ABC
TAIL ?= 100
NAME ?=
OUT ?= dump.sql
IN ?=
NO_COLOR ?=
export NO_COLOR

PB_BRIDGE_DIR := services/powerbuilder-bridge/ConjuntoInteligente-Bloque7-PowerBuilder-Bridge/legacy/powerbuilder-admin
DOTNET_PROJECT := $(PB_BRIDGE_DIR)/bridge/ConjuntoInteligente.PbBridge.csproj
DOTNET_TEST_PROJECT := $(PB_BRIDGE_DIR)/tests/ConjuntoInteligente.PbBridge.Tests.csproj
CORE_API_DIR := services/core-api-dotnet
CORE_API_PROJECT := $(CORE_API_DIR)/src/ConjuntoInteligente.CoreApi/ConjuntoInteligente.CoreApi.csproj
CORE_API_TEST_PROJECT := $(CORE_API_DIR)/tests/ConjuntoInteligente.CoreApi.Tests/ConjuntoInteligente.CoreApi.Tests.csproj
COMPOSE_FILE ?= docker-compose.yml
COMPOSE := docker compose -f $(COMPOSE_FILE)
WEB_DIR := 00_ERP_Enterprise_v5/frontend
MOBILE_DIR := apps/mobile-residente/resident-app
AI_DIR := services/ai-agent/conjunto-ai-block2
ERP_DIR := 00_ERP_Enterprise_v5
EDGE_DIR := edge/gateway/conjunto/edge
ESP32_DIR := edge/esp32-firmware/edge/esp32/firmware
AI_PYTHON ?= $(if $(wildcard $(AI_DIR)/.venv/Scripts/python.exe),$(CURDIR)/$(AI_DIR)/.venv/Scripts/python.exe,$(if $(wildcard $(AI_DIR)/.venv/bin/python),$(CURDIR)/$(AI_DIR)/.venv/bin/python,python))
ERP_PYTHON ?= $(if $(wildcard $(ERP_DIR)/.venv/Scripts/python.exe),$(CURDIR)/$(ERP_DIR)/.venv/Scripts/python.exe,$(if $(wildcard $(ERP_DIR)/.venv/bin/python),$(CURDIR)/$(ERP_DIR)/.venv/bin/python,python))

# Colores resueltos por el shell para no depender de ifeq/.if de un make concreto.
C_RED = $$(test -n "$$NO_COLOR" && printf '' || printf '\033[0;31m')
C_GREEN = $$(test -n "$$NO_COLOR" && printf '' || printf '\033[0;32m')
C_YELLOW = $$(test -n "$$NO_COLOR" && printf '' || printf '\033[0;33m')
C_BLUE = $$(test -n "$$NO_COLOR" && printf '' || printf '\033[0;34m')
C_BOLD = $$(test -n "$$NO_COLOR" && printf '' || printf '\033[1m')
C_DIM = $$(test -n "$$NO_COLOR" && printf '' || printf '\033[2m')
C_RESET = $$(test -n "$$NO_COLOR" && printf '' || printf '\033[0m')

# ---------- Helpers ----------
.PHONY: help doctor version env setup install install-dotnet install-ai install-web install-mobile install-hooks \
	up dev prod down restart ps url logs exec rebuild tools compose-validate \
	migrate migration-add psql seed db-dump db-restore \
	build build-dotnet build-ai build-edge build-esp32 build-web build-mobile \
	test test-dotnet test-backend test-ai test-edge test-web test-mobile test-contract test-integration test-maintenance test-watch coverage \
	fmt fmt-dotnet fmt-ai fmt-cpp fmt-web lint lint-dotnet lint-ai lint-cpp lint-web lint-mobile check \
	sec sec-dotnet sec-npm sec-python sec-secrets \
	docs docs-api docs-diagrams tree \
	clean clean-dotnet clean-deps nuke ci full release api grafana mqtt ping

help:
	@printf "\n$(C_BOLD)Conjunto Inteligente · Makefile$(C_RESET)\n\n"
	@NO_COLOR="$(NO_COLOR)" awk 'BEGIN{FS=":.*##"; n=(ENVIRON["NO_COLOR"]!=""); b=n?"":"\\033[1m"; g=n?"":"\\033[0;32m"; r=n?"":"\\033[0m"} /^##@/{printf "\n%s%s%s\n",b,substr($$0,5),r} /^[a-zA-Z0-9_.-]+:.*##/{printf "  %s%-24s%s %s\n",g,$$1,r,$$2}' Makefile
	@printf "\n$(C_DIM)Ejemplos:$(C_RESET)\n"
	@printf "  make test-edge\n  make test-dotnet\n  make test-web\n  COMPOSE_FILE=path/to/compose.yml make up\n  make ci\n\n"

##@ Diagnóstico
doctor: ## Diagnostica host, herramientas y puertos
	@printf "$(C_BOLD)▶ Diagnóstico$(C_RESET)\n"
	@test -f "$(DOTNET_PROJECT)" || { printf "$(C_RED)[FAIL]$(C_RESET) Falta el proyecto .NET del bridge\n"; exit 1; }
	@test -f "$(CORE_API_PROJECT)" || { printf "$(C_RED)[FAIL]$(C_RESET) Falta la API central .NET\n"; exit 1; }
	@test -f "$(ERP_DIR)/backend/app/main.py" || { printf "$(C_RED)[FAIL]$(C_RESET) Falta la API ERP Python\n"; exit 1; }
	@test -f "$(EDGE_DIR)/CMakeLists.txt" || { printf "$(C_RED)[FAIL]$(C_RESET) Falta el gateway C++\n"; exit 1; }
	@printf "$(C_GREEN)[ OK ]$(C_RESET) Rutas de componentes presentes\n"
	@printf "$(C_BLUE)[INFO]$(C_RESET) Puertos comunes:\n"
	@for p in 3000 5000 5100 5173 5432 5672 6379 8000 8080 9000 9090 15672; do \
	  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:$$p -sTCP:LISTEN >/dev/null 2>&1; then \
	    printf "  $(C_YELLOW)[WARN]$(C_RESET) %s en uso\n" "$$p"; \
	  fi; \
	done
	@printf "$(C_GREEN)[ OK ]$(C_RESET) Diagnóstico completo\n"

version: ## Muestra versiones de herramientas
	@printf "dotnet:    $$(dotnet --version 2>/dev/null || echo ausente)\n"
	@printf "python:    $$(python3 --version 2>/dev/null | awk '{print $$2}' || echo ausente)\n"
	@printf "ai python: "; $(AI_PYTHON) --version 2>/dev/null || echo ausente
	@printf "node:      $$(node --version 2>/dev/null || echo ausente)\n"
	@printf "pnpm:      $$(pnpm --version 2>/dev/null || echo ausente)\n"
	@printf "cmake:     $$(cmake --version 2>/dev/null | head -n1 | awk '{print $$3}' || echo ausente)\n"
	@printf "ninja:     $$(ninja --version 2>/dev/null || echo ausente)\n"
	@printf "pio:       $$(pio --version 2>/dev/null | awk '{print $$2}' || echo ausente)\n"
	@printf "terraform: $$(terraform version 2>/dev/null | head -n1 | awk '{print $$2}' || echo ausente)\n"
	@printf "buf:       $$(buf --version 2>/dev/null || echo ausente)\n"
	@printf "docker:    $$(docker --version 2>/dev/null | awk '{print $$3}' | tr -d ',' || echo ausente)\n"
	@printf "compose:   $$(docker compose version --short 2>/dev/null || echo ausente)\n"

env: ## Crea .env desde .env.example si falta y muestra variables no secretas
	@if test ! -f .env; then test -f .env.example || { echo "Falta .env.example"; exit 1; }; cp .env.example .env; fi
	@grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|AI_PORT|WEB_ADMIN_PORT|PB_BRIDGE_PORT|GRAFANA_PORT|POSTGRES_PORT)=' .env | sort || true

##@ Setup y arranque
setup: ## Instala dependencias de componentes presentes
	@$(MAKE) install
	@printf "$(C_GREEN)[ OK ]$(C_RESET) Dependencias instaladas; configura secretos por módulo\n"

install: install-dotnet install-ai install-web ## Instala dependencias de módulos presentes

install-dotnet: ## Restaura .NET
	@command -v dotnet >/dev/null 2>&1 || { echo "Falta dotnet"; exit 1; }
	@dotnet restore $(DOTNET_PROJECT)
	@dotnet restore $(DOTNET_TEST_PROJECT)
	@dotnet restore $(CORE_API_TEST_PROJECT)

install-ai: ## Instala extras de prueba Python en el entorno del proyecto
	@python -m venv $(AI_DIR)/.venv
	@cd $(AI_DIR) && if test -x .venv/Scripts/python.exe; then .venv/Scripts/python.exe -m pip install -e '.[test]'; else .venv/bin/python -m pip install -e '.[test]'; fi

install-web: ## Instala el frontend ERP
	@command -v npm >/dev/null 2>&1 || { echo "Falta npm"; exit 1; }
	@cd $(WEB_DIR) && npm ci

install-mobile: ## Instala mobile
	@test -d "$(MOBILE_DIR)" || { echo "La app móvil no está incluida en este workspace."; exit 1; }
	@command -v pnpm >/dev/null 2>&1 || { echo "Falta pnpm"; exit 1; }
	@cd $(MOBILE_DIR) && pnpm install

install-hooks: ## Instala hook pre-commit
	@test ! -d .git || { test -f .githooks/pre-commit || { echo "Falta .githooks/pre-commit"; exit 1; }; cp .githooks/pre-commit .git/hooks/pre-commit; chmod +x .git/hooks/pre-commit; }

##@ Docker / Stack
up: ## Levanta stack; PROFILE opcional
	@command -v docker >/dev/null 2>&1 || { echo "Falta docker"; exit 1; }
	@test -f "$(COMPOSE_FILE)" || { echo "No existe la compose raíz '$(COMPOSE_FILE)'; no se ha integrado una compose monolítica."; exit 1; }
	@if test -n "$(PROFILE)"; then $(COMPOSE) --profile "$(PROFILE)" up -d; else $(COMPOSE) up -d; fi
	@$(MAKE) url

dev: ## Levanta stack dev
	@test -f "$(COMPOSE_FILE)" || { echo "No existe la compose raíz '$(COMPOSE_FILE)'."; exit 1; }
	@$(COMPOSE) up -d
	@$(MAKE) url

prod: ## Levanta stack prod
	@test -f "$(COMPOSE_FILE)" || { echo "No existe la compose raíz '$(COMPOSE_FILE)'."; exit 1; }
	@$(COMPOSE) up -d
	@$(MAKE) url

down: ## Detiene stack sin borrar volúmenes
	@$(COMPOSE) down

restart: down up ## Reinicia stack

ps: ## Estado de servicios
	@$(COMPOSE) ps

url: ## Imprime endpoints
	@set -a; test ! -f .env || . ./.env; set +a; \
	printf "%-14s http://localhost:%s\n" "ERP API" "$${API_PORT:-8000}"; \
	printf "%-14s http://localhost:%s/docs\n" "API docs" "$${API_PORT:-8000}"; \
	printf "%-14s http://localhost:%s/docs\n" "Core API .NET" "$${CORE_API_PORT:-5000}"; \
	printf "%-14s http://localhost:%s/docs\n" AI "$${AI_PORT:-8000}"; \
	printf "%-14s http://localhost:%s\n" "Web Admin" "$${WEB_ADMIN_PORT:-5173}"; \
	printf "%-14s http://localhost:%s/swagger\n" "PB Bridge" "$${PB_BRIDGE_PORT:-5100}"; \
	printf "%-14s http://localhost:%s/metrics\n" Edge "$${EDGE_HEALTH_PORT:-8080}"; \
	printf "%-14s http://localhost:%s\n" Grafana "$${GRAFANA_PORT:-3000}"; \
	printf "%-14s http://localhost:%s\n" Prometheus "$${PROMETHEUS_PORT:-9090}"; \
	printf "%-14s http://localhost:%s\n" RabbitMQ "$${RABBITMQ_MGMT_PORT:-15672}"; \
	printf "%-14s http://localhost:%s\n" MinIO "$${MINIO_CONSOLE_PORT:-9001}"

logs: ## Logs; SERVICE opcional
	@if test -n "$(SERVICE)"; then $(COMPOSE) logs -f --tail="$(TAIL)" "$(SERVICE)"; else $(COMPOSE) logs -f --tail="$(TAIL)"; fi

exec: ## Shell en SERVICE
	@test -n "$(SERVICE)" || { echo "Uso: SERVICE=api make exec"; exit 1; }
	@$(COMPOSE) exec "$(SERVICE)" sh -c 'command -v bash >/dev/null 2>&1 && exec bash || exec sh'

rebuild: ## Rebuild sin caché de SERVICE
	@test -n "$(SERVICE)" || { echo "Uso: SERVICE=api make rebuild"; exit 1; }
	@$(COMPOSE) build --no-cache "$(SERVICE)"
	@$(COMPOSE) up -d "$(SERVICE)"

tools: ## Levanta Adminer y MailHog
	@$(COMPOSE) --profile tools up -d adminer mailhog

compose-validate: ## Valida una compose raíz proporcionada mediante COMPOSE_FILE
	@test -f "$(COMPOSE_FILE)" || { echo "No existe la compose raíz '$(COMPOSE_FILE)'; valida cada compose de módulo por separado."; exit 1; }
	@$(COMPOSE) config --quiet

##@ Base de datos
migrate: ## Aplica las migraciones Alembic del backend ERP
	@cd $(ERP_DIR) && $(ERP_PYTHON) -m alembic upgrade head

migration-add: ## NAME=initial make migration-add
	@test -n "$(NAME)" || { echo "Uso: NAME=nombre make migration-add"; exit 1; }
	@cd $(ERP_DIR) && $(ERP_PYTHON) -m alembic revision --autogenerate -m "$(NAME)"

psql: ## Abre psql
	@set -a; test ! -f .env || . ./.env; set +a; $(COMPOSE) exec postgres psql -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}"

seed: ## Inserta tenant demo idempotente
	@set -a; test ! -f .env || . ./.env; set +a; \
	$(COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}" \
	  -v tenant_code="$(TENANT_CODE)" -v tenant_name="$(TENANT_NAME)" \
	  -c "INSERT INTO tenants (id, code, name, country, time_zone, currency, active, created_at, created_by, is_deleted) VALUES (gen_random_uuid(), :'tenant_code', :'tenant_name', 'CO', 'America/Bogota', 'COP', true, now(), 'seed', false) ON CONFLICT (code) DO NOTHING;"

db-dump: ## OUT=dump.sql make db-dump
	@set -a; test ! -f .env || . ./.env; set +a; $(COMPOSE) exec -T postgres pg_dump -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}" > "$(OUT)"

db-restore: ## IN=dump.sql make db-restore
	@test -n "$(IN)" && test -f "$(IN)" || { echo "Uso: IN=dump.sql make db-restore"; exit 1; }
	@set -a; test ! -f .env || . ./.env; set +a; $(COMPOSE) exec -T postgres psql -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}" < "$(IN)"

##@ Build
build: build-dotnet build-ai build-edge build-web ## Compila artefactos principales

build-dotnet: ## Build .NET
	@dotnet build $(DOTNET_PROJECT) -c Debug --nologo
	@dotnet build $(CORE_API_PROJECT) -c Debug --nologo

build-ai: ## Compila Python
	@$(AI_PYTHON) -m compileall -q $(AI_DIR)/app

build-edge: ## Build C++ Edge
	@cmake -S $(EDGE_DIR) -B $(EDGE_DIR)/build -G Ninja -DCMAKE_BUILD_TYPE=Release
	@cmake --build $(EDGE_DIR)/build -j

build-esp32: ## Build firmware ESP32
	@pio run -d $(ESP32_DIR)

build-web: ## Build del frontend ERP
	@cd $(WEB_DIR) && npm run build

build-mobile: ## Lint/type validation mobile
	@test -d "$(MOBILE_DIR)" || { echo "La app móvil no está incluida en este workspace."; exit 1; }
	@cd $(MOBILE_DIR) && pnpm lint

##@ Tests
test: test-dotnet test-backend test-ai test-edge test-web ## Ejecuta las suites de componentes presentes

test-dotnet: ## Suite .NET
	@dotnet test $(DOTNET_TEST_PROJECT) -c Debug --nologo
	@dotnet test $(CORE_API_TEST_PROJECT) -c Debug --nologo

test-backend: ## Suite backend ERP sin pruebas de integración PostgreSQL
	@cd $(ERP_DIR)/backend && $(ERP_PYTHON) -m pytest -q tests --ignore=tests/integration

test-ai: ## Suite pytest
	@cd $(AI_DIR) && $(AI_PYTHON) -m pytest -q

test-edge: ## Suite ctest
	@cmake -S $(EDGE_DIR) -B $(EDGE_DIR)/build -G Ninja -DCMAKE_BUILD_TYPE=Debug -DEDGE_BUILD_TESTS=ON
	@cmake --build $(EDGE_DIR)/build -j
	@ctest --test-dir $(EDGE_DIR)/build --output-on-failure

test-web: ## Suite web
	@cd $(WEB_DIR) && npm test

test-mobile: ## Suite mobile (no disponible en este workspace)
	@test -d "$(MOBILE_DIR)" || { echo "La app móvil no está incluida en este workspace."; exit 1; }
	@cd $(MOBILE_DIR) && pnpm test -- --watchAll=false

test-contract: ## Contratos OpenAPI/protobuf
	@if test -d contracts/protobuf; then command -v buf >/dev/null 2>&1 && buf lint contracts/protobuf; else echo "SKIP: no hay contratos protobuf raíz."; fi
	@if test -f contracts/openapi/conjunto-api.yaml; then command -v npx >/dev/null 2>&1 && npx --yes @redocly/cli lint contracts/openapi/conjunto-api.yaml; else echo "SKIP: no hay contrato OpenAPI raíz."; fi

test-integration: ## Tests de integración del ERP (requiere PostgreSQL configurado)
	@cd $(ERP_DIR)/backend && $(ERP_PYTHON) -m pytest -q tests/integration

test-maintenance: ## E2E de mantenimiento en PostgreSQL descartable (requiere confirmación explícita)
	@test -n "$$PHASE13_DATABASE_URL" || { echo "Define PHASE13_DATABASE_URL apuntando a una base PostgreSQL descartable."; exit 2; }
	@test "$$PHASE13_ALLOW_DATABASE_RESET" = "1" || { echo "Define PHASE13_ALLOW_DATABASE_RESET=1 solo para la base descartable."; exit 2; }
	@cd $(ERP_DIR)/backend && $(ERP_PYTHON) -m pytest -q tests/integration/test_maintenance_postgres_e2e.py

test-watch: ## dotnet watch test
	@dotnet watch test --project $(DOTNET_TEST_PROJECT)

coverage: ## Cobertura .NET
	@dotnet test $(DOTNET_TEST_PROJECT) -c Debug --collect:"XPlat Code Coverage" --results-directory ./coverage --nologo
	@dotnet test $(CORE_API_TEST_PROJECT) -c Debug --collect:"XPlat Code Coverage" --results-directory ./coverage --nologo

##@ Calidad
fmt: fmt-dotnet fmt-ai fmt-cpp ## Formatea los componentes con formatter configurado

fmt-dotnet: ## dotnet format
	@dotnet format $(DOTNET_PROJECT) --verbosity quiet
	@dotnet format $(CORE_API_PROJECT) --verbosity quiet
	@dotnet format $(CORE_API_TEST_PROJECT) --verbosity quiet

fmt-ai: ## ruff format + fix
	@cd $(AI_DIR) && $(AI_PYTHON) -m ruff format . && $(AI_PYTHON) -m ruff check --fix .

fmt-cpp: ## clang-format
	@command -v clang-format >/dev/null 2>&1 || { echo "clang-format no instalado"; exit 1; }
	@find $(EDGE_DIR)/gateway $(EDGE_DIR)/tests \( -name '*.cpp' -o -name '*.hpp' \) -print0 | xargs -0 clang-format -i

fmt-web: ## Formato web (no configurado)
	@echo "No hay formatter web configurado en package.json; no se modificaron archivos."
	@exit 2

lint: lint-dotnet lint-ai lint-cpp lint-web ## Lint de los componentes disponibles

lint-dotnet: ## .NET warnings as errors
	@dotnet build $(DOTNET_PROJECT) -c Debug --nologo /warnaserror
	@dotnet build $(CORE_API_PROJECT) -c Debug --nologo /warnaserror

lint-ai: ## ruff + mypy
	@cd $(AI_DIR) && $(AI_PYTHON) -m ruff check . && $(AI_PYTHON) -m mypy app

lint-cpp: ## Compilación C++ de calidad
	@cmake -S $(EDGE_DIR) -B $(EDGE_DIR)/build -G Ninja -DCMAKE_BUILD_TYPE=Debug -DEDGE_BUILD_TESTS=ON
	@cmake --build $(EDGE_DIR)/build -j

lint-web: ## Lint web
	@cd $(WEB_DIR) && npm run lint

lint-mobile: ## Lint mobile
	@test -d "$(MOBILE_DIR)" || { echo "La app móvil no está incluida en este workspace."; exit 1; }
	@cd $(MOBILE_DIR) && pnpm lint

check: lint test ## Gate local antes de commit

##@ Seguridad
sec: sec-dotnet sec-npm sec-python sec-secrets ## Auditoría de seguridad

sec-dotnet: ## Vulnerabilidades .NET
	@dotnet list $(DOTNET_PROJECT) package --vulnerable --include-transitive
	@dotnet list $(CORE_API_PROJECT) package --vulnerable --include-transitive

sec-npm: ## Auditoría npm
	@cd $(WEB_DIR) && npm audit --audit-level=high

sec-python: ## pip-audit
	@cd $(AI_DIR) && $(AI_PYTHON) -m pip_audit

sec-secrets: ## Busca secretos
	@if command -v gitleaks >/dev/null 2>&1; then gitleaks detect --no-banner --source .; else \
	  echo "gitleaks no instalado; instala gitleaks para un gate de secretos completo"; \
	  exit 1; \
	fi

##@ Documentación
docs: docs-api docs-diagrams ## Genera documentación

docs-api: ## Documentación API
	@echo "FastAPI es el origen del contrato OpenAPI; la API central .NET lo expone por /openapi.json y /docs."

docs-diagrams: ## Regenera diagramas
	@if test -x scripts/render-diagrams.sh; then bash scripts/render-diagrams.sh; else echo "SKIP: el generador de diagramas raíz no está incluido."; fi

tree: ## Árbol del repositorio
	@if command -v tree >/dev/null 2>&1; then tree -L 3 -I 'node_modules|bin|obj|.git|.venv|__pycache__|dist|build|.pytest_cache|.ruff_cache'; else find . -maxdepth 3 -type d | sort; fi

##@ Limpieza
clean: ## Limpia artefactos; NO borra volúmenes
	@rm -rf $(EDGE_DIR)/build $(WEB_DIR)/dist $(WEB_DIR)/node_modules/.vite
	@find . -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' -o -name '.mypy_cache' \) -prune -exec rm -rf {} + 2>/dev/null || true

clean-dotnet: ## Limpia bin/obj
	@find . -type d \( -name bin -o -name obj \) -prune -exec rm -rf {} + 2>/dev/null || true

clean-deps: ## Limpia node_modules/.venv
	@rm -rf $(WEB_DIR)/node_modules $(MOBILE_DIR)/node_modules $(AI_DIR)/.venv

nuke: ## Destructivo: exige escribir NUKE
	@printf "Escribe 'NUKE' para confirmar: "; read ans; test "$$ans" = "NUKE" || { echo "Cancelado."; exit 1; }
	@$(COMPOSE) down -v --rmi local --remove-orphans
	@$(MAKE) clean
	@$(MAKE) clean-deps

##@ CI / Composición
ci: lint test build ## Pipeline CI de los componentes presentes

full: setup up migrate seed ## Setup + stack + migraciones + demo

release: ## Placeholder explícito para firma futura
	@echo "Release firmado pendiente de pipeline CI. No se genera un artefacto falsamente firmado."

##@ Atajos
api: ## Abre la documentación OpenAPI del ERP
	@set -a; test ! -f .env || . ./.env; set +a; \
	url="http://localhost:$${API_PORT:-8000}/docs"; \
	if command -v open >/dev/null 2>&1; then open "$$url"; \
	elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$$url"; \
	else echo "$$url"; fi

grafana: ## Abre Grafana
	@set -a; test ! -f .env || . ./.env; set +a; \
	url="http://localhost:$${GRAFANA_PORT:-3000}"; \
	if command -v open >/dev/null 2>&1; then open "$$url"; \
	elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$$url"; \
	else echo "$$url"; fi

mqtt: ## Suscribe al broker MQTT
	@$(COMPOSE) exec mosquitto mosquitto_sub -h localhost -t 'conjunto/+/events' -v

ping: ## Comprueba healthchecks y falla si alguno falla
	@set -a; test ! -f .env || . ./.env; set +a; \
	ok=1; \
	for pair in \
	  "api:http://localhost:$${API_PORT:-8000}/health" \
	  "ai:http://localhost:$${AI_PORT:-8000}/health" \
	  "edge:http://localhost:$${EDGE_HEALTH_PORT:-8080}/health" \
	  "pb-bridge:http://localhost:$${PB_BRIDGE_PORT:-5100}/health" \
	  "prometheus:http://localhost:$${PROMETHEUS_PORT:-9090}/-/healthy" \
	  "loki:http://localhost:$${LOKI_PORT:-3100}/ready" \
	  "tempo:http://localhost:$${TEMPO_PORT:-3200}/ready"; do \
	  name="$${pair%%:*}"; url="$${pair#*:}"; \
	  if curl -fsS "$$url" >/dev/null 2>&1; then echo "OK   $$name"; else echo "FAIL $$name"; ok=0; fi; \
	done; test $$ok -eq 1

##@ Vigilancia (base de datos y verificación)
.PHONY: vig-migrate vig-migrate-status vig-verify vig-test
vig-migrate: ## Aplica migraciones SQL de vigilancia (requiere DB_DSN)
	@python integrations/vigilancia-sistema/infrastructure/postgres/migrate.py
vig-migrate-status: ## Estado de migraciones (solo lectura)
	@python integrations/vigilancia-sistema/infrastructure/postgres/migrate.py --status
vig-verify: ## Verificación estática: sintaxis, JSON, esquema SQL, manifiesto
	@python integrations/vigilancia-sistema/scripts/verify_platform.py
vig-test: ## Pruebas de vigilancia
	@cd integrations/vigilancia-sistema && python -m pytest -q tests && python -m pytest -q services/agent-orchestrator/tests

.PHONY: verify
verify: ## Verificación de rutas y suites de componentes disponibles
	@$(MAKE) doctor
	@$(MAKE) test
