# Bloque 8 — Scripts Bootstrap Host

Automatización real para preparar un host de desarrollo de **Conjunto Inteligente** sin Dev Container.

## Estructura

```text
scripts/
├── bootstrap-host.sh
├── bootstrap-host.ps1
├── verify.sh
├── verify.ps1
├── lib/
│   ├── common.sh
│   └── common.ps1
└── install/
    ├── dotnet.sh
    ├── python.sh
    ├── node.sh
    ├── cpp-deps.sh
    ├── platformio.sh
    ├── terraform.sh
    ├── buf.sh
    ├── dotnet.ps1
    ├── python.ps1
    ├── node.ps1
    ├── cpp-deps.ps1
    ├── platformio.ps1
    ├── terraform.ps1
    └── buf.ps1
```

## Linux/macOS

```bash
chmod +x scripts/bootstrap-host.sh scripts/verify.sh scripts/install/*.sh
./scripts/bootstrap-host.sh --check
./scripts/bootstrap-host.sh --all
./scripts/bootstrap-host.sh --dotnet --node
NO_COLOR=1 ./scripts/verify.sh
```

Sin argumentos, `bootstrap-host.sh` equivale a `--all`. `--check` no instala nada. `--no-sudo` deshabilita sudo y hace fallar claramente cualquier operación que necesite privilegios.

## Windows 11 / PowerShell 7+

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\scripts\bootstrap-host.ps1 -Check
.\scripts\bootstrap-host.ps1 -All
.\scripts\bootstrap-host.ps1 -Python -Pio
.\scripts\verify.ps1
```

## Herramientas

- .NET SDK 8 + `dotnet-ef` + `dotnet-format`
- Python 3.12 + Poetry
- Node 20 + pnpm 9 mediante Corepack
- CMake, Ninja y toolchain C++
- Paho MQTT / SQLite de desarrollo cuando el sistema los soporta
- PlatformIO + plataforma Espressif32
- Terraform >= 1.7
- buf CLI >= 1.30
- Docker: **solo verificación**, nunca instalación

Xcode, Visual Studio, Android SDK y Kubernetes/kubectl no son instalados por este bloque.

## Idempotencia y concurrencia

Los instaladores detectan herramientas existentes y salen sin reinstalar cuando cumplen el mínimo. El bootstrap usa `/tmp/conjunto-bootstrap.lock` en Unix y `%TEMP%\conjunto-bootstrap.lock` en Windows para evitar dos ejecuciones simultáneas.

## CI

En Unix:

```bash
CI=1 ./scripts/bootstrap-host.sh --check
```

Para instalación en un entorno CI donde el proceso ya tiene privilegios:

```bash
CI=1 ./scripts/bootstrap-host.sh --all --no-sudo
```

## Códigos de salida

- `0`: operación/verificación correcta.
- `1`: verificación fallida o herramienta no disponible.
- `2`: argumento inválido.
- `3`: sistema operativo no soportado.
- `4`: uno o más instaladores fallaron.

## Nota de diseño

Docker se verifica pero no se instala. El bloque tampoco modifica otros bloques del proyecto ni cambia gestores de paquetes del sistema fuera de las acciones explícitas del instalador seleccionado.
