@echo off
setlocal enabledelayedexpansion

for %%I in ("%~dp0..") do set "ROOT_DIR=%%~fI"
set "PORT=5090"
set "URL=http://127.0.0.1:%PORT%/dev/demo-industrial-console"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

echo ============================================
echo   Smart Process System - Dev Start
echo ============================================
echo.

:: Detect Python: .venv > py launcher > python
set "PYTHON_EXE="
if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
    echo [OK] Using .venv
) else (
    py --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=py"
        echo [OK] Using py launcher
    ) else (
        python --version >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_EXE=python"
            echo [OK] Using system Python
        ) else (
            echo [ERROR] Python not found. Install Python 3.11+
            pause
            exit /b 1
        )
    )
)

:: Kill any process already on port 5090
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5090 "') do (
    echo [INFO] Releasing port %PORT% (PID: %%a)
    taskkill /f /pid %%a >nul 2>&1
)

:: Start backend in a new window
echo [START] Launching Flask backend...
start "ProcessSystem-Backend" /D "%ROOT_DIR%" "!PYTHON_EXE!" -m backend.run

:: Wait up to 30 s for backend to respond
echo [WAIT] Waiting for backend...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ try{ Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:%PORT%/api/health' -TimeoutSec 1 | Out-Null; $ok=$true; break }catch{ Start-Sleep 1 } }; if(-not $ok){ Write-Host '[ERROR] Backend timeout - check backend window'; exit 1 }"
if errorlevel 1 (
    pause
    exit /b 1
)

echo [OK] Backend ready
echo [OPEN] %URL%
start "" "%URL%"

exit /b 0
