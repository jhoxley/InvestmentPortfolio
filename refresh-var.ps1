<#
.SYNOPSIS
    Triggers a historical-simulation VaR calculation run for one or more accounts
    against a running portfolio-analysis-service, and waits for each to finish.

.DESCRIPTION
    A standalone counterpart to run_end_to_end.ps1's "Compute Value at Risk" phase,
    for refreshing VaR on its own (e.g. a daily scheduled task) without rerunning the
    full ingestion pipeline. Requires portfolio-analysis-service (and, transitively,
    market-data-web-service) to already be running at -BaseUrl.

.PARAMETER BaseUrl
    portfolio-analysis-service base URL. Default: http://127.0.0.1:8000

.PARAMETER Accounts
    Account names to refresh. If omitted, every account reported by GET /v1/accounts
    with a position_ladder is refreshed.

.PARAMETER Mode
    "missing" (default) recomputes only what has changed since the last run; "full"
    recomputes every date.

.PARAMETER TimeoutMinutes
    Per-account wait limit for a run to finish. Default: 15.

.PARAMETER PollSeconds
    Polling interval while waiting for a run to finish. Default: 2.

.OUTPUTS
    Exit code 0 if every account's run succeeded; 1 if any failed, timed out, or
    could not be queued.
#>

param(
    [string]   $BaseUrl = 'http://127.0.0.1:8000',
    [string[]] $Accounts,
    [ValidateSet('missing', 'full')] [string] $Mode = 'missing',
    [int]      $TimeoutMinutes = 15,
    [int]      $PollSeconds = 2
)

Import-Module (Join-Path $PSScriptRoot 'scripts\VarRefresh.psm1') -Force

function Write-RefreshScriptLog {
    param([string] $Message, [string] $Level = 'Info')
    $color = switch ($Level) {
        'OK'    { 'Green' }
        'Warn'  { 'Yellow' }
        'Error' { 'Red' }
        default { 'White' }
    }
    Write-Host $Message -ForegroundColor $color
}

if (-not $Accounts -or $Accounts.Count -eq 0) {
    Write-RefreshScriptLog "Listing accounts from $BaseUrl/v1/accounts..." 'Info'
    try {
        $accountsResponse = Invoke-WebRequest -Uri "$BaseUrl/v1/accounts" -UseBasicParsing -ErrorAction Stop
        $accountsBody = $accountsResponse.Content | ConvertFrom-Json
        $Accounts = @($accountsBody.accounts) |
            Where-Object { $_.position_ladder } |
            ForEach-Object { $_.account_name }
    } catch {
        Write-RefreshScriptLog "Failed to list accounts from ${BaseUrl}: $_" 'Error'
        exit 1
    }
}

if (-not $Accounts -or $Accounts.Count -eq 0) {
    Write-RefreshScriptLog 'No accounts with a position ladder were found; nothing to refresh.' 'Warn'
    exit 0
}

Write-RefreshScriptLog "Refreshing VaR (mode=$Mode) for: $($Accounts -join ', ')" 'Info'

$results = @()
foreach ($account in $Accounts) {
    Write-RefreshScriptLog "" 'Info'
    Write-RefreshScriptLog "-- $account --------------------------------" 'Info'
    $result = Invoke-VarRefresh -BaseUrl $BaseUrl -AccountName $account -Mode $Mode `
        -TimeoutMinutes $TimeoutMinutes -PollSeconds $PollSeconds `
        -LogFunction { param($Message, $Level) Write-RefreshScriptLog $Message $Level }
    $results += $result

    if ($result.Status -eq 'succeeded') {
        Write-RefreshScriptLog "  $account : succeeded -- $($result.DatesComputed) date(s) computed, $($result.WarningCount) warning(s)." 'OK'
        foreach ($warning in $result.Warnings) {
            Write-RefreshScriptLog "    warning: [$($warning.kind)] $($warning.identifier) $($warning.date): $($warning.message)" 'Warn'
        }
    } else {
        Write-RefreshScriptLog "  $account : $($result.Status) -- $($result.FailureDetail)" 'Error'
    }
}

Write-Host ''
Write-Host 'Summary:' -ForegroundColor Cyan
$results | Format-Table -Property Account, Status, DatesComputed, WarningCount -AutoSize | Out-Host

$failed = @($results | Where-Object { $_.Status -ne 'succeeded' })
if ($failed.Count -gt 0) {
    Write-RefreshScriptLog "$($failed.Count) of $($results.Count) account(s) did not succeed." 'Error'
    exit 1
}

Write-RefreshScriptLog "All $($results.Count) account(s) refreshed successfully." 'OK'
exit 0
