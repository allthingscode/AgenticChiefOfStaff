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

$customFiles = @("strategic_launcher.py", "strategic_google_surgical.py", "strategic_email_reporter.py")
foreach ($f in $customFiles) {
    if (Test-Path $f) {
        Write-Host "  [OK] Custom file preserved: $f" -ForegroundColor Green
    } else {
        Write-Host "  [WARNING] Custom file missing: $f" -ForegroundColor Yellow
    }
}

Write-Host "Audit Complete." -ForegroundColor Green
