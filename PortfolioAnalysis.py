import yfinance as yf
import datetime as dt
import AnalysisFuncs as af
import DataFormatting
import DataGeneration as dg
# Fetch historical data for a stock (e.g., Apple)


# Use yfinance to look up a ticker from an isin
#ticker = yf.Ticker("GB00BV8VN462")
# Print the ticker information  
#print(ticker.info)
# Print the historical market data
#print(ticker.history(period="5d"))


#data = yf.download(ticker.info["symbol"], start="2025-01-01", end="2025-06-16")
#print(data)






def get_time_series(start_date, end_date, ticker, pxmultiplier=1.0):
    # Fetch historical data for the ticker
    if ticker == 'N/A':
        return pd.DataFrame({'Settle date': pd.date_range(start=start_date, end=end_date, freq='B'), 'Close': 0})
    
    try:
        data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)
        d2 = data[('Close', ticker)]
        d3data = {'Settle date': d2.index.values, 'Close': d2.values}
        d3 = pd.DataFrame(d3data)
        d3['Close'] = d3['Close'] * pxmultiplier
        return d3
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame({'Settle date': pd.date_range(start=start_date, end=end_date, freq='B'), 'Close': 0})



# create our reference dictionary:
position_identifiers = {
    "HSBC FTSE 250 Index Class S - Income (GBP)":                                   "GB00BV8VN462",
    "Barclays plc Ordinary 25p" :                                                   "GB0031348658",
    "iShares II plc USD TIPS UCITS ETF USD (Acc)" :                                 "ITPS.L",
    "iShares II plc GBP Index-Linked Gilts UCITS ETF Dist" :                        "INXG.L",
    "Man Group Ordinary 3 3/7 US cents" :                                           "",
    "Man Group plc ORD USD0.0342857142" :                                           "JE00BJ1DLW90",
    "iShares V plc S&P 500 Information Technology Sector UCITS ETF" :               "IITU.L",
    "Legal & General Global Technology Index Trust Class C - Accumulation (GBP)" :  "GB00BJLP1W53",
    "Lindsell Train Global Equity Class B - Accumulation (GBP)" :                   "IE00051RD3C4",
    "Xtrackers Stoxx Europe 600 UCITS ETF (DR)" :                                   "XSX6.L", 
    "Cash" :                                                                        "GBP=",
}

stock_price_multiplier = {
    "GB0031348658" : 0.01,
    "JE00BJ1DLW90" : 0.01,
    "XSX6.L" : 0.01,
    "IITU.L" : 0.01
}


# read an excel file into a pandas dataframe
import pandas as pd
import openpyxl

df = pd.read_excel("C:\\Users\\jhoxl\\OneDrive\\Investments\\InvestmentData.xlsx", sheet_name="Transactions")
dfIncome = pd.read_excel("C:\\Users\\jhoxl\\OneDrive\\Investments\\InvestmentData.xlsx", sheet_name="Income")

# get distinct values from the 'Position Name' column except for values equal to "Cash"
#distinct_positions = (df[df['Position Name'] != "Cash"])['Position Name'].unique()  
distinct_positions = df['Position Name'].unique()
frames = []

for position in distinct_positions:
    ident = position_identifiers.get(position, "")
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
        positionLastTran = dt.datetime.today().date()

    ds = dg.create_date_series(positionFirstTran, positionLastTran)

    # Fugly hack to handle cash positions, should be removed when we have a better way to handle cash
    if ticker == 'N/A' and ident == "GBP=":
        ts = pd.DataFrame(ds)
        ts['Close'] = 1.0  # Assuming cash has a constant value of 1.0
    else:
        ts = get_time_series(positionFirstTran, positionLastTran, ticker, stock_price_multiplier.get(ident, 1.0))    

    transactions = df[df['Position Name'] == position][['Settle date', 'Adj Qty', 'Value (£)']].rename(columns={'Adj Qty': 'Quantity'})
    transactions['Value (£)'] = transactions['Value (£)'].abs()

    income = dfIncome[dfIncome['Position Name'] == position][['Settle date', 'Quantity', 'Value (£)']]

    PositionDf = DataFormatting.create_holding_dataframe(
        transactions,
        income,
        ds,
        ts,
        position
    )

    #frames.append(mergeddf)
    frames.append(PositionDf)

print("Generating final dataframe...")
# Concatenate all dataframes in the list into a single dataframe
#final_df = pd.concat(frames, ignore_index=True).sort_values(by='Settle date')
final_df = DataFormatting.create_portfolio(frames)

print("Creating daily summary...")
dailyDF = af.create_daily_summary(final_df)

print("Adding scaled daily analytics...")
final_df = af.calculate_weights(final_df, dailyDF)
final_df = af.calculate_daily_returns(final_df)
final_df = af.calculate_composite_returns(final_df)

dailyDF = af.update_summary_with_daily_returns(dailyDF, final_df)
dailyDF = af.calculate_summary_composite_returns(dailyDF)

# Save the final dataframe to an Excel file
print("Saving results...")
print(final_df)
final_df = DataFormatting.drop_unwanted_columns(final_df, [
        'Settle date', 
        'Position name', 
        'Quantity', 
        'Book cost', 
        'ISIN', 
        'Ticker', 
        'Close', 
        'Market value', 
        'ITD PnL', 
        'Income',
        'Portfolio Weight %', 
        'Daily Return %', 
        'Portfolio Return %',
        'Cm. Portfolio Return %',
        'ITD Return %',
        'ITD Portfolio Return %',
        'Ann. ITD Portfolio Return %',
        '1Y Portfolio Return %',
        '3Y Portfolio Return %',
        '5Y Portfolio Return %',
    ])


final_df.to_excel("C:\\Users\\jhoxl\\OneDrive\\Investments\\ProcessedDailyInvestmentData.xlsx", index=False)
dailyDF.to_excel("C:\\Users\\jhoxl\\OneDrive\\Investments\\ProcessedDailySummary.xlsx", index=False)

