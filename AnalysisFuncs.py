import pandas as pd
import numpy as np
import datetime as dt

# create a python function to create a daily summary of the portfolio
def create_daily_summary(df):
    # Ensure 'Settle date' is in datetime format
    df['Settle date'] = pd.to_datetime(df['Settle date'])
    
    # Group by 'Settle date' and aggregate
    daily_summary = df.groupby('Settle date').agg(
        Total_Book_Cost=('Book cost', 'sum'),
        Total_Market_Value=('Market value', 'sum'),
        Total_Income=('Income', 'sum'),
        Total_PnL=('ITD PnL', 'sum'),
        Total_Portfolio_Return_Percent=('Portfolio Return %', 'sum')
    ).reset_index()

    daily_summary = daily_summary.rename(columns={
                                            'Total_Book_Cost': 'Book cost', 
                                            'Total_Market_Value': 'Market value',
                                            'Total_Income': 'Income',
                                            'Total_PnL': 'ITD PnL',
                                            'Total_Portfolio_Return_Percent': 'Portfolio Return %'
                                            }
                                        )

    return daily_summary

# create a python function to calculate the portfolio weight of each position
def calculate_position_weights(df):
    # Calculate the total market value for each settle date
    total_market_value = df.groupby('Settle date')['Market value'].transform('sum')
    
    # Calculate the portfolio weight for each position
    df['Weight %'] = (df['Market value'] / total_market_value) * 100
    
    return df

def calculate_itd_pnl(df):
    # Calculate ITD PnL as Market Value - Book Cost + Income
    # BUG: this is wrong as needs to be rolling sum of 'Income' not immediate, daily value
    df['ITD PnL'] = df['Market value'] - df['Book cost'] + df['Income'].cumsum()
    return df

# create a python function given a dataframe returns the cumulative quantity and value by settle date
def cumulative_by_settle_date(df):    
    # Group by 'Settle Date' and aggregate
    cumulative_df = df.groupby('Settle date').agg(
        Cumulative_Quantity=('Adj Qty', 'sum'),
        Cumulative_Value=('Value (£)', 'sum')
    ).reset_index()

    cumulative_df['Cm.Qty'] = cumulative_df['Cumulative_Quantity'].cumsum()
    cumulative_df['Cm.BookCost'] = cumulative_df['Cumulative_Value'].cumsum()
    
    return cumulative_df[['Settle date', 'Cm.Qty', 'Cm.BookCost']]

def calculate_daily_returns(df, include_portfolio_return=True):
    # The total return for each position is (current close - previous close) + dividend per share / previous close
    ts = []

    # write a loop to iterate over groups in df by 'Position name' and calculate the daily return
    for _, group_df in df.groupby('Position name'):
        group_df = group_df.sort_values(by='Settle date')
        group_df['Daily Return %'] = 100.0 * (((group_df['Close'] - group_df['Close'].shift(1).fillna(method='bfill')) + np.where(group_df['Income Qty'] > 0.0, group_df['Income'] / group_df['Income Qty'], 0.0)) / (group_df['Close'].shift(1).fillna(method='bfill')))
        if include_portfolio_return:
            group_df['Portfolio Return %'] = group_df['Daily Return %'] * group_df['Portfolio Weight %'] / 100
        ts.append(group_df)

    return pd.concat(ts, ignore_index=True).sort_values(by=['Settle date', 'Position name']).reset_index(drop=True)

def calculate_composite_returns(df):
    ts = []

    for _, group_df in df.groupby('Position name'):
        group_df = group_df.sort_values(by='Settle date')
        group_df['Settle date'] = pd.to_datetime(group_df['Settle date'])
        # ITD
        group_df['ITD Portfolio Return %'] = 100.0*((1 + group_df['Portfolio Return %'] / 100).cumprod() - 1)
        # Ann. ITD
        first_trade_date = np.datetime64(group_df['Settle date'].min(), 'D')
        group_df['Ann. ITD Portfolio Return %'] = 100.0 * ((1 + group_df['ITD Portfolio Return %'] / 100) ** (260 / np.maximum(np.busday_count(first_trade_date, group_df['Settle date'].values.astype('datetime64[D]')), 1)) - 1)
        # 1Y
        group_df['1Y Portfolio Return %'] = group_df['Portfolio Return %'].rolling(window=260 * 1).apply(lambda x: 100.0 * ((1 + x / 100).cumprod().iloc[-1] - 1))
        # 3Y
        group_df['3Y Portfolio Return %'] = group_df['Portfolio Return %'].rolling(window=260 * 3).apply(lambda x: 100.0 * ((1 + x / 100).cumprod().iloc[-1] - 1))
        group_df['3Y Portfolio Return %'] = ((1 + group_df['3Y Portfolio Return %'] / 100.0) ** (1/3) - 1) * 100.0
        # 5Y
        group_df['5Y Portfolio Return %'] = group_df['Portfolio Return %'].rolling(window=260 * 5).apply(lambda x: 100.0 * ((1 + x / 100).cumprod().iloc[-1] - 1))
        group_df['5Y Portfolio Return %'] = ((1 + group_df['5Y Portfolio Return %'] / 100.0) ** (1/5) - 1) * 100.0
        ts.append(group_df)
    
    return pd.concat(ts, ignore_index=True).sort_values(by=['Settle date', 'Position name']).reset_index(drop=True)