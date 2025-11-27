Param(
    [string]$Message = "Quanto é 1234 * 5678?",
    [string]$Url = "http://127.0.0.1:8000/chat"
)

# Build compact JSON and send as UTF-8 bytes to avoid PowerShell/curl quoting issues
$payload = @{ message = $Message } | ConvertTo-Json -Compress
Write-Host "Sending to $Url -> $payload"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)

try {
    $resp = Invoke-RestMethod -Uri $Url -Method Post -Body $bytes -ContentType 'application/json; charset=utf-8'
    Write-Host "Response:`n" (ConvertTo-Json $resp -Depth 5)
} catch {
    Write-Host "Request failed:`n" $_.Exception.Message
    if ($_.Exception.Response -ne $null) {
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $body = $reader.ReadToEnd()
            Write-Host "Response body:`n$body"
        } catch {
            # ignore
        }
    }
}
