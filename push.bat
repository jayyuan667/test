@echo off

echo ============================================
echo   Git Push
echo ============================================
echo   Stage: git add .
git add .
echo   Commit: git commit
git commit -m "update"
if errorlevel 1 (
    echo   Nothing to commit or commit failed.
    pause
    exit /b 1
)
echo   Push: git push
git push
echo ============================================
echo   Done.
echo ============================================
pause
