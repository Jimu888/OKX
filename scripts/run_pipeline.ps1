param(
  [string]$Profile = "live",
  [int]$Days = 60,
  [string]$Name = "TradeMate"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-LastExitCode {
  param(
    [string]$StepName
  )

  if ($LASTEXITCODE -ne 0) {
    throw "$StepName failed with exit code $LASTEXITCODE"
  }
}

# Ensure OKX_* env vars cannot override ~/.okx/config.toml
$env:OKX_API_KEY=$null
$env:OKX_SECRET_KEY=$null
$env:OKX_PASSPHRASE=$null
$env:OKX_SITE=$null
$env:OKX_API_BASE_URL=$null

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition | Split-Path -Parent
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$run = Join-Path $root ("runs\\" + $ts)
$raw = Join-Path $run 'raw'
$analysis = Join-Path $run 'analysis'
$output = Join-Path $run 'output'

New-Item -ItemType Directory -Force -Path $raw,$analysis,$output | Out-Null

& node (Join-Path $root 'scripts\\export_contracts.js') --profile $Profile --days $Days --out $raw
Assert-LastExitCode 'Export'

$rawFiles = Get-ChildItem -Path $raw -File -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 0 }
if (-not $rawFiles) {
  throw "Export produced no raw data. Stop here to avoid generating an empty report."
}

& python (Join-Path $root 'scripts\\analyze_contracts.py') --raw $raw --out $analysis
Assert-LastExitCode 'Analyze'

& python (Join-Path $root 'scripts\\render_report.py') --analysis (Join-Path $analysis 'analysis.json') --out $output
Assert-LastExitCode 'Render report'

& python (Join-Path $root 'scripts\\build_letter_prompt.py') `
  --analysis (Join-Path $analysis 'analysis.json') `
  --report (Join-Path $output 'REPORT.md') `
  --out $output `
  --name $Name
Assert-LastExitCode 'Build letter prompt'

if (Test-Path (Join-Path $output 'LETTER.md')) {
  & python (Join-Path $root 'scripts\\render_letter_html.py') `
    --analysis (Join-Path $analysis 'analysis.json') `
    --template (Join-Path $root 'assets\\letter-version.template.html') `
    --letter-md (Join-Path $output 'LETTER.md') `
    --out $output
  Assert-LastExitCode 'Render letter HTML'
} else {
  Write-Host "[NEXT] Letter prompt generated: $(Join-Path $output 'LETTER_PROMPT.md')"
  Write-Host "[NEXT] Ask the agent to write: $(Join-Path $output 'LETTER.md')"
  Write-Host "[NEXT] After that, run render_letter_html.py to generate the webpage."
}

Write-Host "DONE: $run"
Write-Host "- raw: $raw"
Write-Host "- analysis: $analysis"
Write-Host "- output: $output"
