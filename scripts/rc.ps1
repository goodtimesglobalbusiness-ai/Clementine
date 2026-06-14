# rc.ps1 ~ restart ONLY the Python Clementine bot
$botPath  = "C:\Users\zonef\Desktop\Clementine"
$pyEntry  = "bot.py"
$pidFile  = Join-Path $botPath ".clem-pids"

Set-Location $botPath

# --- Stop the previous Python process if it exists ---
if (Test-Path $pidFile) {
    Get-Content $pidFile | ForEach-Object {
        $procId = $_.Trim()
        if ($procId) {
            $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($p) {
                Write-Host "Stopping Clem PID $procId ($($p.ProcessName))..." -ForegroundColor Yellow
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
} else {
    Write-Host "No PID file yet ~ first run, starting fresh." -ForegroundColor Cyan
}

# --- Start ONLY the Python bot ---
Write-Host "Starting Clem (python $pyEntry)..." -ForegroundColor Green
$py = Start-Process python -ArgumentList $pyEntry -WorkingDirectory $botPath -PassThru

# --- Save the PID ---
@($py.Id) | Set-Content $pidFile

Write-Host "Clem is back up. python PID $($py.Id)." -ForegroundColor Green
