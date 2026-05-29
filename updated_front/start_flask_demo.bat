@echo off
setlocal

pushd "%~dp0.."
set "ROOT_DIR=%CD%"
popd

set "URL=http://127.0.0.1:5000/dev/demo-industrial-console"
set "VENV_PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtualenv not found. Run setup.bat first.
    pause
    exit /b 1
)

set "PYTHONIOENCODING=utf-8"

start "Flask Backend" /D "%ROOT_DIR%" cmd /c "set PYTHONIOENCODING=utf-8 && ""%VENV_PYTHON%"" -m backend.run"

powershell -NoProfile -Command "$ok=$false; for($i=0; $i -lt 30; $i++){ try { Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5000/api/health' -TimeoutSec 1 | Out-Null; $ok=$true; break } catch { Start-Sleep -Seconds 1 } }; if(-not $ok){ exit 1 }"

start "" "%URL%"

exit /b 0
