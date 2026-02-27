# Simple PowerShell script to sync the local 'development' branch with 'upstream/main'
# Usage: .\sync-upstream.ps1

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

Write-Host "Sync complete! You are now up to date with the latest from HKUDS/nanobot." -ForegroundColor Green
