@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Process Spec Gen System - Setup
echo ============================================
echo.

REM --- Root dir (where this .bat lives) ---
pushd "%~dp0"
set "ROOT_DIR=%CD%"
popd

set "VENV_DIR=%ROOT_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"
set "ENV_FILE=%ROOT_DIR%\.env"
set "ENV_EXAMPLE=%ROOT_DIR%\.env.example"
set "REQ_FILE=%ROOT_DIR%\backend\requirements.txt"
set "HAS_ERROR=0"

REM =============================================
REM  1. Check Python
REM =============================================
echo [1/9] Checking Python ...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python ^>=3.11:
    echo         https://www.python.org/downloads/
    echo         IMPORTANT: check "Add Python to PATH" during installation.
    set HAS_ERROR=1
    goto :summary
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo        Python %PY_VER%  OK

REM =============================================
REM  2. Create virtualenv
REM =============================================
echo [2/9] Checking virtualenv ...
if exist "%VENV_PYTHON%" (
    echo        .venv exists, skip creation.
) else (
    echo        Creating .venv ...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtualenv.
        echo         Make sure the project path does not contain Chinese characters.
        set HAS_ERROR=1
        goto :summary
    )
    echo        .venv created.
)

REM =============================================
REM  3. Upgrade pip + install deps
REM =============================================
echo [3/9] Installing Python dependencies (this may take 5-10 min) ...
"%VENV_PIP%" install --upgrade pip -q 2>nul
"%VENV_PIP%" install -r "%REQ_FILE%" -q
if errorlevel 1 (
    echo [WARN] Batch install failed, retrying one by one ...
    for /f "usebackq delims=" %%p in ("%REQ_FILE%") do (
        set "LINE=%%p"
        if "!LINE!" neq "" if "!LINE:~0,1!" neq "#" (
            if "!LINE:~0,1!" neq " " if "!LINE:~0,1!" neq "" (
                for /f "tokens=1 delims=>=~^<^! " %%n in ("!LINE!") do (
                    echo        Installing %%n ...
                    "%VENV_PIP%" install "%%n" -q 2>nul
                    if errorlevel 1 echo        [FAIL] %%n
                )
            )
        )
    )
    echo        Retry done.
) else (
    echo        Dependencies installed.
)

REM =============================================
REM  4. .env config
REM =============================================
echo [4/9] Checking .env config ...
if exist "%ENV_FILE%" (
    echo        .env exists
) else (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo        Created .env from .env.example
        echo        [TODO] Edit .env and fill in your API keys.
    ) else (
        echo [ERROR] .env.example missing. Cannot auto-create .env
        set HAS_ERROR=1
    )
)

REM =============================================
REM  5. Check FreeCAD
REM =============================================
echo [5/9] Checking FreeCAD ...
set "FC_BIN="

REM Try registry
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\FreeCAD\FreeCAD" /ve 2^>nul ^| find "REG_SZ"') do set "FC_DIR=%%b"
if not defined FC_DIR (
    for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\WOW6432Node\FreeCAD\FreeCAD" /ve 2^>nul ^| find "REG_SZ"') do set "FC_DIR=%%b"
)

if defined FC_DIR (
    if exist "!FC_DIR!\bin\FreeCAD.exe" set "FC_BIN=!FC_DIR!\bin\FreeCAD.exe"
)

REM Try common paths
if not defined FC_BIN (
    for %%d in (
        "D:\Program Files\FreeCAD 1.1"
        "C:\Program Files\FreeCAD 1.1"
        "D:\Program Files\FreeCAD 1.0"
        "C:\Program Files\FreeCAD 1.0"
        "D:\FreeCAD"
        "C:\FreeCAD"
    ) do (
        if exist "%%~d\bin\FreeCAD.exe" (
            if not defined FC_BIN set "FC_BIN=%%~d\bin\FreeCAD.exe"
        )
    )
)

if defined FC_BIN (
    echo        FreeCAD found: !FC_BIN!
    findstr /c:"FREECAD_BIN" "%ENV_FILE%" >nul 2>&1
    if errorlevel 1 (
        for %%f in ("!FC_BIN!") do set "FC_DIR=%%~dpf"
        set "FC_DIR=!FC_DIR:~0,-1!"
        for %%f in ("!FC_DIR!") do set "FC_DIR=%%~dpf"
        set "FC_DIR=!FC_DIR:~0,-1!"
        >>"%ENV_FILE%" echo.
        >>"%ENV_FILE%" echo # FreeCAD paths
        >>"%ENV_FILE%" echo FREECAD_BIN=!FC_DIR!\bin
        >>"%ENV_FILE%" echo FREECAD_LIB=!FC_DIR!\lib
        echo        FreeCAD paths added to .env
    )
) else (
    echo [WARN] FreeCAD not found in common locations.
    echo        If installed elsewhere, edit .env and add:
    echo          FREECAD_BIN=your_path\bin
    echo          FREECAD_LIB=your_path\lib
    echo        Download: https://www.freecad.org/downloads.php
)

REM =============================================
REM  6. Check Node.js + npm install
REM =============================================
echo [6/9] Checking Node.js ...
where node >nul 2>&1
if errorlevel 1 (
    echo        Node.js not found - PPT export will not work.
    echo        Download: https://nodejs.org/
) else (
    for /f "delims=" %%v in ('node -v 2^>^&1') do echo        Node %%v OK
)

echo [7/9] Installing Node.js packages ...
if exist "%ROOT_DIR%\package.json" (
    pushd "%ROOT_DIR%"
    call npm install
    if errorlevel 1 (
        echo [WARN] npm install failed. PPT export may not work.
        echo        Make sure Node.js is installed and in PATH.
    ) else (
        echo        npm packages installed.
    )
    popd
) else (
    echo        No package.json found, skip npm install.
)

REM =============================================
REM  8. VC++ Redistributable check
REM =============================================
echo [8/9] Checking VC++ Redistributable ...
set "VCREDIST=0"
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" /v Version 2>nul | find "0" >nul && set "VCREDIST=1"
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" /v Version 2>nul | find "0" >nul && set "VCREDIST=1"
if "!VCREDIST!"=="1" (
    echo        VC++ Redistributable found
) else (
    echo [WARN] VC++ 2015+ Redistributable not found.
    echo        PaddleOCR requires this. Download and install:
    echo        https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo        If skipped, OCR features will fail.
)

REM =============================================
REM  9. Vector DB
REM =============================================
echo [9/9] Checking vector database ...
if exist "%ROOT_DIR%\db_data\vector_map_new.db" (
    echo        vector_map_new.db found.
) else (
    echo [WARN] db_data\vector_map_new.db not found.
    echo        Copy it from the source machine - RAG feature requires it.
)

REM =============================================
:summary
echo.
echo ============================================
if "%HAS_ERROR%"=="0" (
    echo   Setup complete.
    echo.
    echo   Next steps:
    echo     1. Edit .env and fill in your API keys
    echo     2. Run: updated_front\start_flask_demo.bat
    echo.
    echo   If you see ANY [WARN] above,
    echo   review the corresponding section.
) else (
    echo   Setup has unresolved errors.
    echo   Fix the [ERROR] items above and re-run.
)
echo ============================================
echo.
pause
endlocal
