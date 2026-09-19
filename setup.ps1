param([switch]$Install)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if ($Install) {
    py -3 -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
py -3 -c "import requests, dotenv, yaml, pytest; print('Runtime dependencies: OK')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
py -3 -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Local verification passed; ChatGPT deployment is a separate step."
Write-Host "Network collection: set FIRECRAWL_API_KEY in .env"
Write-Host "GPT mode: set OPENAI_API_KEY and OPENAI_MODEL, then add --gpt"
