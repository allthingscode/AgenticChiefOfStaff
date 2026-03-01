# Usage: .\sync_upstream.ps1
# This script helps sync with the upstream repository while preserving Strategic Edition customizations.

Write-Host "--- Starting Upstream Sync ---" -ForegroundColor Cyan

# 1. Fetch from upstream
git fetch upstream

# 2. Attempt merge
Write-Host "Attempting merge from upstream/main..."
git merge upstream/main

if ($LASTEXITCODE -ne 0) {
    Write-Host "CONFLICTS DETECTED. Please resolve them manually." -ForegroundColor Red
    exit 1
}

# 3. Customization Audit
Write-Host "   Customization Audit Report (Post-Merge)        " -ForegroundColor Cyan
Write-Host "--------------------------------------------------" -ForegroundColor Gray

$customFiles = @(
    "strategery/strategic_launcher.py", 
    "strategery/strategic_google_surgical.py", 
    "strategery/strategic_email_reporter.py",
    "strategery/patches/",
    "strategic_sync_upstream.ps1",
    "start_strategic_nanobot.ps1"
)
foreach ($f in $customFiles) {
    if (Test-Path $f) {
        Write-Host "  [OK] Custom component preserved: $f" -ForegroundColor Green
    } else {
        Write-Host "  [WARNING] Custom component missing: $f" -ForegroundColor Yellow
    }
}

Write-Host "Audit Complete." -ForegroundColor Green
