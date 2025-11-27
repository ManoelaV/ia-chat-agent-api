# Copy .env.example to .env and configure for Ollama gpt-oss
# Usage: run in PowerShell from project root with venv activated

$src = Join-Path -Path (Get-Location) -ChildPath '.env.example'
$dst = Join-Path -Path (Get-Location) -ChildPath '.env'

if (-Not (Test-Path $src)) {
    Write-Error ".env.example not found"
    exit 1
}

Copy-Item -Path $src -Destination $dst -Force

# Set recommended values for Ollama gpt-oss
# Note: change OLLAMA_URL if your Ollama host uses a different address/port

$envContent = Get-Content $dst
$envContent = $envContent -replace 'OLLAMA_MODEL=.*', 'OLLAMA_MODEL=gpt-oss'
$envContent = $envContent -replace 'MOCK_AGENT=.*', 'MOCK_AGENT=false'

Set-Content -Path $dst -Value $envContent

Write-Host "Created .env with OLLAMA_MODEL=gpt-oss and MOCK_AGENT=false"
