@echo off

echo ============================================
echo   Git Pull + Submodule Update
echo ============================================
echo   Pull: git pull
git pull
if errorlevel 1 (
    echo   Pull failed. Check your connection or merge conflicts.
    pause
    exit /b 1
)
echo   Submodule: git submodule update --remote
git submodule update --remote
echo ============================================
echo   Done.
echo ============================================
pause
