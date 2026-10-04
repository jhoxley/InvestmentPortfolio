<#
.SYNOPSIS
    Shared helper for queuing and waiting on a portfolio-analysis-service VaR
    calculation run (feature 012-var-calculation-runs).

.DESCRIPTION
    Exports Invoke-VarRefresh, used by both refresh-var.ps1 (standalone refresh) and
    run_end_to_end.ps1's "Compute Value at Risk" phase, so the two never drift.
#>

function Invoke-VarRefresh {
    <#
    .SYNOPSIS
        POSTs a VaR run for one account and polls it to completion.
    .DESCRIPTION
        POSTs /v1/accounts/{account}/risk/var/runs. On HTTP 409 (a run is already
        active for this account), adopts that run via the problem body's
        _links.active_run instead of failing. Polls GET on the run until it reaches
        "succeeded" or "failed", or until TimeoutMinutes elapses.
    .OUTPUTS
        A PSCustomObject: Account, Status ("succeeded" | "failed" | "timed_out" |
        "not_queued"), DatesComputed, WarningCount, Warnings (up to 5), FailureDetail.
    #>
    param(
        [Parameter(Mandatory = $true)]  [string] $BaseUrl,
        [Parameter(Mandatory = $true)]  [string] $AccountName,
        [ValidateSet('missing', 'full')] [string] $Mode = 'missing',
        [int] $TimeoutMinutes = 15,
        [int] $PollSeconds = 2,
        [scriptblock] $LogFunction = { param($Message, $Level) Write-Host $Message }
    )

    function Write-RefreshLog {
        param([string] $Message, [string] $Level = 'Info')
        & $LogFunction $Message $Level
    }

    $result = [PSCustomObject]@{
        Account       = $AccountName
        Status        = 'not_queued'
        DatesComputed = 0
        WarningCount  = 0
        Warnings      = @()
        FailureDetail = $null
    }

    $runsUrl = "$BaseUrl/v1/accounts/$AccountName/risk/var/runs"
    $bodyJson = (@{ mode = $Mode } | ConvertTo-Json -Compress)
    $runId = $null

    try {
        $response = Invoke-WebRequest -Uri $runsUrl -Method Post -Body $bodyJson `
            -ContentType 'application/json' -UseBasicParsing -ErrorAction Stop
        $parsed = $response.Content | ConvertFrom-Json
        $runId = $parsed.run_id
    } catch {
        $statusCode = $null
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        if ($statusCode -eq 409) {
            try {
                $rawBody = $null
                if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
                    $rawBody = $_.ErrorDetails.Message
                } elseif ($_.Exception.Response) {
                    $stream = $_.Exception.Response.GetResponseStream()
                    $reader = [System.IO.StreamReader]::new($stream)
                    $rawBody = $reader.ReadToEnd()
                }
                $errorBody = $rawBody | ConvertFrom-Json
                $activeLink = $errorBody._links.active_run
                $runId = ($activeLink -split '/')[-1]
                Write-RefreshLog "  ${AccountName}: a run is already active; adopting run $runId." 'Warn'
            } catch {
                $result.Status = 'failed'
                $result.FailureDetail = "Received 409 but could not parse the active run link: $_"
                return $result
            }
        } else {
            $result.Status = 'failed'
            $result.FailureDetail = "Failed to queue a VaR run: $_"
            return $result
        }
    }

    if (-not $runId) {
        $result.Status = 'failed'
        $result.FailureDetail = 'No run_id was returned by the create-run request.'
        return $result
    }

    $getUrl = "$runsUrl/$runId"
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $final = $null

    while ((Get-Date) -lt $deadline) {
        try {
            $poll = Invoke-WebRequest -Uri $getUrl -UseBasicParsing -ErrorAction Stop
            $final = $poll.Content | ConvertFrom-Json
            if ($final.status -eq 'succeeded' -or $final.status -eq 'failed') {
                break
            }
        } catch {
            # Transient polling failure -- keep trying until the deadline.
        }
        Start-Sleep -Seconds $PollSeconds
    }

    if (-not $final -or ($final.status -ne 'succeeded' -and $final.status -ne 'failed')) {
        $result.Status = 'timed_out'
        $result.FailureDetail = "Run '$runId' did not finish within $TimeoutMinutes minute(s)."
        return $result
    }

    $result.Status = $final.status
    $result.DatesComputed = $final.dates_computed
    $result.WarningCount = @($final.warnings).Count
    $result.Warnings = @($final.warnings) | Select-Object -First 5
    if ($final.status -eq 'failed') {
        $result.FailureDetail = $final.failure.detail
    }
    return $result
}

Export-ModuleMember -Function Invoke-VarRefresh
