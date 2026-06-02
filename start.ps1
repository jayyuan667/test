# PDF Workflow Startup Script
# UTF-8 with BOM

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  PDF Process Analysis System - Startup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
$pythonCmd = "E:\programdata\miniconda3\python.exe"
if (!(Test-Path $pythonCmd)) {
    $pythonCmd = "python"
}

Write-Host "[1/2] Checking Python..." -ForegroundColor Yellow
& $pythonCmd --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Python not found" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "OK: Python found" -ForegroundColor Green

# Check dependencies
Write-Host "[2/2] Checking dependencies..." -ForegroundColor Yellow
$deps = @("flask", "flask_cors", "dotenv", "pdf2image", "PIL", "langchain_openai")
$missing = @()
foreach ($dep in $deps) {
    $result = & $pythonCmd -m pip show $dep 2>$null
    if ($LASTEXITCODE -ne 0) {
        $missing += $dep
    }
}

if ($missing.Count -gt 0) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    & $pythonCmd -m pip install flask flask-cors python-dotenv pdf2image Pillow langchain-openai -q
    Write-Host "Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "OK: Dependencies ready" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Backend: http://localhost:5000" -ForegroundColor Cyan
Write-Host "  Frontend: Opening in browser..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Start backend
$backendDir = Join-Path $PSScriptRoot "backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendDir'; & '$pythonCmd' -W ignore app.py"

# Open frontend in browser
Start-Sleep -Seconds 2
Start-Process (Join-Path $PSScriptRoot "frontend\index.html")