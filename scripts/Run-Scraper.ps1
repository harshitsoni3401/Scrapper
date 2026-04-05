param(
    [Parameter(Mandatory = $true)][string]$Start,
    [Parameter(Mandatory = $true)][string]$End,
    [int]$Workers = 3,
    [int]$Lookback = 2,
    [string]$Sites = "",
    [switch]$Visible,
    [switch]$NoAggregator
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = if (Test-Path ".venv\Scripts\python.exe") {
    ".\.venv\Scripts\python.exe"
} elseif (Test-Path "test_venv\Scripts\python.exe") {
    ".\test_venv\Scripts\python.exe"
} else {
    throw "No virtual environment found. Run .\scripts\Setup.ps1 first."
}

$argsList = @(
    "-m", "energy_scraper.main",
    "--start", $Start,
    "--end", $End,
    "--workers", $Workers,
    "--lookback", $Lookback
)

if ($Sites) {
    $argsList += @("--sites", $Sites)
}

if ($Visible) {
    $argsList += "--visible"
}

if ($NoAggregator) {
    $argsList += "--no-aggregator"
}

& $python @argsList

