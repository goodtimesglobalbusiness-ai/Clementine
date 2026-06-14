# cs.ps1 ~ show Clem's folder structure (read-only, touches nothing)
$botPath = "C:\Users\zonef\Desktop\Clementine"

if (-not (Test-Path $botPath)) {
    Write-Host "Folder not found: $botPath" -ForegroundColor Red
    return
}

Write-Host "`n=== Clementine folder structure ===" -ForegroundColor Cyan
Write-Host "Path: $botPath`n"

# Walk the tree, skip the noise (node_modules, .git, __pycache__, venv)
$skip = 'node_modules|\.git|__pycache__|venv|\.venv'

Get-ChildItem -Path $botPath -Recurse |
    Where-Object { $_.FullName -notmatch $skip } |
    ForEach-Object {
        $depth  = ($_.FullName.Substring($botPath.Length).TrimStart('\') -split '\\').Count - 1
        $indent = '  ' * $depth
        if ($_.PSIsContainer) {
            Write-Host "$indent[+] $($_.Name)" -ForegroundColor Yellow
        } else {
            $kb = [math]::Round($_.Length / 1KB, 1)
            Write-Host "$indent    $($_.Name)  (${kb} KB)"
        }
    }

# Quick sanity check on the files that matter for Clem
Write-Host "`n=== Key files ===" -ForegroundColor Cyan
$key = @('bot.py', 'requirements.txt', '.env')
foreach ($f in $key) {
    $p = Join-Path $botPath $f
    if (Test-Path $p) {
        Write-Host "  [OK]      $f" -ForegroundColor Green
    } else {
        Write-Host "  [missing] $f" -ForegroundColor DarkGray
    }
}
Write-Host ""
