@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

set "ROOT_DIR=%~dp0"
set "VENV_DIR=%ROOT_DIR%.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "FRONTEND_DIR=%ROOT_DIR%frontend-react"
set "ENV_FILE=%ROOT_DIR%.env"
set "ENV_EXAMPLE=%ROOT_DIR%.env.example"
set "PYTHON_CMD="

echo ============================================
echo   yolo-react development setup
echo ============================================
echo.

echo [1/5] Checking uv...
where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv is required: https://docs.astral.sh/uv/
    exit /b 1
)

echo [2/5] Installing Python and dependencies...
uv python install 3.11.15
if "%INSTALL_YOLO%"=="1" (
    if "%INSTALL_CREO%"=="1" (
        uv sync --locked --extra yolo --extra windows-creo
    ) else (
        uv sync --locked --extra yolo
    )
) else (
    if "%INSTALL_CREO%"=="1" (
        uv sync --locked --extra windows-creo
    ) else (
        uv sync --locked
    )
)
if errorlevel 1 exit /b 1

echo.
echo [3/5] Checking Node.js and npm...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js 20 or newer is required.
    echo         https://nodejs.org/
    exit /b 1
)
call npm --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found. Reinstall Node.js.
    exit /b 1
)
node --version
call npm --version

echo.
echo [4/5] Installing React dependencies...
if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] frontend-react\package.json was not found.
    exit /b 1
)
pushd "%FRONTEND_DIR%"
call npm ci
set "NPM_EXIT=%ERRORLEVEL%"
popd
if not "%NPM_EXIT%"=="0" (
    echo [ERROR] Frontend dependency installation failed.
    exit /b %NPM_EXIT%
)

echo.
echo [5/5] Preparing local configuration...
if exist "%ENV_FILE%" (
    echo         .env already exists; it was not overwritten.
) else (
    if not exist "%ENV_EXAMPLE%" (
        echo [ERROR] .env.example was not found.
        exit /b 1
    )
    copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
    echo         Created .env from .env.example.
)

echo.
echo [5/5] Creating runtime directories...
if not exist "%ROOT_DIR%db_data" mkdir "%ROOT_DIR%db_data"
if not exist "%ROOT_DIR%uploads" mkdir "%ROOT_DIR%uploads"
if not exist "%ROOT_DIR%output" mkdir "%ROOT_DIR%output"

echo.
echo Running runtime smoke check...
uv run python scripts/runtime_smoke.py
if errorlevel 1 (
    echo [WARNING] Smoke check issues detected. Review above output.
)

echo.
echo ============================================
echo   Setup completed.
echo ============================================
echo.
echo 1. Edit "%ENV_FILE%" and replace API placeholders.
echo 2. Start the project:
echo.
echo      start.ps1
echo.
echo Frontend: http://127.0.0.1:3200
echo Backend:  http://127.0.0.1:5190
echo Health:   http://127.0.0.1:5190/api/health
echo.
pause
endlocal
