param(
  [Parameter(Mandatory=$true)][string]$Ledger,
  [string]$Start = "2020-01-01",
  [string]$End = "2026-08-01",
  [string]$Output = "same-broker-v05",
  [string[]]$Symbols = @("EURUSD","GBPUSD","XAUUSD","US30"),
  [string[]]$Aliases = @()
)

$ErrorActionPreference = "Stop"

Write-Host "V2 Quant v0.5 Same-Broker Reconstruction" -ForegroundColor Cyan
Write-Host "This does not place trades. MT5 is read only for historical export." -ForegroundColor Yellow

if (-not (Test-Path $Ledger)) {
  throw "Ledger not found: $Ledger"
}

python -m pip install -r requirements-mt5.txt

$exportArgs = @(
  "scripts/v05_mt5_export.py",
  "--symbols"
) + $Symbols + @(
  "--start", $Start,
  "--end", $End,
  "--out", "$Output/export"
)
foreach ($a in $Aliases) {
  $exportArgs += @("--alias", $a)
}

Write-Host "`n[1/5] Exporting original-broker bars and bid/ask ticks..." -ForegroundColor Cyan
python @exportArgs
if ($LASTEXITCODE -ne 0) { throw "MT5 export failed" }

Write-Host "`n[2/5] Verifying immutable file hashes..." -ForegroundColor Cyan
python scripts/v05_verify_export.py --export-root "$Output/export"
if ($LASTEXITCODE -ne 0) { throw "Export hash verification failed" }

Write-Host "`n[3/5] Replaying recovered V2 trades on the same broker..." -ForegroundColor Cyan
python scripts/v05_same_broker_relabel_runner.py `
  --ledger $Ledger `
  --export-root "$Output/export" `
  --out "$Output/v05_same_broker_relabels.csv"
if ($LASTEXITCODE -ne 0) { throw "Same-broker relabeling failed" }

Write-Host "`n[4/5] Running pre-registered label-integrity gate..." -ForegroundColor Cyan
python scripts/v05_label_gate.py `
  --relabels "$Output/v05_same_broker_relabels.csv" `
  --out "$Output/gate"
if ($LASTEXITCODE -ne 0) { throw "Label-gate analysis failed" }

$gatePath = "$Output/gate/v05_label_gate_summary.json"
$gate = Get-Content $gatePath -Raw | ConvertFrom-Json

Write-Host "`n[5/5] Training eligibility" -ForegroundColor Cyan
if ($gate.training_eligible -eq $true) {
  Write-Host "Label gate PASSED. Creating executable-label research ledger." -ForegroundColor Green
  python scripts/v05_prepare_training_ledger.py `
    --ledger $Ledger `
    --relabels "$Output/v05_same_broker_relabels.csv" `
    --gate-summary $gatePath `
    --out "$Output/v05_execution_training_ledger.csv"
  if ($LASTEXITCODE -ne 0) { throw "Training-ledger preparation failed" }
} else {
  Write-Host "Label gate FAILED. No training ledger was created." -ForegroundColor Red
  Write-Host "This is intentional. Diagnose same-broker label disagreement before any retraining." -ForegroundColor Yellow
}

Write-Host "`nFinished. Research outputs: $Output" -ForegroundColor Cyan
Write-Host "Raw tick files stay local; share the small CSV/JSON summaries if remote review is needed." -ForegroundColor Gray
