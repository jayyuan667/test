# Smart Process System - Dev Startup
# Shows both backend and frontend logs in one terminal

$ROOT = $PSScriptRoot

Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "    Smart Process System - Dev Startup" -ForegroundColor Cyan
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""

# Kill existing processes on ports
foreach ($port in @(5090, 3000)) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $pids) {
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  [!] Killing process on port ${port}: $($proc.ProcessName) (PID $p)" -ForegroundColor Yellow
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Write-Host "  [1/2] Starting backend :5090 ..." -ForegroundColor Green
$backend = Start-Process -FilePath "python" -ArgumentList "-m", "backend.run" -WorkingDirectory $ROOT -PassThru -NoNewWindow -RedirectStandardOutput "$ROOT\backend_stdout.log" -RedirectStandardError "$ROOT\backend_stderr.log"
Write-Host "         Backend PID: $($backend.Id)" -ForegroundColor DarkGray

# Wait for backend
$w = 0
while ($w -lt 30) {
    $listening = Get-NetTCPConnection -LocalPort 5090 -State Listen -ErrorAction SilentlyContinue
    if ($listening) { break }
    Start-Sleep -Seconds 1
    $w++
}
if ($w -ge 30) {
    Write-Host "         Backend timeout!" -ForegroundColor Red
} else {
    Write-Host "         Backend ready" -ForegroundColor Green
}

Write-Host "  [2/2] Starting frontend :3000 ..." -ForegroundColor Green
$frontend = Start-Process -FilePath "cmd" -ArgumentList "/c", "cd /d `"$ROOT\frontend`" && npx vite --port 3000 --host" -PassThru -NoNewWindow -RedirectStandardOutput "$ROOT\frontend_stdout.log" -RedirectStandardError "$ROOT\frontend_stderr.log"
Write-Host "         Frontend PID: $($frontend.Id)" -ForegroundColor DarkGray

# Wait for frontend
$w = 0
while ($w -lt 30) {
    $listening = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
    if ($listening) { break }
    Start-Sleep -Seconds 1
    $w++
}
if ($w -ge 30) {
    Write-Host "         Frontend timeout!" -ForegroundColor Red
} else {
    Write-Host "         Frontend ready" -ForegroundColor Green
}

Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "    Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "    Backend:  http://localhost:5090/api/health" -ForegroundColor White
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Streaming logs (Ctrl+C to stop all) ..." -ForegroundColor DarkGray
Write-Host "  --------------------------------------------" -ForegroundColor DarkGray

Start-Process "http://localhost:3000" -ErrorAction SilentlyContinue

# Stream logs from both services
$backendLog = "$ROOT\backend_stdout.log"
$backendErr = "$ROOT\backend_stderr.log"
$frontendLog = "$ROOT\frontend_stdout.log"
$frontendErr = "$ROOT\frontend_stderr.log"

# Create log files if they don't exist
foreach ($f in @($backendLog, $backendErr, $frontendLog, $frontendErr)) {
    if (-not (Test-Path $f)) { New-Item -Path $f -ItemType File -Force | Out-Null }
}

try {
    $bePos = 0
    $fePos = 0
    while (-not $backend.HasExited -or -not $frontend.HasExited) {
        # Read backend logs
        if (Test-Path $backendLog) {
            $content = Get-Content $backendLog -ErrorAction SilentlyContinue
            if ($content -and $content.Count -gt $bePos) {
                $newLines = $content[$bePos..($content.Count - 1)]
                foreach ($line in $newLines) {
                    Write-Host "  [BACKEND]  " -ForegroundColor Yellow -NoNewline
                    Write-Host $line
                }
                $bePos = $content.Count
            }
        }
        if (Test-Path $backendErr) {
            $errContent = Get-Content $backendErr -ErrorAction SilentlyContinue
            if ($errContent -and $errContent.Count -gt 0) {
                $newErr = $errContent | Select-Object -Last 5
                foreach ($line in $newErr) {
                    if ($line.Trim()) {
                        Write-Host "  [BACKEND]  " -ForegroundColor Red -NoNewline
                        Write-Host $line -ForegroundColor Red
                    }
                }
                Clear-Content $backendErr -ErrorAction SilentlyContinue
            }
        }

        # Read frontend logs
        if (Test-Path $frontendLog) {
            $content = Get-Content $frontendLog -ErrorAction SilentlyContinue
            if ($content -and $content.Count -gt $fePos) {
                $newLines = $content[$fePos..($content.Count - 1)]
                foreach ($line in $newLines) {
                    Write-Host "  [FRONTEND] " -ForegroundColor Cyan -NoNewline
                    Write-Host $line
                }
                $fePos = $content.Count
            }
        }
        if (Test-Path $frontendErr) {
            $errContent = Get-Content $frontendErr -ErrorAction SilentlyContinue
            if ($errContent -and $errContent.Count -gt 0) {
                $newErr = $errContent | Select-Object -Last 5
                foreach ($line in $newErr) {
                    if ($line.Trim()) {
                        Write-Host "  [FRONTEND] " -ForegroundColor Magenta -NoNewline
                        Write-Host $line
                    }
                }
                Clear-Content $frontendErr -ErrorAction SilentlyContinue
            }
        }

        Start-Sleep -Milliseconds 500
    }
} finally {
    Write-Host ""
    Write-Host "  Stopping services ..." -ForegroundColor Yellow
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue

    # Cleanup log files
    foreach ($f in @($backendLog, $backendErr, $frontendLog, $frontendErr)) {
        Remove-Item $f -Force -ErrorAction SilentlyContinue
    }

    Write-Host "  Done" -ForegroundColor Green
}
