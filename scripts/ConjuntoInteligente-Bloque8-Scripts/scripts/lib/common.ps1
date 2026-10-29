$ErrorActionPreference = 'Stop'
function Write-Info { param($m) Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Ok { param($m) Write-Host "[ OK ] $m" -ForegroundColor Green }
function Write-Warn { param($m) Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err { param($m) Write-Host "[ERR ] $m" -ForegroundColor Red }
function Write-Step { param($m) Write-Host "`n▶ $m" -ForegroundColor White }
function Test-Command { param([string]$Name) return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }
function Get-Version([string]$Text) { $m=[regex]::Match([string]$Text,'\d+(?:\.\d+){1,3}'); if($m.Success){return $m.Value}; return '' }
function Test-VersionGE { param([string]$Current,[string]$Required); try { return ([version](Get-Version $Current)) -ge ([version](Get-Version $Required)) } catch { return $false } }
function Ensure-PathLine { param([string]$Line,[string]$ProfileFile); $dir=Split-Path -Parent $ProfileFile; if($dir -and -not(Test-Path $dir)){New-Item -ItemType Directory -Path $dir -Force|Out-Null}; if(-not(Test-Path $ProfileFile)){New-Item -ItemType File -Path $ProfileFile -Force|Out-Null}; if(-not((Get-Content $ProfileFile -ErrorAction SilentlyContinue) -contains $Line)){Add-Content $ProfileFile "`n# Añadido por bootstrap Conjunto Inteligente"; Add-Content $ProfileFile $Line} }
function Get-UserProfile { return $PROFILE.CurrentUserAllHosts }
function Acquire-Lock { $lock=Join-Path $env:TEMP 'conjunto-bootstrap.lock'; if(Test-Path $lock){$old=Get-Content $lock -ErrorAction SilentlyContinue; if($old -and (Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue)){Write-Err "Ya hay un bootstrap corriendo (pid=$old)."; return $false}}; $PID|Out-File $lock -Encoding ascii; $Global:ConjuntoLockFile=$lock; return $true }
function Release-Lock { if($Global:ConjuntoLockFile -and (Test-Path $Global:ConjuntoLockFile)){Remove-Item $Global:ConjuntoLockFile -Force -ErrorAction SilentlyContinue} }
