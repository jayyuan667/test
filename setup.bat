@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ============================================
echo   智能工艺系统 - 开发环境初始化
echo ============================================
echo.

set "ROOT_DIR=%~dp0"
set "VENV_DIR=%ROOT_DIR%.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"
set "ENV_FILE=%ROOT_DIR%.env"
set "ENV_EXAMPLE=%ROOT_DIR%.env.example"
set "REQ_FILE=%ROOT_DIR%backend\requirements.txt"
set "HAS_ERROR=0"

:: 1. 检查 Python
echo [1/5] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    echo        https://www.python.org/downloads/
    set HAS_ERROR=1
    goto :summary
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo        Python %PY_VER% OK

:: 2. 创建虚拟环境
echo [2/5] 检查虚拟环境...
if exist "%VENV_PYTHON%" (
    echo        .venv 已存在，跳过创建
) else (
    echo        正在创建 .venv ...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败
        set HAS_ERROR=1
        goto :summary
    )
    echo        .venv 创建成功
)

:: 3. 安装依赖
echo [3/5] 安装 Python 依赖...
"%VENV_PIP%" install -r "%REQ_FILE%" -q
if errorlevel 1 (
    echo [错误] 依赖安装失败
    echo        请手动运行: .venv\Scripts\pip install -r backend\requirements.txt
    set HAS_ERROR=1
) else (
    echo        依赖安装完成
)

:: 4. 检查 .env 配置
echo [4/5] 检查 .env 配置...
if exist "%ENV_FILE%" (
    echo        .env 已存在
) else (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo        已复制 .env.example -^> .env，请确认 API Key 正确
    ) else (
        echo [警告] 未找到 .env.example，请手动创建 .env
    )
)

:: 5. 检查知识库
echo [5/5] 检查知识库...
if not exist "%ROOT_DIR%db_data\2d-v.db" (
    echo [警告] 未找到 db_data\2d-v.db，知识库检索不可用
    echo        该文件需从已有环境复制或通过 ZIP 导入构建
) else (
    echo        2d-v.db 已就绪
)

:summary
echo.
echo ============================================
if "%HAS_ERROR%"=="0" (
    echo  初始化完成！
    echo.
    echo  启动命令:
    echo    .venv\Scripts\python -m backend.run
    echo.
    echo  浏览器访问:
    echo    http://localhost:5190/dev/demo-industrial-console
) else (
    echo  存在错误，请按提示处理后重试
)
echo ============================================
pause
endlocal
