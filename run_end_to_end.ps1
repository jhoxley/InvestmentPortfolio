<#
.SYNOPSIS
    End-to-end orchestration: prepare ledgers, start services, ingest into the portfolio analysis API.

.DESCRIPTION
    Executes the full investment pipeline in sequence:

      Phase 1  Run AccountPreparationPipeline\run_pipeline.ps1 to consolidate journals,
               build ledgers, and generate sub-account ledger XLSX files.

      Phase 2  Validate and (if required) write config.yaml files for both web services,
               ensuring ports and data directories are non-conflicting.

      Phase 3  Start the market-data-web-service on localhost:$MarketDataPort and poll
               the /openapi.json endpoint until the service is accepting requests.

      Phase 4  Start the portfolio-analysis-service on localhost:$AnalysisPort and poll
               /health until the service is ready.

      Phase 5  POST each sub-account ledger XLSX to the portfolio-analysis-service
               ingestion endpoint.

      Phase 6  POST each capital ledger XLSX (also produced by run_pipeline.ps1's
               create_capital_ledger step) to the portfolio-analysis-service
               capital ingestion endpoint.

      Phase 7  Start the Investment Portfolio Browser (Dash app) on
               localhost:$DashPort, configured to read the market-data-web-service
               and portfolio-analysis-service URLs started above, poll it until
               ready, and open it in the user's default browser.

    All steps are written to both the console and a timestamped log file.
    All three service processes (market-data-web-service, portfolio-analysis-service,
    and the Dash app) are terminated on script exit (success or failure).

.PARAMETER SkipPipeline
    If set, Phase 1 (AccountPreparationPipeline) is skipped. Useful when the
    ledger files are already up to date.

.PARAMETER HealthTimeoutSeconds
    Maximum number of seconds to wait for each service to pass its health check.
    Default: 60.
#>
[CmdletBinding()]
param(
    [switch] $SkipPipeline,
    [int]    $HealthTimeoutSeconds = 60,
    [switch] $NonInteractive          # Skip the ReadKey prompt; services remain running after exit.
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# -- Configuration -------------------------------------------------------------
#
# Ports  - each service must use a distinct port so all three can run concurrently.
$MarketDataPort = 8001
$AnalysisPort   = 8000
$DashPort       = 8050

# Hosts  - all services bind to loopback only (no external exposure).
$MarketDataHost = "127.0.0.1"
$AnalysisHost   = "127.0.0.1"
$DashAppHost    = "127.0.0.1"

# Absolute paths to each service root.
$RepoRoot              = $PSScriptRoot
$PipelineDir           = Join-Path $RepoRoot "AccountPreparationPipeline"
$MarketDataDir         = Join-Path $RepoRoot "market-data-web-service"
$AnalysisDir           = Join-Path $RepoRoot "portfolio-analysis-service"
$DashAppDir            = Join-Path $RepoRoot "portfolio-browser"

# Executable paths inside each service's virtual environment.
$PipelinePython        = Join-Path $PipelineDir  ".venv\Scripts\python.exe"
$MarketDataUvicorn     = Join-Path $MarketDataDir ".venv\Scripts\uvicorn.exe"
$AnalysisUvicorn       = Join-Path $AnalysisDir  ".venv\Scripts\uvicorn.exe"
$DashAppPython         = Join-Path $DashAppDir  ".venv\Scripts\python.exe"

# Health / readiness URLs.
# NOTE: market-data-web-service has no dedicated /health endpoint; /openapi.json
# is a reliable proxy  - FastAPI always serves it once the app is started.
$MarketDataHealthUrl   = "http://${MarketDataHost}:${MarketDataPort}/openapi.json"
$AnalysisHealthUrl     = "http://${AnalysisHost}:${AnalysisPort}/health"
$DashAppUrl            = "http://${DashAppHost}:${DashPort}/"
$DashAppHealthUrl      = $DashAppUrl

# Ingestion endpoint base (portfolio-analysis-service).
$AnalysisBaseUrl       = "http://${AnalysisHost}:${AnalysisPort}"

# Base URLs the Dash app is configured to read from  - the same market-data-web-service
# and portfolio-analysis-service instances started in Phases 3-4 above.
$MarketDataBaseUrl     = "http://${MarketDataHost}:${MarketDataPort}"

# Sub-account ledger files produced by run_pipeline.ps1 and the account names
# they should be registered under in the portfolio-analysis-service.
# Account names must match ^[A-Za-z0-9_-]{1,64}$.
$InvestmentsDir        = "C:\Users\jhoxl\OneDrive\Investments"

$SubAccountLedgers = @(
    @{
        AccountName  = "HL-SIPP"
        LedgerPath   = Join-Path $InvestmentsDir "HL_SIPP_SubAccount_Ledger.xlsx"
        DisplayName  = "HL SIPP"
    }
    @{
        AccountName  = "HL-ISA"
        LedgerPath   = Join-Path $InvestmentsDir "HL_ISA_SubAccount_Ledger.xlsx"
        DisplayName  = "HL ISA"
    }
)

# Capital ledger files produced by run_pipeline.ps1's create_capital_ledger step
# (Step 3, for accounts with IsCapitalAccount=$true) and the account names they
# should be registered under in the portfolio-analysis-service. Account names
# match those used for $SubAccountLedgers above  - capital and position-ladder
# resources are keyed by the same account_name but stored independently.
$CapitalLedgers = @(
    @{
        AccountName  = "HL-SIPP"
        LedgerPath   = Join-Path $InvestmentsDir "HL_SIPP_Capital_Ledger.xlsx"
        DisplayName  = "HL SIPP"
    }
    @{
        AccountName  = "HL-ISA"
        LedgerPath   = Join-Path $InvestmentsDir "HL_ISA_Capital_Ledger.xlsx"
        DisplayName  = "HL ISA"
    }
)

# Log file  - written to a logs/ directory in the repo root, timestamped.
$LogDir  = Join-Path $RepoRoot "logs"
$LogFile = Join-Path $LogDir ("end_to_end_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

# -- Logging -------------------------------------------------------------------

function Initialize-Log {
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir | Out-Null
    }
    $header = @(
        ("=" * 72),
        "  Investment Portfolio  - End-to-End Run",
        "  Started : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
        "  Log     : $LogFile",
        ("=" * 72)
    ) -join "`n"
    $header | Out-File -FilePath $LogFile -Encoding utf8
    Write-Host $header -ForegroundColor DarkCyan
}

function Write-Log {
    param(
        [string] $Message,
        [ValidateSet('Info','OK','Warn','Error','Phase','Detail')] [string] $Level = 'Info'
    )
    $timestamp = Get-Date -Format "HH:mm:ss"
    $prefix = switch ($Level) {
        'Phase'  { "[$timestamp] [PHASE]" }
        'OK'     { "[$timestamp] [OK   ]" }
        'Warn'   { "[$timestamp] [WARN ]" }
        'Error'  { "[$timestamp] [ERROR]" }
        'Detail' { "[$timestamp]        " }
        default  { "[$timestamp] [INFO ]" }
    }
    $line = "$prefix $Message"
    $line | Out-File -FilePath $LogFile -Append -Encoding utf8

    $color = switch ($Level) {
        'Phase'  { 'Cyan' }
        'OK'     { 'Green' }
        'Warn'   { 'Yellow' }
        'Error'  { 'Red' }
        'Detail' { 'DarkGray' }
        default  { 'White' }
    }
    Write-Host $line -ForegroundColor $color
}

function Write-PhaseHeader {
    param([int] $Number, [string] $Title)
    $bar = ("-" * 72)
    Write-Log "" -Level Detail
    Write-Log $bar -Level Phase
    Write-Log "  Phase $Number : $Title" -Level Phase
    Write-Log $bar -Level Phase
}

# -- Cleanup -------------------------------------------------------------------
#
# Service process handles are stored here so they can be stopped on exit.
$script:ServiceProcesses = @()

function Stop-Services {
    foreach ($proc in $script:ServiceProcesses) {
        if ($proc -and -not $proc.HasExited) {
            Write-Log "Stopping process PID $($proc.Id) ($($proc.ProcessName))..." -Level Info
            try {
                $proc.Kill()
                $proc.WaitForExit(5000) | Out-Null
                Write-Log "Process PID $($proc.Id) stopped." -Level Detail
            } catch {
                Write-Log "Could not stop PID $($proc.Id): $_" -Level Warn
            }
        }
    }
    $script:ServiceProcesses = @()
}

# Register a cleanup handler so services are always stopped when the script exits.
# Skipped in -NonInteractive mode so services outlive the script process.
if (-not $NonInteractive) {
    $null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Stop-Services }
}

# -- Health polling -------------------------------------------------------------

function Wait-ForHealth {
    <#
    .SYNOPSIS
        Polls a URL until it returns HTTP 200 or the timeout is reached.
    .OUTPUTS
        $true if the endpoint became healthy within the timeout; $false otherwise.
    #>
    param(
        [string] $Url,
        [string] $ServiceName,
        [int]    $TimeoutSeconds = $HealthTimeoutSeconds,
        [int]    $PollIntervalSeconds = 2
    )
    Write-Log "Waiting for $ServiceName to respond at $Url (timeout: ${TimeoutSeconds}s)..." -Level Info
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $attempts = 0
    while ((Get-Date) -lt $deadline) {
        $attempts++
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Log "$ServiceName is healthy (attempt $attempts, $(([math]::Round(((Get-Date) - ($deadline - [TimeSpan]::FromSeconds($TimeoutSeconds))).TotalSeconds)))s elapsed)." -Level OK
                return $true
            }
        } catch {
            # Not yet up  - keep polling.
        }
        Start-Sleep -Seconds $PollIntervalSeconds
    }
    Write-Log "$ServiceName did not respond within ${TimeoutSeconds}s after $attempts attempts." -Level Error
    return $false
}

# -- HTTP multipart file upload -------------------------------------------------

function Invoke-LedgerIngestion {
    <#
    .SYNOPSIS
        POSTs an XLSX file to POST /v1/accounts/{account}/ladder.
    .OUTPUTS
        $true on HTTP 200/201; $false on any error.
    #>
    param(
        [string] $AccountName,
        [string] $LedgerPath,
        [string] $DisplayName
    )

    if (-not (Test-Path $LedgerPath)) {
        Write-Log "  Ledger file not found: $LedgerPath" -Level Error
        return $false
    }

    $url = "$AnalysisBaseUrl/v1/accounts/$AccountName/ladder"
    Write-Log "  POST $url" -Level Detail
    Write-Log "       File: $LedgerPath" -Level Detail

    Add-Type -AssemblyName 'System.Net.Http' -ErrorAction SilentlyContinue

    $client  = $null
    $stream  = $null
    $form    = $null
    $success = $false

    try {
        $client = [System.Net.Http.HttpClient]::new()
        $client.Timeout = [TimeSpan]::FromSeconds(120)

        $form    = [System.Net.Http.MultipartFormDataContent]::new()
        $stream  = [System.IO.File]::OpenRead($LedgerPath)
        $content = [System.Net.Http.StreamContent]::new($stream)
        $content.Headers.ContentType = `
            [System.Net.Http.Headers.MediaTypeHeaderValue]::new(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        $form.Add($content, "file", [System.IO.Path]::GetFileName($LedgerPath))

        $response     = $client.PostAsync($url, $form).GetAwaiter().GetResult()
        $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $statusCode   = [int]$response.StatusCode

        if ($statusCode -eq 200) {
            $parsed = $responseBody | ConvertFrom-Json
            Write-Log "  ${DisplayName}: unchanged (checksum matched, no reprocessing)." -Level OK
            Write-Log "  Row count: $($parsed.row_count)  From: $($parsed.from_date)  To: $($parsed.to_date)" -Level Detail
            $success = $true
        } elseif ($statusCode -eq 201) {
            $parsed = $responseBody | ConvertFrom-Json
            Write-Log "  ${DisplayName}: created successfully." -Level OK
            Write-Log "  Row count: $($parsed.row_count)  From: $($parsed.from_date)  To: $($parsed.to_date)" -Level Detail
            Write-Log "  Sub-accounts: $($parsed.sub_accounts -join ', ')" -Level Detail
            $success = $true
        } elseif ($statusCode -eq 409) {
            Write-Log "  ${DisplayName}: conflict (HTTP 409). A different ledger already exists for this account." -Level Warn
            Write-Log "  Detail: $responseBody" -Level Detail
            $success = $false
        } else {
            Write-Log "  ${DisplayName}: unexpected HTTP $statusCode." -Level Error
            Write-Log "  Response: $responseBody" -Level Detail
            $success = $false
        }
    } catch {
        Write-Log "  ${DisplayName}: ingestion request failed: $_" -Level Error
        $success = $false
    } finally {
        if ($stream)  { $stream.Dispose() }
        if ($form)    { $form.Dispose() }
        if ($client)  { $client.Dispose() }
    }

    return $success
}

function Invoke-CapitalLedgerIngestion {
    <#
    .SYNOPSIS
        POSTs an XLSX file to POST /v1/accounts/{account}/capital.
    .OUTPUTS
        $true on HTTP 200/201; $false on any error.
    #>
    param(
        [string] $AccountName,
        [string] $LedgerPath,
        [string] $DisplayName
    )

    if (-not (Test-Path $LedgerPath)) {
        Write-Log "  Capital ledger file not found: $LedgerPath" -Level Error
        return $false
    }

    $url = "$AnalysisBaseUrl/v1/accounts/$AccountName/capital"
    Write-Log "  POST $url" -Level Detail
    Write-Log "       File: $LedgerPath" -Level Detail

    Add-Type -AssemblyName 'System.Net.Http' -ErrorAction SilentlyContinue

    $client  = $null
    $stream  = $null
    $form    = $null
    $success = $false

    try {
        $client = [System.Net.Http.HttpClient]::new()
        $client.Timeout = [TimeSpan]::FromSeconds(120)

        $form    = [System.Net.Http.MultipartFormDataContent]::new()
        $stream  = [System.IO.File]::OpenRead($LedgerPath)
        $content = [System.Net.Http.StreamContent]::new($stream)
        $content.Headers.ContentType = `
            [System.Net.Http.Headers.MediaTypeHeaderValue]::new(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        $form.Add($content, "file", [System.IO.Path]::GetFileName($LedgerPath))

        $response     = $client.PostAsync($url, $form).GetAwaiter().GetResult()
        $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $statusCode   = [int]$response.StatusCode

        if ($statusCode -eq 200) {
            $parsed = $responseBody | ConvertFrom-Json
            Write-Log "  ${DisplayName}: refreshed (checksum matched, ledger confirmed current)." -Level OK
            Write-Log "  Row count: $($parsed.row_count)  From: $($parsed.from_date)  To: $($parsed.to_date)" -Level Detail
            $success = $true
        } elseif ($statusCode -eq 201) {
            $parsed = $responseBody | ConvertFrom-Json
            Write-Log "  ${DisplayName}: created successfully." -Level OK
            Write-Log "  Row count: $($parsed.row_count)  From: $($parsed.from_date)  To: $($parsed.to_date)" -Level Detail
            $success = $true
        } elseif ($statusCode -eq 409) {
            Write-Log "  ${DisplayName}: conflict (HTTP 409). A different capital ledger already exists for this account." -Level Warn
            Write-Log "  Detail: $responseBody" -Level Detail
            $success = $false
        } else {
            Write-Log "  ${DisplayName}: unexpected HTTP $statusCode." -Level Error
            Write-Log "  Response: $responseBody" -Level Detail
            $success = $false
        }
    } catch {
        Write-Log "  ${DisplayName}: ingestion request failed: $_" -Level Error
        $success = $false
    } finally {
        if ($stream)  { $stream.Dispose() }
        if ($form)    { $form.Dispose() }
        if ($client)  { $client.Dispose() }
    }

    return $success
}

# -- Config helpers -------------------------------------------------------------

function Assert-ConfigYaml {
    <#
    .SYNOPSIS
        Checks that a config.yaml exists and contains expected key text.
        Writes a default version if the file is absent.
    #>
    param(
        [string]   $ServiceDir,
        [string]   $ServiceName,
        [string[]] $ExpectedKeys,
        [string]   $DefaultContent
    )
    $configPath = Join-Path $ServiceDir "config.yaml"
    if (-not (Test-Path $configPath)) {
        Write-Log "  $ServiceName config.yaml not found  - writing defaults." -Level Warn
        $DefaultContent | Out-File -FilePath $configPath -Encoding utf8 -NoNewline
        Write-Log "  Wrote: $configPath" -Level Detail
        return
    }
    $text = Get-Content $configPath -Raw
    foreach ($key in $ExpectedKeys) {
        if ($text -notmatch [regex]::Escape($key)) {
            Write-Log "  $ServiceName config.yaml is missing expected key '$key'  - file may need manual review." -Level Warn
        }
    }
    Write-Log "  $ServiceName config.yaml OK: $configPath" -Level OK
}

# -----------------------------------------------------------------------------
#  MAIN
# -----------------------------------------------------------------------------

Initialize-Log

$OverallSuccess = $true

# =============================================================================
#  Phase 1  - Account Preparation Pipeline
# =============================================================================

Write-PhaseHeader 1 "Account Preparation Pipeline"

if ($SkipPipeline) {
    Write-Log "  -SkipPipeline flag set  - skipping Phase 1." -Level Warn
} else {
    $pipelineScript = Join-Path $PipelineDir "run_pipeline.ps1"

    if (-not (Test-Path $pipelineScript)) {
        Write-Log "Pipeline script not found: $pipelineScript" -Level Error
        Stop-Services
        exit 1
    }
    if (-not (Test-Path $PipelinePython)) {
        Write-Log "Pipeline venv not found: $PipelinePython" -Level Error
        Write-Log "Run: cd AccountPreparationPipeline && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt" -Level Detail
        Stop-Services
        exit 1
    }

    Write-Log "  Executing: $pipelineScript" -Level Info
    Write-Log "  (All pipeline output is written to console and captured below)" -Level Detail
    Write-Log "" -Level Detail

    # Run inline  - output flows directly to console and is already visible.
    & $pipelineScript
    $pipelineExit = $LASTEXITCODE

    Write-Log "" -Level Detail
    if ($pipelineExit -ne 0) {
        Write-Log "AccountPreparationPipeline exited with code $pipelineExit." -Level Error
        $OverallSuccess = $false
        Stop-Services
        exit 1
    }
    Write-Log "AccountPreparationPipeline completed successfully." -Level OK
}

# Verify the ledger files that will be ingested actually exist.
Write-Log "  Verifying sub-account ledger files..." -Level Info
foreach ($ledger in $SubAccountLedgers) {
    if (Test-Path $ledger.LedgerPath) {
        Write-Log "  [FOUND] $($ledger.DisplayName): $($ledger.LedgerPath)" -Level OK
    } else {
        Write-Log "  [MISSING] $($ledger.DisplayName): $($ledger.LedgerPath)" -Level Warn
        Write-Log "  This ledger will be skipped during ingestion (Phase 5)." -Level Detail
    }
}

Write-Log "  Verifying capital ledger files..." -Level Info
foreach ($ledger in $CapitalLedgers) {
    if (Test-Path $ledger.LedgerPath) {
        Write-Log "  [FOUND] $($ledger.DisplayName): $($ledger.LedgerPath)" -Level OK
    } else {
        Write-Log "  [MISSING] $($ledger.DisplayName): $($ledger.LedgerPath)" -Level Warn
        Write-Log "  This capital ledger will be skipped during ingestion (Phase 6)." -Level Detail
    }
}

# =============================================================================
#  Phase 2  - Service Configuration
# =============================================================================

Write-PhaseHeader 2 "Service Configuration"

Write-Log "  Port assignments:" -Level Info
Write-Log "    market-data-web-service  -> http://${MarketDataHost}:${MarketDataPort}" -Level Detail
Write-Log "    portfolio-analysis-service -> http://${AnalysisHost}:${AnalysisPort}" -Level Detail
Write-Log "" -Level Detail
Write-Log "  Note: port is passed directly to uvicorn at startup  - it is NOT" -Level Detail
Write-Log "  read from config.yaml. Change MarketDataPort / AnalysisPort at the" -Level Detail
Write-Log "  top of this script if a different port is required." -Level Detail

# -- market-data-web-service ---------------------------------------------------
Write-Log "" -Level Detail
Write-Log "  Checking market-data-web-service config..." -Level Info

$mdwsDefaultConfig = @"
cache:
  directory: ./cache
fallback:
  config_path: ./data/fallback_config.json
"@

Assert-ConfigYaml `
    -ServiceDir   $MarketDataDir `
    -ServiceName  "market-data-web-service" `
    -ExpectedKeys @("cache:", "directory:") `
    -DefaultContent $mdwsDefaultConfig

Write-Log "  Cache directory : $(Join-Path $MarketDataDir 'cache')  (relative: ./cache)" -Level Detail
Write-Log "  This is distinct from portfolio-analysis-service's data/ directory." -Level Detail

# -- portfolio-analysis-service ------------------------------------------------
Write-Log "" -Level Detail
Write-Log "  Checking portfolio-analysis-service config..." -Level Info

# The market_data_service and identifier_mapping sections wire portfolio-analysis-service
# to the market-data-web-service instance this same script starts (Phase 3 below) and to
# the sub-account-to-identifier mapping file used to resolve prices.
$analysisDefaultConfig = @"
data:
  directory: ./data

market_data_service:
  base_url: http://${MarketDataHost}:${MarketDataPort}
  timeout_seconds: 30

identifier_mapping:
  path: $(Join-Path $InvestmentsDir "InvestmentDataStatic.json")
"@

Assert-ConfigYaml `
    -ServiceDir   $AnalysisDir `
    -ServiceName  "portfolio-analysis-service" `
    -ExpectedKeys @("data:", "directory:", "market_data_service:", "identifier_mapping:") `
    -DefaultContent $analysisDefaultConfig

Write-Log "  Data directory  : $(Join-Path $AnalysisDir 'data')  (relative: ./data)" -Level Detail
Write-Log "  Market-data URL : http://${MarketDataHost}:${MarketDataPort}" -Level Detail
Write-Log "  Identifier mapping file: $(Join-Path $InvestmentsDir 'InvestmentDataStatic.json')" -Level Detail

# =============================================================================
#  Phase 3  - Start market-data-web-service
# =============================================================================

Write-PhaseHeader 3 "Start market-data-web-service"

if (-not (Test-Path $MarketDataUvicorn)) {
    Write-Log "uvicorn not found in market-data-web-service venv: $MarketDataUvicorn" -Level Error
    Write-Log "Run: cd market-data-web-service && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt" -Level Detail
    Stop-Services
    exit 1
}

# Service log files (stdout and stderr are redirected so the parent console
# stays readable; logs are appended to the same logs/ directory).
$mdwsStdout = Join-Path $LogDir "market-data-svc.stdout.log"
$mdwsStderr = Join-Path $LogDir "market-data-svc.stderr.log"

Write-Log "  Launching: uvicorn app.main:app --host $MarketDataHost --port $MarketDataPort" -Level Info
Write-Log "  Working dir : $MarketDataDir" -Level Detail
Write-Log "  stdout log  : $mdwsStdout" -Level Detail
Write-Log "  stderr log  : $mdwsStderr" -Level Detail

$mdwsProc = Start-Process `
    -FilePath         $MarketDataUvicorn `
    -ArgumentList     "app.main:app", "--host", $MarketDataHost, "--port", $MarketDataPort `
    -WorkingDirectory $MarketDataDir `
    -PassThru `
    -NoNewWindow `
    -RedirectStandardOutput $mdwsStdout `
    -RedirectStandardError  $mdwsStderr

$script:ServiceProcesses += $mdwsProc
Write-Log "  market-data-web-service started (PID $($mdwsProc.Id))." -Level OK

$mdwsHealthy = Wait-ForHealth `
    -Url         $MarketDataHealthUrl `
    -ServiceName "market-data-web-service"

if (-not $mdwsHealthy) {
    Write-Log "market-data-web-service did not become healthy. Check: $mdwsStderr" -Level Error
    Stop-Services
    exit 1
}

# =============================================================================
#  Phase 4  - Start portfolio-analysis-service
# =============================================================================

Write-PhaseHeader 4 "Start portfolio-analysis-service"

if (-not (Test-Path $AnalysisUvicorn)) {
    Write-Log "uvicorn not found in portfolio-analysis-service venv: $AnalysisUvicorn" -Level Error
    Write-Log "Run: cd portfolio-analysis-service && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt" -Level Detail
    Stop-Services
    exit 1
}

$analysisStdout = Join-Path $LogDir "portfolio-analysis-svc.stdout.log"
$analysisStderr = Join-Path $LogDir "portfolio-analysis-svc.stderr.log"

Write-Log "  Launching: uvicorn app.main:app --host $AnalysisHost --port $AnalysisPort" -Level Info
Write-Log "  Working dir : $AnalysisDir" -Level Detail
Write-Log "  stdout log  : $analysisStdout" -Level Detail
Write-Log "  stderr log  : $analysisStderr" -Level Detail

$analysisProc = Start-Process `
    -FilePath         $AnalysisUvicorn `
    -ArgumentList     "app.main:app", "--host", $AnalysisHost, "--port", $AnalysisPort `
    -WorkingDirectory $AnalysisDir `
    -PassThru `
    -NoNewWindow `
    -RedirectStandardOutput $analysisStdout `
    -RedirectStandardError  $analysisStderr

$script:ServiceProcesses += $analysisProc
Write-Log "  portfolio-analysis-service started (PID $($analysisProc.Id))." -Level OK

$analysisHealthy = Wait-ForHealth `
    -Url         $AnalysisHealthUrl `
    -ServiceName "portfolio-analysis-service"

if (-not $analysisHealthy) {
    Write-Log "portfolio-analysis-service did not become healthy. Check: $analysisStderr" -Level Error
    Stop-Services
    exit 1
}

# =============================================================================
#  Phase 5  - Ingest sub-account ledgers
# =============================================================================

Write-PhaseHeader 5 "Ingest Sub-Account Ledgers"

Write-Log "  Ingesting $($SubAccountLedgers.Count) ledger(s) into portfolio-analysis-service..." -Level Info

$ingestSuccessCount = 0
$ingestFailCount    = 0

foreach ($ledger in $SubAccountLedgers) {
    Write-Log "" -Level Detail
    Write-Log "  -- $($ledger.DisplayName) -----------------------------" -Level Info
    Write-Log "     Account : $($ledger.AccountName)" -Level Detail
    Write-Log "     File    : $($ledger.LedgerPath)" -Level Detail

    if (-not (Test-Path $ledger.LedgerPath)) {
        Write-Log "  Ledger file does not exist  - skipping." -Level Warn
        $ingestFailCount++
        continue
    }

    $ok = Invoke-LedgerIngestion `
        -AccountName $ledger.AccountName `
        -LedgerPath  $ledger.LedgerPath `
        -DisplayName $ledger.DisplayName

    if ($ok) {
        $ingestSuccessCount++
        Write-Log "  Download: $AnalysisBaseUrl/v1/accounts/$($ledger.AccountName)/ladder/download" -Level Detail
    } else {
        $ingestFailCount++
        $OverallSuccess = $false
    }
}

Write-Log "" -Level Detail
Write-Log "  Ingestion summary: $ingestSuccessCount succeeded, $ingestFailCount failed." -Level Info

# =============================================================================
#  Phase 6  - Ingest capital ledgers
# =============================================================================

Write-PhaseHeader 6 "Ingest Capital Ledgers"

Write-Log "  Ingesting $($CapitalLedgers.Count) capital ledger(s) into portfolio-analysis-service..." -Level Info

$capitalSuccessCount = 0
$capitalFailCount    = 0

foreach ($ledger in $CapitalLedgers) {
    Write-Log "" -Level Detail
    Write-Log "  -- $($ledger.DisplayName) -----------------------------" -Level Info
    Write-Log "     Account : $($ledger.AccountName)" -Level Detail
    Write-Log "     File    : $($ledger.LedgerPath)" -Level Detail

    if (-not (Test-Path $ledger.LedgerPath)) {
        Write-Log "  Capital ledger file does not exist  - skipping." -Level Warn
        $capitalFailCount++
        continue
    }

    $ok = Invoke-CapitalLedgerIngestion `
        -AccountName $ledger.AccountName `
        -LedgerPath  $ledger.LedgerPath `
        -DisplayName $ledger.DisplayName

    if ($ok) {
        $capitalSuccessCount++
        Write-Log "  Download: $AnalysisBaseUrl/v1/accounts/$($ledger.AccountName)/capital/download" -Level Detail
    } else {
        $capitalFailCount++
        $OverallSuccess = $false
    }
}

Write-Log "" -Level Detail
Write-Log "  Capital ledger ingestion summary: $capitalSuccessCount succeeded, $capitalFailCount failed." -Level Info

# =============================================================================
#  Phase 7  - Start Investment Portfolio Browser (Dash app)
# =============================================================================

Write-PhaseHeader 7 "Start Investment Portfolio Browser"

if (-not (Test-Path $DashAppPython)) {
    Write-Log "Python not found in portfolio-browser venv: $DashAppPython" -Level Error
    Write-Log "Run: cd portfolio-browser && python -m venv .venv && .venv\Scripts\pip install -e `".[dev]`"" -Level Detail
    Stop-Services
    exit 1
}

$dashStdout = Join-Path $LogDir "portfolio-browser.stdout.log"
$dashStderr = Join-Path $LogDir "portfolio-browser.stderr.log"

Write-Log "  Configuring Dash app to read from:" -Level Info
Write-Log "    market-data-web-service    -> $MarketDataBaseUrl" -Level Detail
Write-Log "    portfolio-analysis-service -> $AnalysisBaseUrl" -Level Detail

# Passed to the child process via environment variables (pydantic-settings
# reads these; env vars take precedence over any .env file in the app's
# working directory). DEBUG is forced off so Dash/Werkzeug does not spawn a
# reloader subprocess  - that would leave an orphan behind $dashProc.Kill().
$env:HOST                          = $DashAppHost
$env:PORT                          = "$DashPort"
$env:DEBUG                         = "false"
$env:MARKET_DATA_SERVICE_URL       = $MarketDataBaseUrl
$env:PORTFOLIO_ANALYSIS_SERVICE_URL = $AnalysisBaseUrl

Write-Log "  Launching: python app.py" -Level Info
Write-Log "  Working dir : $DashAppDir" -Level Detail
Write-Log "  stdout log  : $dashStdout" -Level Detail
Write-Log "  stderr log  : $dashStderr" -Level Detail

$dashProc = Start-Process `
    -FilePath         $DashAppPython `
    -ArgumentList     "app.py" `
    -WorkingDirectory $DashAppDir `
    -PassThru `
    -NoNewWindow `
    -RedirectStandardOutput $dashStdout `
    -RedirectStandardError  $dashStderr

$script:ServiceProcesses += $dashProc
Write-Log "  Investment Portfolio Browser started (PID $($dashProc.Id))." -Level OK

$dashHealthy = Wait-ForHealth `
    -Url         $DashAppHealthUrl `
    -ServiceName "Investment Portfolio Browser"

if (-not $dashHealthy) {
    Write-Log "Investment Portfolio Browser did not become healthy. Check: $dashStderr" -Level Error
    $OverallSuccess = $false
} else {
    Write-Log "  Opening $DashAppUrl in the default browser..." -Level Info
    try {
        Start-Process $DashAppUrl
        Write-Log "  Browser launch requested." -Level OK
    } catch {
        Write-Log "  Could not open the default browser automatically: $_" -Level Warn
        Write-Log "  Open it manually: $DashAppUrl" -Level Detail
    }
}

# =============================================================================
#  Final Summary
# =============================================================================

Write-Log "" -Level Detail
Write-Log ("=" * 72) -Level Phase

if ($OverallSuccess) {
    Write-Log "  END-TO-END RUN COMPLETED SUCCESSFULLY" -Level OK
} else {
    Write-Log "  END-TO-END RUN COMPLETED WITH ERRORS (see above)" -Level Warn
}

Write-Log ("=" * 72) -Level Phase
Write-Log "" -Level Detail
Write-Log "  Services are still running in the background:" -Level Info
Write-Log "    market-data-web-service       PID $($mdwsProc.Id)  http://${MarketDataHost}:${MarketDataPort}/docs" -Level Detail
Write-Log "    portfolio-analysis-service    PID $($analysisProc.Id)  http://${AnalysisHost}:${AnalysisPort}/docs" -Level Detail
Write-Log "    Investment Portfolio Browser  PID $($dashProc.Id)  $DashAppUrl" -Level Detail
Write-Log "" -Level Detail
Write-Log "  To stop services, press Ctrl+C or kill the PIDs above." -Level Detail
Write-Log "  Log file: $LogFile" -Level Detail
Write-Log ("=" * 72) -Level Phase

if ($NonInteractive) {
    Write-Log "  Running non-interactively  - services continue in background (PIDs above)." -Level Info
    Write-Log "  Stop them with: Stop-Process -Id <PID> -Force" -Level Detail
    if ($OverallSuccess) { exit 0 } else { exit 1 }
} else {
    # Keep the script alive so the user can interact with the running services
    # (including the Dash app opened in their browser above). Press any key
    # (or Ctrl+C) to trigger the Exit handler and stop all three processes.
    Write-Log "" -Level Detail
    Write-Host ""
    Write-Host "  Press any key to stop all services and exit..." -ForegroundColor DarkCyan
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    Stop-Services
    if ($OverallSuccess) { exit 0 } else { exit 1 }
}
