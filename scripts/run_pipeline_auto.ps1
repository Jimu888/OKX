param(
  [ValidateSet('auto','okx','binance')]
  [string]$Exchange = 'auto',

  [string]$Profile = 'live',
  [int]$Days = 90,
  [string]$Name = 'Lan',

  [string]$OrdersCsv = $null,
  [string]$TradesCsv = $null,
  [string]$IncomeCsv = $null
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition | Split-Path -Parent
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'

function Run-Binance {
  if (-not $OrdersCsv -or -not $TradesCsv -or -not $IncomeCsv) {
    throw 'Binance mode requires -OrdersCsv -TradesCsv -IncomeCsv'
  }

  $run = Join-Path $root ("runs\\binance_" + $ts)
  $raw = Join-Path $run 'raw'
  $analysis = Join-Path $run 'analysis'
  $output = Join-Path $run 'output'
  New-Item -ItemType Directory -Force -Path $raw, $analysis, $output | Out-Null

  & python (Join-Path $root 'scripts\\import_binance_usdm_csvs.py') --orders $OrdersCsv --trades $TradesCsv --income $IncomeCsv --out $raw | Out-Null
  & python (Join-Path $root 'scripts\\analyze_contracts.py') --raw $raw --out $analysis | Out-Null
  & python (Join-Path $root 'scripts\\render_report.py') --analysis (Join-Path $analysis 'analysis.json') --out $output | Out-Null
  & python (Join-Path $root 'scripts\\build_letter_prompt.py') --analysis (Join-Path $analysis 'analysis.json') --report (Join-Path $output 'REPORT.md') --out $output --name $Name | Out-Null

  Write-Host "DONE: $run"
  Write-Host "- raw: $raw"
  Write-Host "- analysis: $analysis"
  Write-Host "- output: $output"
  Write-Host "[NEXT] Letter prompt created: $(Join-Path $output 'LETTER_PROMPT.md')"
}

function Run-OKX {
  # Ensure OKX_* env vars won't override ~/.okx/config.toml
  $env:OKX_API_KEY = $null
  $env:OKX_SECRET_KEY = $null
  $env:OKX_PASSPHRASE = $null
  $env:OKX_SITE = $null
  $env:OKX_API_BASE_URL = $null

  $run = Join-Path $root ("runs\\" + $ts)
  $raw = Join-Path $run 'raw'
  $analysis = Join-Path $run 'analysis'
  $output = Join-Path $run 'output'
  New-Item -ItemType Directory -Force -Path $raw, $analysis, $output | Out-Null

  & node (Join-Path $root 'scripts\\export_contracts.js') --profile $Profile --days $Days --out $raw | Out-Null
  & python (Join-Path $root 'scripts\\analyze_contracts.py') --raw $raw --out $analysis | Out-Null
  & python (Join-Path $root 'scripts\\render_report.py') --analysis (Join-Path $analysis 'analysis.json') --out $output | Out-Null
  & python (Join-Path $root 'scripts\\build_letter_prompt.py') --analysis (Join-Path $analysis 'analysis.json') --report (Join-Path $output 'REPORT.md') --out $output --name $Name | Out-Null

  Write-Host "DONE: $run"
  Write-Host "- raw: $raw"
  Write-Host "- analysis: $analysis"
  Write-Host "- output: $output"
  Write-Host "[NEXT] Letter prompt created: $(Join-Path $output 'LETTER_PROMPT.md')"
}

if ($Exchange -eq 'auto') {
  if ($OrdersCsv -or $TradesCsv -or $IncomeCsv) {
    $Exchange = 'binance'
  } else {
    $Exchange = 'okx'
  }
}

if ($Exchange -eq 'binance') {
  Run-Binance
} elseif ($Exchange -eq 'okx') {
  Run-OKX
} else {
  throw "Unknown exchange: $Exchange"
}
