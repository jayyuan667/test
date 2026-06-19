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

echo [1/7] Checking Python...
py -3.11 --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3.11"

if not defined PYTHON_CMD (
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3.12"
)

if not defined PYTHON_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 (
        for /f %%v in ('python -c "import sys; print(str(sys.version_info.major) + '.' + str(sys.version_info.minor))"') do set "SYSTEM_PYTHON_VERSION=%%v"
        if "!SYSTEM_PYTHON_VERSION!"=="3.11" set "PYTHON_CMD=python"
        if "!SYSTEM_PYTHON_VERSION!"=="3.12" set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python 3.11 or 3.12 is required.
    echo         Python 3.13 is not supported by rapidocr-onnxruntime.
    echo         https://www.python.org/downloads/
    exit /b 1
)
%PYTHON_CMD% --version

echo.
echo [2/7] Checking Node.js and npm...
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
echo [3/7] Creating Python virtual environment...
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" --version 2>&1 | findstr /R /C:"Python 3\.11" /C:"Python 3\.12" >nul
    if errorlevel 1 (
        echo         Existing .venv uses an unsupported Python version; rebuilding it.
        rmdir /s /q "%VENV_DIR%"
    ) else (
        echo         Existing .venv is compatible.
    )
)
if not exist "%VENV_PYTHON%" (
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv.
        exit /b 1
    )
)

echo.
echo [4/7] Installing backend dependencies...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%VENV_PYTHON%" -m pip install -r "%ROOT_DIR%backend\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Backend dependency installation failed.
    exit /b 1
)

echo.
echo [5/7] Installing React dependencies...
if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] frontend-react\package.json was not found.
    exit /b 1
)
pushd "%FRONTEND_DIR%"
call npm install
set "NPM_EXIT=%ERRORLEVEL%"
popd
if not "%NPM_EXIT%"=="0" (
    echo [ERROR] Frontend dependency installation failed.
    exit /b %NPM_EXIT%
)

echo.
echo [6/7] Preparing local configuration...
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
echo [7/7] Creating runtime directories...
if not exist "%ROOT_DIR%db_data" mkdir "%ROOT_DIR%db_data"
if not exist "%ROOT_DIR%uploads" mkdir "%ROOT_DIR%uploads"
if not exist "%ROOT_DIR%output" mkdir "%ROOT_DIR%output"

echo.
echo ============================================
echo   Setup completed.
echo ============================================
echo.
echo 1. Edit "%ENV_FILE%" and replace API placeholders.
echo 2. Start the project:
echo.
echo      start.bat
echo.
echo Frontend: http://127.0.0.1:3200
echo Backend:  http://127.0.0.1:5190
echo Health:   http://127.0.0.1:5190/api/health
echo.
pause
endlocal
