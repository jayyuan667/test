@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0.."
set "URL=http://127.0.0.1:5090/dev/demo-industrial-console"
set "PYTHONIOENCODING=utf-8"

echo ============================================
echo   智能工艺系统 - 开发启动
echo ============================================
echo.

:: Auto-detect Python (virtual env > system python)
set "PYTHON_EXE="
if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
    echo [OK] 使用虚拟环境: .venv
) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
        echo [OK] 使用系统 Python
    ) else (
        echo [错误] 未找到 Python，请先运行 setup.bat 或安装 Python 3.11+
        pause
        exit /b 1
    )
)

:: Kill any existing process on port 5090
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5090.*LISTENING" 2^>nul') do (
    echo [提示] 端口 5090 被占用 (PID: %%a)，正在释放...
    taskkill /f /pid %%a >nul 2>&1
)

:: Start backend
echo [启动] 启动 Flask 后端...
start "智能工艺系统-后端" /D "%ROOT_DIR%" cmd /c "set PYTHONIOENCODING=utf-8 && "!PYTHON_EXE!" -m backend.run"

:: Wait for backend to be ready
echo [等待] 等待后端就绪...
powershell -NoProfile -Command "$ok=$false; for($i=0; $i -lt 30; $i++){ try { Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5090/api/health' -TimeoutSec 1 | Out-Null; $ok=$true; break } catch { Start-Sleep -Seconds 1 } }; if(-not $ok){ Write-Host '后端启动超时，请检查日志' ; exit 1 }"
if errorlevel 1 (
    echo [错误] 后端启动失败，请查看 backend.log
    pause
    exit /b 1
)

echo [OK] 后端就绪
echo [打开] 浏览器: %URL%
start "" "%URL%"

exit /b 0
