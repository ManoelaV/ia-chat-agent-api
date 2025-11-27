Param(
    [string]$Model = "",
    [switch]$PullModel,
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

Write-Host "== ia-chat-agent-api: start_local.ps1 =="
Write-Host "Model: $Model    PullModel: $PullModel    Port: $Port"

# Create venv if missing
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtualenv .venv..."
    python -m venv .venv
} else {
    Write-Host ".venv already exists - skipping creation."
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = ".venv\Scripts\python.exe" }

Write-Host "Using Python: $python"

Write-Host "Upgrading pip and installing requirements..."
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
& $python -m pip install python-dotenv

# Copy .env if missing
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item .env.example .env -Force
        Write-Host "Copied .env.example -> .env. Edit .env if needed."
    } else {
        Write-Host "No .env.example found; creating a minimal .env"
        @"
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=$($Model)
PORT=$Port
MOCK_AGENT=false
STRANDS_USE_SDK=false
STRANDS_SDK_PACKAGE=strands
LOG_LEVEL=INFO
"@ | Out-File -Encoding utf8 .env
        Write-Host "Created minimal .env - please edit it if necessary."
    }
} else {
    Write-Host ".env already exists - skipping copy."
}

# Optionally pull Ollama model
if ($PullModel.IsPresent -and $Model) {
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Write-Host "Pulling Ollama model: $Model"
        ollama pull $Model
    } else {
        Write-Host "ollama CLI not found in PATH - cannot pull model."
    }
} elseif ($PullModel.IsPresent -and -not $Model) {
    Write-Host "To pull a model, pass -Model <model-name> and -PullModel"
}

Write-Host "Starting uvicorn (app.main:app) on port $Port..."
& $python -m uvicorn app.main:app --reload --port $Port
