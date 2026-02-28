# Simple PowerShell script to sync the local 'development' branch with 'upstream/main'
# Usage: .\hayes_sync_upstream.ps1

Write-Host "Fetching latest changes from 'upstream' (HKUDS/nanobot)..." -ForegroundColor Cyan
git fetch upstream

Write-Host "Merging 'upstream/main' into current branch..." -ForegroundColor Cyan
# This assumes you are on 'development'. If not, we'll check first.
$currentBranch = git branch --show-current
if ($currentBranch -ne "development") {
    Write-Host "Warning: You are currently on '$currentBranch', not 'development'. Please switch to 'development' if this is not intended." -ForegroundColor Yellow
}

$mergeResult = git merge upstream/main --no-edit
if ($LASTEXITCODE -ne 0) {
    Write-Host "Merge failed! You may have conflicts to resolve manually." -ForegroundColor Red
    exit 1
}

Write-Host "Pushing updated '$currentBranch' to 'origin' (your fork)..." -ForegroundColor Cyan
git push origin $currentBranch

# ==========================================
# --- CUSTOMIZATION AUDIT REPORT (Hayes) ---
# ==========================================
Write-Host "`nChecking customization health..." -ForegroundColor Cyan

# Define the "Risk" files to check for changes upstream
$riskyFiles = @(
    "nanobot/agent/loop.py",
    "nanobot/agent/memory.py",
    "nanobot/config/loader.py",
    "nanobot/config/schema.py",
    "nanobot/providers/litellm_provider.py",
    "nanobot/heartbeat/service.py"
)

Write-Host "--------------------------------------------------------" -ForegroundColor White
Write-Host "   Hayes Customization Audit Report (Post-Merge)        " -ForegroundColor Cyan
Write-Host "--------------------------------------------------------" -ForegroundColor White

foreach ($file in $riskyFiles) {
    # Check if the file changed in the merge using git diff directly with the file path
    $changedFile = git diff --name-only ORIG_HEAD HEAD -- $file
    if ($changedFile) {
        Write-Host "[!] ALERT: $file was updated upstream." -ForegroundColor Red
        Write-Host "    -> Action: Verify that 'hayes_gateway_launcher.py' patches are still compatible." -ForegroundColor Yellow
    } else {
        Write-Host "[OK] $file (No changes upstream)" -ForegroundColor Gray
    }
}

Write-Host "--------------------------------------------------------" -ForegroundColor White
Write-Host "Sync and Audit complete! Review any ALERTs above." -ForegroundColor Green
