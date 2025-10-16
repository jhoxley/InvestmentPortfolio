# .\.venv\Scripts\Python .\PortfolioAnalysis.py DailySummary data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\ProcessedDailySummary_New.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py MonthlySummary data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\ProcessedMonthlySummary_New.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py QuarterlySummary data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\ProcessedQuarterlySummary_New.xlsx"v
# .\.venv\Scripts\Python .\PortfolioAnalysis.py AnnualSummary data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\ProcessedQuarterlySummary_New.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py DailyDetails data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\ProcessedDailyInvestmentData_New.xlsx"
# .\.venv\Scripts\Python .\PortfolioAnalysis.py All data_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentData.xlsx" static_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentDataStatic.json" transactions_sheet="Transactions" income_sheet="Income" output_file="C:\Users\jhoxl\OneDrive\Investments\InvestmentIsa.xlsx"

import sys
import yfinance as yf
import datetime as dt
import AnalysisFuncs as af
import DataFormatting
import DataGeneration as dg
from Reports import DailyDetails, MonthlySummary, QuarterlySummary, DailySummary, MultiReport, AnnualSummary
import pandas as pd
from Data import MarketData
import json

report_types = {
    "DailyDetails": DailyDetails.DailyDetailsReport(),
    "MonthlySummary": MonthlySummary.MonthlySummaryReport(),
    "QuarterlySummary": QuarterlySummary.QuarterlySummaryReport(),
    "AnnualSummary": AnnualSummary.AnnualSummaryReport(),
    "DailySummary": DailySummary.DailySummaryReport(),
    "All" : MultiReport.MultiReport([
        DailyDetails.DailyDetailsReport(),
        MonthlySummary.MonthlySummaryReport(),
        QuarterlySummary.QuarterlySummaryReport(),
        AnnualSummary.AnnualSummaryReport(),
        DailySummary.DailySummaryReport()
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

print(f"Selected report: {report.get_report_name()}")

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

mdApi = MarketData.MarketDataApi()

for position in distinct_positions:
    static = position_lookup.get(position, {})
    ident = static.get("isin", "")
    ticker = yf.Ticker(ident).info.get('symbol', 'N/A') if ident else 'N/A'
    
    print(f"Processing... Name: {position}, Isin: {ident}, Ticker: {ticker}")
    df2 = df[df['Position Name'] == position]

    df3 = af.cumulative_by_settle_date(df2)
    df3['Position Name'] = position
    df3['ISIN']= ident
    df3['Ticker'] = ticker
    
    positionFirstTran = pd.to_datetime(df3['Settle date']).min()
    positionLastTran = pd.to_datetime(df3['Settle date']).max()
    if df3['Cm.Qty'].iloc[-1] != 0:
        positionLastTran = dt.datetime.today().date() - pd.tseries.offsets.BDay(1)

    ds = dg.create_date_series(positionFirstTran, positionLastTran)

    # Fugly hack to handle cash positions, should be removed when we have a better way to handle cash
    if ticker == 'N/A' and ident == "GBP=":
        ts = pd.DataFrame(ds)
        ts['Close'] = 1.0  # Assuming cash has a constant value of 1.0
    else:
        multiplier = static.get("multiplier", 1.0)
        ts = mdApi.get_time_series(positionFirstTran, positionLastTran, ticker, multiplier)    

    transactions = df[df['Position Name'] == position][['Settle date', 'Reference', 'Adj Qty', 'Value (£)']].rename(columns={'Adj Qty': 'Quantity'})
    transactions['Value (£)'] = transactions['Value (£)'].abs()

    income = dfIncome[dfIncome['Position Name'] == position][['Settle date', 'Quantity', 'Value (£)']]

    PositionDf = DataFormatting.create_holding_dataframe(
        transactions,
        income,
        ds,
        ts,
        position
    )

    frames.append(PositionDf)

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

# Run the report
print("Generating report, saving to " + output_file)
report.generate(output_file, final_df)