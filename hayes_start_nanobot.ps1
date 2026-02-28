# --- Configuration Loader ---
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ConfigPath = Join-Path $env:USERPROFILE ".nanobot\config.json"
$Config = if (Test-Path $ConfigPath) { Get-Content $ConfigPath | ConvertFrom-Json } else { @{} }
$Strategic = if ($Config.hayes_strategic) { $Config.hayes_strategic } else { @{} }

# Detect paths with defaults
$AppPath = if ($Strategic.app_root) { $Strategic.app_root } else { (Get-Item .).FullName }
$VenvName = "nanoClaw"
$PythonExe = Join-Path $AppPath "$VenvName\Scripts\python.exe"
$StorageRoot = if ($Strategic.storage_root) { $Strategic.storage_root } else { "D:\Nanobot_Storage" }
$LogDir = Join-Path $StorageRoot "logs"
$MCPDataPath = "$env:LOCALAPPDATA\google-ai-mode-mcp\Data\chrome_profile"

# --- Initialization ---
if (-not (Test-Path $PythonExe)) {
    Write-Host "Error: Virtual environment not found at $PythonExe" -ForegroundColor Red
    Write-Host "Please ensure you have created a venv named '$VenvName' in '$AppPath'." -ForegroundColor Yellow
    exit 1
}

# Ensure Log Directory exists
if (-not (Test-Path $LogDir)) {
    try {
        New-Item -ItemType Directory -Path $LogDir -Force -ErrorAction Stop | Out-Null
        Write-Host "Created log directory: $LogDir" -ForegroundColor Gray
    } catch {
        Write-Host "Warning: Could not create log directory $LogDir. Logging to local 'logs' folder instead." -ForegroundColor Yellow
        $LogDir = Join-Path $AppPath "logs"
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }
}

$LogFile = Join-Path $LogDir "nanobot_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

Set-Location $AppPath

function Stop-NanobotProcesses {
    param($ProcessId)
    Write-Host "--- Performing Cleanup ---" -ForegroundColor Yellow
    
    # 1. Kill the specific Python process we started (and its children)
    if ($ProcessId) {
        Write-Host "Stopping Nanobot Gateway (PID: $ProcessId) and its children..." -ForegroundColor Gray
        
        # Get children before killing the parent
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId"
        
        # Kill parent
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        
        # Kill children (MCP servers, playwright, etc.)
        foreach ($child in $children) {
            Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
        }
    } else {
        # Search for any process running our launcher if no PID was provided
        $launcherProcs = Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%hayes_gateway_launcher.py%'"
        foreach ($p in $launcherProcs) {
             Write-Host "Stopping Nanobot Gateway (PID: $($p.ProcessId)) and its children..." -ForegroundColor Gray
             $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($p.ProcessId)"
             foreach ($child in $children) {
                 Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
             }
             Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    # 2. Cleanup leftover specific zombie targets if they are in this workspace
    $targets = @("node", "chromium", "playwright")
    foreach ($name in $targets) {
        $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
        foreach ($p in $procs) {
            try {
                $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)").CommandLine
                if ($cmd -like "*nanobot*" -or $cmd -like "*google-ai-mode-mcp*" -or $cmd -like "*playwright*") {
                    # Safety: Don't kill the Gemini CLI node process
                    if ($cmd -notlike "*gemini-cli*") {
                        Write-Host "Cleaning up zombie $name process (PID: $($p.Id))..." -ForegroundColor Gray
                        $p | Stop-Process -Force -ErrorAction SilentlyContinue
                    }
                }
            } catch {}
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
Write-Host "Logging to: $LogFile" -ForegroundColor Gray

try {
    while($true) {
        # Always clean up before a fresh start
        Stop-NanobotProcesses

        Write-Host "--- Starting Nanobot Gateway (Port 18790) ---" -ForegroundColor Cyan
        
        # We use cmd /c to run the command and redirect stderr to stdout 
        # BEFORE it hits PowerShell. This prevents NativeCommandError (red text)
        # while still allowing Tee-Object to capture everything.
        cmd /c "`"$PythonExe`" `"$AppPath\hayes_gateway_launcher.py`" 2>&1" | Tee-Object -FilePath $LogFile -Append
        
        $exitCode = $LASTEXITCODE

        # Check the exit code
        if ($exitCode -eq 0) {
            Write-Host "`nNanobot shut down gracefully." -ForegroundColor Green
            break
        }

        Write-Host "`nGateway exited unexpectedly with code $exitCode." -ForegroundColor Red
        Write-Host "Restarting in 5 seconds (Press CTRL+C now to stop)..." -ForegroundColor White
        
        Start-Sleep -Seconds 5
    }
}
finally {
    # This block runs even if you press CTRL+C
    Write-Host "`n`n--- Shutdown Signal Received ---" -ForegroundColor Magenta
    Stop-NanobotProcesses
    Write-Host "Nanobot has been stopped. Safe to close this window." -ForegroundColor Green
}
