<#
.SYNOPSIS
    Sends Gemini CLI notifications to Discord via Webhook.
    Retrieves the webhook URL from the environment variable 'DISCORD_WEBHOOK' or 'GOOGLE_CHAT_WEBHOOK'.
#>

# 1. Capture JSON input from Gemini CLI (stdin)
$inputJson = $Input | Out-String | ConvertFrom-Json

# 2. Retrieve Webhook URL (Priority: Discord Env > Google Env > .env file)
$webhookUrl = $env:DISCORD_WEBHOOK
if (-not $webhookUrl) { $webhookUrl = $env:GOOGLE_CHAT_WEBHOOK }

if (-not $webhookUrl -and (Test-Path ".env")) {
    $envContent = Get-Content ".env" | ConvertFrom-StringData
    $webhookUrl = $envContent.DISCORD_WEBHOOK
    if (-not $webhookUrl) { $webhookUrl = $envContent.GOOGLE_CHAT_WEBHOOK }
}

# 3. Validation & Resilience
if (-not $webhookUrl) {
    [Console]::Error.WriteLine("[!] Error: No Webhook URL found (Set DISCORD_WEBHOOK environment variable).")
    exit 0 
}

# 4. Construct Discord Payload (Rich Embed)
$color = 3447003 # Default Blue
if ($inputJson.notification_type -match "Error") { $color = 15158332 } # Red
if ($inputJson.notification_type -match "Permission") { $color = 15844367 } # Gold

$embed = @{
    title = "Gemini CLI Notification"
    description = $inputJson.message
    color = $color
    fields = @(
        @{ name = "Type"; value = $inputJson.notification_type; inline = $true }
        @{ name = "Session ID"; value = $inputJson.session_id; inline = $true }
    )
    timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

$payload = @{
    username = "Gemini CLI"
    content = "@everyone Gemini needs attention: $($inputJson.message)"
    embeds = @($embed)
} | ConvertTo-Json -Depth 10

# 5. Send Request with Timeout & Error Handling
try {
    Invoke-RestMethod -Uri $webhookUrl -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 5
    Write-Output '{"status": "success"}'
} catch {
    [Console]::Error.WriteLine("[!] Discord Bridge Failed: $($_.Exception.Message)")
    Write-Output '{"status": "failure"}'
}
