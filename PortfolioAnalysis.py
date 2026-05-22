# .\.venv\Scripts\Python .\PortfolioAnalysis.py DailySummary data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\ProcessedDailySummary_New.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py MonthlySummary data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\ProcessedMonthlySummary_New.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py QuarterlySummary data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\ProcessedQuarterlySummary_New.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py AnnualSummary data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\ProcessedQuarterlySummary_New.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py DailyDetails data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentISA_DailyDetails.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py Projected data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\ProcessedProjectedInvestmentData_New.xlsx" fwd_periods=1095
# .\.venv\Scripts\Python .\PortfolioAnalysis.py All data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentIsa.xlsx" fwd_periods=1095 periodicity="QE"

# .\.venv\Scripts\Python .\PortfolioAnalysis.py DailyDetails data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="SIPP-Trans" income_sheet="SIPP-Income" output_file="C:\Users\jhoxl\OneDrive\Investments\SIPP_DailyDetails.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py DailySummary data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="SIPP-Trans" income_sheet="SIPP-Income" output_file="C:\Users\jhoxl\OneDrive\Investments\SIPP_DailySummary.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py All data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="SIPP-Trans" income_sheet="SIPP-Income" output_file="C:\Users\jhoxl\OneDrive\Investments\SIPP\SIPP.xlsx" fwd_periods=3650 periodicity="ME"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py Projected data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="SIPP-Trans" income_sheet="SIPP-Income" output_file="C:\Users\jhoxl\OneDrive\Investments\SIPP.xlsx" fwd_periods=3650 periodicity="QE"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py Current data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="SIPP-Trans" income_sheet="SIPP-Income" output_file="C:\Users\jhoxl\OneDrive\Investments\SIPP_Holdings.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py Performance data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="SIPP-Trans" income_sheet="SIPP-Income" output_file="C:\Users\jhoxl\OneDrive\Investments\SIPP_Holdings.xlsx"

import sys
import datetime as dt
import AnalysisFuncs as af
import DataFormatting
import DataGeneration as dg
from Reports import DailyDetails, MonthlySummary, QuarterlySummary, DailySummary, MultiReport, AnnualSummary,ForwardProjection,CurrentHoldings,PeriodicPerformance
import pandas as pd
from Data.MarketDataClient import MarketDataClient
import json

report_types = {
    "DailyDetails": DailyDetails.DailyDetailsReport(),
    "MonthlySummary": MonthlySummary.MonthlySummaryReport(),
    "QuarterlySummary": QuarterlySummary.QuarterlySummaryReport(),
    "AnnualSummary": AnnualSummary.AnnualSummaryReport(),
    "DailySummary": DailySummary.DailySummaryReport(),
    "Projected" : ForwardProjection.ForwardProjectionReport(),
    "Current" : CurrentHoldings.CurrentHoldingsReport(),
    "Performance" : PeriodicPerformance.PeriodicPerformanceReport(),
    "All" : MultiReport.MultiReport([
        DailyDetails.DailyDetailsReport(),
        MonthlySummary.MonthlySummaryReport(),
        QuarterlySummary.QuarterlySummaryReport(),
        AnnualSummary.AnnualSummaryReport(),
        DailySummary.DailySummaryReport(),
        ForwardProjection.ForwardProjectionReport(),
        CurrentHoldings.CurrentHoldingsReport(),
        PeriodicPerformance.PeriodicPerformanceReport()
    ])
}

# select the type of report to use by inspecting the command line arguments
report=None
if len(sys.argv) > 1 and sys.argv[1] in report_types:   
    report = report_types[sys.argv[1]]

if report is None:
    print("Please specify a valid report type as the first argument:")
    print("Options are: " + ", ".join(report_types.keys()))
    sys.exit(1)

print(f"Selected report: {report.report_name()}")

# extract params
kv_args = sys.argv[2:]  # Skip script name and first argument
params = dict(arg.split('=', 1) for arg in kv_args if '=' in arg)
print(f"Parameters: {params}")

# decode params
data_file = params.get('data_file')
static_file = params.get('static_file')
trans_sheet = params.get('transactions_sheet', 'Transactions')
income_sheet = params.get('income_sheet', 'Income')
output_file = params.get('output_file', 'output.csv')
api_url = params.get('api_url', 'http://localhost:8000')

df = pd.read_excel(data_file, sheet_name=trans_sheet)
dfIncome = pd.read_excel(data_file, sheet_name=income_sheet)

if static_file is None:
    print("Error: static_file parameter is required.")
    sys.exit(1)

with open(static_file, 'r') as f:
    static_data = json.load(f)
position_lookup = {item["name"]: item for item in static_data}

# get distinct values from the 'Position Name' column except for values equal to "Cash"
distinct_positions = df['Position Name'].unique()
frames = []
market_data_errors = []

client = MarketDataClient(api_url)

for position in distinct_positions:
    static = position_lookup.get(position, {})
    if static.get("ignore", False):
        print(f"Skipping ignored position: {position}")
        continue
    print(' ')
    print('================================')
    print(f"Processing... Name: {position}, Isin: {static.get('isin','')}, Ticker: {static.get('ticker','')}")

    if static.get("ticker"):
        ticker = static.get("ticker")
    else:
        ident = static.get("isin", "")
        if ident:
            resolved = client.resolve_ticker(ident)
            if resolved is not None:
                ticker = resolved
                print(f"   Translated {ident} to ticker {ticker}")
            else:
                ticker = ident  # use identifier directly (e.g. FX tickers like GBP=)
                print(f"   Could not resolve {ident} via identifier service, using as ticker directly")
        else:
            ticker = "N/A"

    identifier = static.get("isin") or static.get("ticker") or "N/A"

    df2 = df[df['Position Name'] == position]

    df3 = af.cumulative_by_settle_date(df2)
    df3['Position Name'] = position
    df3['ISIN']= static.get("isin", "")
    df3['Ticker'] = ticker

    positionFirstTran = pd.to_datetime(df3['Settle date']).min()
    positionLastTran = pd.to_datetime(df3['Settle date']).max()
    if df3['Cm.Qty'].iloc[-1] != 0:
        positionLastTran = dt.datetime.today().date() - pd.tseries.offsets.BDay(2) # assume data is up to 2 business days old in YFinance API

    ds = dg.create_date_series(positionFirstTran, positionLastTran)

    # hack for new positions where we dont get the 2BD history yet
    if positionFirstTran > dt.datetime.today().date() - pd.tseries.offsets.BDay(2):
        print(f"   Skipping inclusion of new position '{position}' with insufficient history. Need at least 2 business days of history, looking for data from {positionFirstTran}.")
        continue

    try:
        multiplier = static.get("multiplier", 1.0)
        if ticker == "N/A" and position.lower() == "cash":
            ts = ds[["Settle date"]].copy()
            ts["Close"] = 1.0
        else:
            ts = client.get_price_history(ticker, positionFirstTran, positionLastTran, multiplier)
            if ts is None:
                print(f"   WARNING: No market data returned for '{position}' (ticker: {ticker}). Skipping.")
                market_data_errors.append({"Position": position, "Identifier": identifier, "Ticker": ticker, "Error Code": "404", "Message": "No market data found"})
                continue

        transactions = df[df['Position Name'] == position][['Settle date', 'Reference', 'Adj Qty', 'Value (£)']].rename(columns={'Adj Qty': 'Quantity'})
        transactions['Value (£)'] = transactions['Value (£)'].abs()

        income = dfIncome[dfIncome['Position Name'] == position][['Settle date', 'Quantity', 'Value (£)']]

        theme = static.get("theme", "n/a")

        PositionDf = DataFormatting.create_holding_dataframe(
            transactions,
            income,
            ds,
            ts,
            position,
            theme
        )

        frames.append(PositionDf)

    except RuntimeError as exc:
        print(f"   WARNING: Market data service error for '{position}' (ticker: {ticker}): {exc}. Skipping.")
        market_data_errors.append({"Position": position, "Identifier": identifier, "Ticker": ticker, "Error Code": "ERROR", "Message": str(exc)})
        continue

if market_data_errors:
    print(' ')
    print('================================')
    print(f"MARKET DATA ERRORS — {len(market_data_errors)} position(s) excluded from report:")
    error_df = pd.DataFrame(market_data_errors)
    print(error_df.to_string(index=False))
    print('================================')

# Concatenate all dataframes in the list into a single dataframe
print("Generating final dataframe...")
final_df = DataFormatting.create_portfolio(frames)

# Expected schema:
# 'Settle date', 'Position name', 'Capital', 'Quantity', 'Book cost', 'Close', 'Market value', 'Income'

# Interrogate the report to see what measures it needs
print("Report requires the following measures: " + ", ".join(report.required_measures()))

if "Daily Return %" in report.required_measures():
    print("Calculating 'Daily Return %'...")
    final_df = af.calculate_daily_returns(final_df, False)

if "Weight %" in report.required_measures():
    print("Calculating 'Weight %'...")
    final_df = af.calculate_position_weights(final_df)

if "ITD PnL" in report.required_measures():
    print("Calculating 'ITD PnL'...")
    final_df = af.calculate_itd_pnl(final_df)

# Check that we've populated the required measures
missing_measures = [measure for measure in report.required_measures() if measure not in final_df.columns]
if missing_measures:
    print(f"Error: The following required measures are missing from the data: {', '.join(missing_measures)}")
    sys.exit(1)

# Determine params passed into report
report_args = {key : params[key] for key in params if key not in ['data_file', 'static_file', 'transactions_sheet', 'income_sheet', 'output_file', 'api_url']}

# Run the report
print("Generating report, saving to " + output_file)
report.generate(output_file, final_df, report_args)