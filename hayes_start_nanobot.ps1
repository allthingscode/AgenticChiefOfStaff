# --- Configuration ---
$AppPath = "C:\Users\HayesChiefOfStaff\Documents\nanobot"
$PythonExe = "$AppPath\nanoclaw\Scripts\python.exe"
$MCPDataPath = "$env:LOCALAPPDATA\google-ai-mode-mcp\Data\chrome_profile"

Set-Location $AppPath

function Stop-NanobotProcesses {
    param($ProcessId)
    Write-Host "--- Performing Cleanup ---" -ForegroundColor Yellow
    
    # 1. Kill the specific Python process we started (and its children)
    if ($ProcessId) {
        Write-Host "Stopping Nanobot Gateway (PID: $ProcessId)..." -ForegroundColor Gray
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }

    # 2. Cleanup common "zombie" targets that Nanobot uses
    $targets = @("node", "chromium", "playwright")
    foreach ($name in $targets) {
        $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
        if ($procs) {
            Write-Host "Cleaning up $name processes..." -ForegroundColor Gray
            $procs | Stop-Process -Force -ErrorAction SilentlyContinue
        }
    }

    # 3. Clear browser lock
    $lockFile = Join-Path $MCPDataPath "SingletonLock"
    if (Test-Path $lockFile) {
        Write-Host "Clearing stale browser lock..." -ForegroundColor Gray
        Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "--- Initializing Nanobot Environment ---" -ForegroundColor Cyan
Write-Host "Press CTRL+C at any time to stop the gateway and exit." -ForegroundColor White

try {
    while($true) {
        # Always clean up before a fresh start
        Stop-NanobotProcesses

        Write-Host "--- Starting Nanobot Gateway (Port 18790) ---" -ForegroundColor Cyan
        
        # Start the process and keep a reference to it
        $process = Start-Process -FilePath $PythonExe -ArgumentList "`"$AppPath\hayes_gateway_launcher.py`"" -Wait -NoNewWindow -PassThru

        # Check the exit code
        if ($process.ExitCode -eq 0) {
            Write-Host "`nNanobot shut down gracefully." -ForegroundColor Green
            break
        }

        Write-Host "`nGateway exited unexpectedly with code $($process.ExitCode)." -ForegroundColor Red
        Write-Host "Restarting in 5 seconds (Press CTRL+C now to stop)..." -ForegroundColor White
        
        Start-Sleep -Seconds 5
    }
}
finally {
    # This block runs even if you press CTRL+C
    Write-Host "`n`n--- Shutdown Signal Received ---" -ForegroundColor Magenta
    if ($process -and -not $process.HasExited) {
        Stop-NanobotProcesses -ProcessId $process.Id
    } else {
        Stop-NanobotProcesses
    }
    Write-Host "Nanobot has been stopped. Safe to close this window." -ForegroundColor Green
}
