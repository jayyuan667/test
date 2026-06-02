@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

cd /d "%~dp0"

:menu
cls
echo ================================================
echo    PDF Process System - Mode Switch
echo ================================================
echo.

findstr /C:"api.deepseek.com" backend\config.json >nul 2>&1
if !errorlevel! equ 0 (
    echo   Current Mode: [Cloud API]
) else (
    echo   Current Mode: [Local vLLM]
)

echo.
echo Select mode:
echo.
echo   [1] Cloud API Mode
echo       - Vision: Doubao Cloud API
echo       - LLM: DeepSeek
echo.
echo   [2] Local Mode
echo       - Vision: Doubao Cloud API
echo       - LLM: Server vLLM (192.168.2.24)
echo.
echo   [3] Exit
echo.
echo ================================================
choice /c 123 /n

if errorlevel 3 goto :end
if errorlevel 2 goto :local_mode
if errorlevel 1 goto :cloud_mode

:cloud_mode
cls
echo.
echo Switching to [Cloud API Mode]...
echo.
copy /Y backend\config_cloud.json backend\config.json >nul 2>&1
if exist backend\config_cloud.json (
    echo   [OK] Config switched
    echo.
    echo   Current config:
    echo   ----------------------------------------
    type backend\config.json
    echo   ----------------------------------------
) else (
    echo   [ERROR] config_cloud.json not found!
)
echo.
pause
goto :menu

:local_mode
cls
echo.
echo Switching to [Local Mode]...
echo.
copy /Y backend\config_local.json backend\config.json >nul 2>&1
if exist backend\config_local.json (
    echo   [OK] Config switched
    echo.
    echo   Current config:
    echo   ----------------------------------------
    type backend\config.json
    echo   ----------------------------------------
) else (
    echo   [ERROR] config_local.json not found!
)
echo.
pause
goto :menu

:end
cls
echo.
echo Bye!
echo.
exit /b
