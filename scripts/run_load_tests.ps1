#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run k6 load tests against the DJPS API running in Docker Compose.

.DESCRIPTION
    Starts the dev stack (if not already running), then executes the requested
    load test scenario via the grafana/k6 Docker image.

.PARAMETER Test
    Which test to run: smoke | load | spike  (default: smoke)

.EXAMPLE
    .\scripts\run_load_tests.ps1
    .\scripts\run_load_tests.ps1 -Test load
    .\scripts\run_load_tests.ps1 -Test spike
#>
param(
    [ValidateSet("smoke", "load", "spike")]
    [string]$Test = "smoke"
)

$ComposeFile = Join-Path $PSScriptRoot "..\docker\docker-compose.yml"
$Script      = "/scripts/$Test.js"

Write-Host ""
Write-Host "=== DJPS Load Test Runner ===" -ForegroundColor Cyan
Write-Host "Test    : $Test"              -ForegroundColor Cyan
Write-Host "Script  : $Script"            -ForegroundColor Cyan
Write-Host ""

# Ensure the dev stack is running
Write-Host "Starting dev stack..." -ForegroundColor Yellow
docker compose -f $ComposeFile up -d --wait 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start dev stack. Aborting." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Running k6 $Test test..." -ForegroundColor Yellow
Write-Host ("─" * 60)

docker compose -f $ComposeFile --profile load run --rm k6 run $Script

$exitCode = $LASTEXITCODE

Write-Host ("─" * 60)
if ($exitCode -eq 0) {
    Write-Host "PASSED — all thresholds met." -ForegroundColor Green
} else {
    Write-Host "FAILED — one or more thresholds breached (exit $exitCode)." -ForegroundColor Red
}

exit $exitCode
