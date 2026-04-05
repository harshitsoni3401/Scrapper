param()

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = if (Test-Path ".venv\Scripts\python.exe") {
    ".\.venv\Scripts\python.exe"
} elseif (Test-Path "test_venv\Scripts\python.exe") {
    ".\test_venv\Scripts\python.exe"
} else {
    throw "No virtual environment found. Run .\scripts\Setup.ps1 first."
}

& $python -m pytest -p no:cacheprovider energy_scraper\test_scraper.py
& $python verify_config.py
& $python -m energy_scraper.main --help
