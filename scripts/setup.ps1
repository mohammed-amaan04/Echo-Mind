param(
  [ValidateSet("prototype", "full")]
  [string]$Profile = "prototype"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

$requirementsFile = if ($Profile -eq "full") { "all.txt" } else { "prototype.txt" }
pip install -r $requirementsFile
python scripts\bootstrap_nlp.py

Write-Host "EchoMind environment setup complete with profile: $Profile"

