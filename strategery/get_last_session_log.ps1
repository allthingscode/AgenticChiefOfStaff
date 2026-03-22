# Define search locations
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDirs = @("D:\Nanobot_Storage\logs", "$projectRoot\logs")

# Keywords to identify critical issues
$keywords = @("Error", "Exception", "Failed", "Anomaly", "Violation", "invalid_grant", "Token expired")
$pattern = ($keywords | ForEach-Object { [regex]::Escape($_) }) -join "|"

# Set output encoding to UTF-8
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$allMatches = @()

foreach ($dir in $logDirs) {
    if (Test-Path $dir) {
        # Get all log files modified in the last 24 hours
        $logs = Get-ChildItem -Path $dir -Filter "*.log" | Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-1) }
        
        foreach ($log in $logs) {
            $content = Get-Content -Path $log.FullName -Tail 200
            $matches = $content | Where-Object { $_ -match $pattern }
            
            if ($matches) {
                $allMatches += "--- FROM LOG: $($log.Name) ($($log.LastWriteTime)) ---"
                $allMatches += $matches
                $allMatches += ""
            }
        }
    }
}

if ($allMatches.Count -gt 0) {
    # Keep output within safe limits (last 1000 lines of matches)
    $allMatches | Select-Object -Last 1000 | Out-String
} else {
    Write-Output "No critical issues found in recent logs (last 24h) across $($logDirs -join ', ')."
}
