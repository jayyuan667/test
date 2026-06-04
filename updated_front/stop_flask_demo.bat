@echo off
echo [STOP] Killing Flask backend on port 5090...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5090 "') do (
    echo [KILL] PID %%a
    taskkill /f /pid %%a >nul 2>&1
)
powershell -NoProfile -Command "Get-Process python,py -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'ProcessSystem-Backend' -or $_.CommandLine -like '*backend.run*' } | Stop-Process -Force -ErrorAction SilentlyContinue"
echo [OK] Done
