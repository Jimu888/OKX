param(
  [string]$Profile = "live",
  [int]$Days = 90,
  [string]$Name = "澜"
)

$ErrorActionPreference = 'Stop'

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

Write-Host "[1/4] 导出 OKX 数据（合约 + 现货 + 理财）..."
node (Join-Path $root 'scripts\\export_contracts.js') --profile $Profile --days $Days --out $raw

Write-Host "[2/4] 分析数据..."
python (Join-Path $root 'scripts\\analyze_contracts.py') --raw $raw --out $analysis | Out-Null

Write-Host "[3/4] 生成报告 + 模板信..."
python (Join-Path $root 'scripts\\render_report.py') --analysis (Join-Path $analysis 'analysis.json') --out $output | Out-Null
python (Join-Path $root 'scripts\\render_letter_md.py') --analysis (Join-Path $analysis 'analysis.json') --out $output | Out-Null
python (Join-Path $root 'scripts\\render_letter_html.py') --analysis (Join-Path $analysis 'analysis.json') --template (Join-Path $root 'assets\\letter-version.template.html') --out $output | Out-Null

Write-Host "[4/4] 生成 AI 信件($Name)..."
if ($env:ANTHROPIC_API_KEY) {
    python (Join-Path $root 'scripts\\render_letter_ai.py') `
        --analysis (Join-Path $analysis 'analysis.json') `
        --out $output `
        --name $Name
} else {
    Write-Host "[WARN] 未设置 ANTHROPIC_API_KEY，跳过 AI 信件生成。"
}

Write-Host ""
Write-Host "DONE: $run"
