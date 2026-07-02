<#
.SYNOPSIS
    Runs the account preparation pipeline for all configured accounts.

.DESCRIPTION
    For each account: consolidates HL CSV journal fragments into a single XLSX,
    then builds a ledger from that journal.

    To add a new account: append a hashtable to $Accounts below.
    To add a new pipeline step: extend the numbered step sequence in the loop body.
#>

# ── Configuration ─────────────────────────────────────────────────────────────

$InvestmentsDir = "C:\Users\jhoxl\OneDrive\Investments"
$JournalsDir    = Join-Path $InvestmentsDir "Journals"

# Each hashtable defines one account's inputs, intermediaries, and outputs.
# Keys:
#   Name               — display label used in console output
#   AccountLabel       — string written into every journal row's 'account' column
#   Method             — consolidation parser (currently only "HL" is supported)
#   FragmentsDir       — directory containing the raw HL CSV export files
#   JournalPath        — consolidated journal XLSX (created or updated by Step 1)
#   LedgerPath         — ledger XLSX produced by Step 2
#   IsCapitalAccount   — $true to run Step 3 (create_capital_ledger); omit/false for income accounts
#   CapitalLedgerPath  — capital summary XLSX produced by Step 3 (required when IsCapitalAccount=$true)

$Accounts = @(
    @{
        Name               = "HL SIPP"
        AccountLabel       = "HL Group SIPP"
        Method             = "HL"
        FragmentsDir       = Join-Path $JournalsDir "HL Group Sipp - Capital Account"
        JournalPath        = Join-Path $JournalsDir "HL_SIPP_Journal.xlsx"
        LedgerPath         = Join-Path $InvestmentsDir "HL_SIPP_Ledger.xlsx"
        IsCapitalAccount   = $true
        CapitalLedgerPath  = Join-Path $InvestmentsDir "HL_SIPP_Capital_Ledger.xlsx"
    }
    @{
        Name               = "HL SIPP Income"
        AccountLabel       = "HL Group SIPP Income"
        Method             = "HL"
        FragmentsDir       = Join-Path $JournalsDir "HL Group Sipp - Income Account"
        JournalPath        = Join-Path $JournalsDir "HL_SIPP_Income_Journal.xlsx"
        LedgerPath         = Join-Path $InvestmentsDir "HL_SIPP_Income_Ledger.xlsx"
        IsCapitalAccount   = $false
    }
    @{
        Name               = "HL ISA"
        AccountLabel       = "HL Stocks and Shares ISA"
        Method             = "HL"
        FragmentsDir       = Join-Path $JournalsDir "HL Stocks and Shares ISA - Capital Account"
        JournalPath        = Join-Path $JournalsDir "HL_ISA_Journal.xlsx"
        LedgerPath         = Join-Path $InvestmentsDir "HL_ISA_Ledger.xlsx"
        IsCapitalAccount   = $true
        CapitalLedgerPath  = Join-Path $InvestmentsDir "HL_ISA_Capital_Ledger.xlsx"
    }
    @{
        Name               = "HL ISA Income"
        AccountLabel       = "HL Stocks and Shares ISA Income"
        Method             = "HL"
        FragmentsDir       = Join-Path $JournalsDir "HL Stocks and Shares ISA - Income Account"
        JournalPath        = Join-Path $JournalsDir "HL_ISA_Income_Journal.xlsx"
        LedgerPath         = Join-Path $InvestmentsDir "HL_ISA_Income_Ledger.xlsx"
        IsCapitalAccount   = $false
    }
)

# ── Runtime paths ─────────────────────────────────────────────────────────────

$PythonExe  = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$PipelinePy = Join-Path $PSScriptRoot "pipeline.py"

# ── Execution ─────────────────────────────────────────────────────────────────

$OverallSuccess = $true

foreach ($account in $Accounts) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor DarkCyan
    Write-Host "  $($account.Name)" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor DarkCyan

    $failed = $false

    # ── Step 1: Consolidate HL journal fragments ───────────────────────────────
    if (-not $failed) {
        Write-Host ""
        Write-Host "  [1/2] consolidate_journals" -ForegroundColor Yellow
        Write-Host "        $($account.FragmentsDir)"
        Write-Host "     -> $($account.JournalPath)"
        & $PythonExe $PipelinePy consolidate_journals `
            $account.JournalPath `
            $account.FragmentsDir `
            $account.Method `
            $account.AccountLabel
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  FAILED: consolidate_journals exited with code $LASTEXITCODE" -ForegroundColor Red
            $failed = $true
        }
    }

    # ── Step 2: Build ledger from consolidated journal ─────────────────────────
    if (-not $failed) {
        Write-Host ""
        Write-Host "  [2/2] create_ledger" -ForegroundColor Yellow
        Write-Host "        $($account.JournalPath)"
        Write-Host "     -> $($account.LedgerPath)"
        & $PythonExe $PipelinePy create_ledger `
            $account.JournalPath `
            $account.LedgerPath
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  FAILED: create_ledger exited with code $LASTEXITCODE" -ForegroundColor Red
            $failed = $true
        }
    }

    # ── Step 3: Build capital summary from ledger ──────────────────────────────
    if (-not $failed -and $account.IsCapitalAccount -eq $true) {
        Write-Host ""
        Write-Host "  [3/3] create_capital_ledger" -ForegroundColor Yellow
        Write-Host "        $($account.LedgerPath)"
        Write-Host "     -> $($account.CapitalLedgerPath)"
        & $PythonExe $PipelinePy create_capital_ledger `
            $account.LedgerPath `
            $account.CapitalLedgerPath
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  FAILED: create_capital_ledger exited with code $LASTEXITCODE" -ForegroundColor Red
            $failed = $true
        }
    }

    Write-Host ""
    if ($failed) {
        Write-Host "  $($account.Name): FAILED" -ForegroundColor Red
        $OverallSuccess = $false
    } else {
        Write-Host "  $($account.Name): OK" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor DarkCyan
if ($OverallSuccess) {
    Write-Host "  All accounts processed successfully." -ForegroundColor Green
    exit 0
} else {
    Write-Host "  One or more accounts failed - see output above." -ForegroundColor Red
    exit 1
}
