# Lance la plateforme du Defi 2 (API NestJS + interface React) sur http://localhost:3000
# Usage : powershell -ExecutionPolicy Bypass -File plateforme\lancer_plateforme.ps1 [-Port 3000] [-SansNavigateur]
# Prerequis : Node.js 20 ou plus. Les donnees viennent du pipeline Python (04_analyse/*_donnees-plateforme_v1.json).
param([int]$Port = 3000, [switch]$SansNavigateur)
$ErrorActionPreference = "Stop"
$ici = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js est introuvable : installez Node.js 20 ou plus (https://nodejs.org)." }
foreach ($d in @("web", "api")) {
    $dossier = Join-Path $ici $d
    if (-not (Test-Path (Join-Path $dossier "node_modules"))) {
        Write-Host "Installation des dependances ($d)..."
        Push-Location $dossier; npm install --no-audit --no-fund; $code = $LASTEXITCODE; Pop-Location
        if ($code -ne 0) { throw "Echec de npm install dans $d" }
    }
}
if (-not (Test-Path (Join-Path $ici "web\dist\index.html"))) { Push-Location (Join-Path $ici "web"); npm run build; Pop-Location }
if (-not (Test-Path (Join-Path $ici "api\dist\main.js"))) { Push-Location (Join-Path $ici "api"); npm run build; Pop-Location }
$env:PORT = "$Port"
if (-not $SansNavigateur) { Start-Job -ScriptBlock { param($p) Start-Sleep -Seconds 3; Start-Process "http://localhost:$p" } -ArgumentList $Port | Out-Null }
Write-Host "Plateforme : http://localhost:$Port   (Ctrl+C pour arreter)"
node (Join-Path $ici "api\dist\main.js")
