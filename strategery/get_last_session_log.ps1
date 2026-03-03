$logDir = "D:/Nanobot_Storage/logs"
$latest = Get-ChildItem "$logDir/nanobot_*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) {
    Write-Output "No log file found."
    exit 0
}

$lines = Get-Content $latest.FullName
$marker = "--- Initializing Nanobot Strategic Edition ---"

# We search from the end for the last marker
$index = -1
for ($i = $lines.Count - 1; $i -ge 0; $i--) {
    if ($lines[$i] -like "*$marker*") {
        $index = $i
        break
    }
}

if ($index -ge 0) {
    # Extract from marker to end
    $lines[$index..($lines.Count - 1)] | Out-String
} else {
    # Fallback to last 200 lines if no marker found
    $lines | Select-Object -Last 200 | Out-String
}
