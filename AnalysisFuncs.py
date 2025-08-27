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
        Total_PnL=('ITD PnL', 'sum')
    ).reset_index()

    daily_summary = daily_summary.rename(columns={
                                            'Total_Book_Cost': 'Book cost', 
                                            'Total_Market_Value': 'Market value',
                                            'Total_Income': 'Income',
                                            'Total_PnL': 'ITD PnL'
                                            }
                                        )

    return daily_summary

# create a python function to calculate the portfolio weight of each position
def calculate_weights(df, daily_summary):   
    # rename columns in daily_summary to avoid conflicts during merge
    daily_summary = daily_summary.rename(columns={
                                            'Book cost': 'Total_Book_Cost', 
                                            'Market value': 'Total_Market_Value',
                                            'ITD PnL': 'Total_ITD_PnL',
                                            'Income': 'Total_Income'
                                            }
                                        )
    # Merge the daily summary with the main dataframe
    df = pd.merge(df, daily_summary, on='Settle date', how='left')
    
    # Calculate the portfolio weight for each position
    df['Portfolio Weight %'] =(df['Market value'] / df['Total_Market_Value']) * 100
    
    # Drop the temporary total columns
    df = df.drop(columns=['Total_Book_Cost', 'Total_Market_Value', 'Total_ITD_PnL', 'Total_Income'])

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

def calculate_returns(df):  
    """
    Calculate daily returns based on the 'Close' column per 'Position Name'.
    
    Parameters:
    df (DataFrame): The DataFrame containing 'Close' and 'Position Name'.
    
    Returns:
    DataFrame: The DataFrame with an additional 'Daily Return %' column.
    """     
    # Return is (current value - book cost + dividends + interest) / original cost
    # calculate a return in 'df' by 'Position Name' by taking the current 'Book Market Value' minus the previous 'Book Market Value' and dividing by the 'Cm.BookCost'
    df['Daily Return %'] = df.sort_values(by=['Position name', 'Settle date']).groupby('Position name').apply(
        lambda x: (x['Market value'] - x['Market value'].shift(1)) / x['Book cost'].shift(1)
    ).reset_index(drop=True) 

    # fill and aggregate
    df['Daily Return %'] = df['Daily Return %'].fillna(0)   
    df['Portfolio Return %'] = df['Daily Return %'] * df['Portfolio Weight %'] / 100

    df['ITD Return %'] = df.groupby('Position name').apply(
        lambda x: (x['Market value'] + x['Book cost']) / -x['Book cost']
    ).reset_index(drop=True) 
    df['Portfolio ITD Return %'] = df['ITD Return %'] * df['Portfolio Weight %'] / 100
 
    # calculate the cumulative portfolio return by grouping by 'Position Name' and 'Settle date' then adding 1 to each daily return and then taking the cumulative product
    df['Cm. Portfolio Return %'] = df.groupby('Position name')['Portfolio Return %'].transform(lambda x: (1 + x).cumprod() - 1) 

    return df

def calculate_daily_returns(df):
    # The total return for each position is (current close - previous close) + dividend per share / previous close
    ts = []

    # write a loop to iterate over groups in df by 'Position name' and calculate the daily return
    for _, group_df in df.groupby('Position name'):
        group_df = group_df.sort_values(by='Settle date')
        group_df['Daily Return %'] = 100.0 * (((group_df['Close'] - group_df['Close'].shift(1).fillna(method='bfill')) + np.where(group_df['Income Qty'] > 0.0, group_df['Income'] / group_df['Income Qty'], 0.0)) / (group_df['Close'].shift(1).fillna(method='bfill')))
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

def calculate_summary_composite_returns(daily_summary):
    daily_summary = daily_summary.sort_values(by='Settle date')
    daily_summary['Portfolio Return %'] = daily_summary['Portfolio Return %'].fillna(0)

    # ITD
    daily_summary['ITD Portfolio Return %'] = 100.0*((1 + daily_summary['Portfolio Return %'] / 100).cumprod() - 1)

    # Ann. ITD
    first_trade_date = np.datetime64(daily_summary['Settle date'].min(), 'D')
    daily_summary['Ann. ITD Portfolio Return %'] = 100.0 * ((1 + daily_summary['ITD Portfolio Return %'] / 100) ** (260 / np.maximum(np.busday_count(first_trade_date, daily_summary['Settle date'].values.astype('datetime64[D]')), 1)) - 1)

    # 1Y
    daily_summary['1Y Portfolio Return %'] = daily_summary['Portfolio Return %'].rolling(window=260 * 1).apply(lambda x: 100.0 * ((1 + x / 100).cumprod().iloc[-1] - 1))
    
    # 3Y
    daily_summary['3Y Portfolio Return %'] = daily_summary['Portfolio Return %'].rolling(window=260 * 3).apply(lambda x: 100.0 * ((1 + x / 100).cumprod().iloc[-1] - 1))
    daily_summary['3Y Portfolio Return %'] = ((1 + daily_summary['3Y Portfolio Return %'] / 100.0) ** (1/3) - 1) * 100.0
    
    # 5Y
    daily_summary['5Y Portfolio Return %'] = daily_summary['Portfolio Return %'].rolling(window=260 * 5).apply(lambda x: 100.0 * ((1 + x / 100).cumprod().iloc[-1] - 1))
    daily_summary['5Y Portfolio Return %'] = ((1 + daily_summary['5Y Portfolio Return %'] / 100.0) ** (1/5) - 1) * 100.0

    return daily_summary

def update_summary_with_daily_returns(daily_summary, df):
    # Ensure 'Settle date' is in datetime format
    daily_summary['Settle date'] = pd.to_datetime(daily_summary['Settle date'])
    df['Settle date'] = pd.to_datetime(df['Settle date'])

    # Merge the daily summary with the main dataframe to get daily returns
    merged_df = pd.merge(daily_summary, df[['Settle date', 'Portfolio Return %']], on='Settle date', how='left')

    # Aggregate to get total daily return and cumulative return
    updated_summary = merged_df.groupby('Settle date').agg(
        Book_cost=('Book cost', 'first'),
        Market_value=('Market value', 'first'),
        ITD_PnL=('ITD PnL', 'first'),
        Income=('Income', 'first'),
        Daily_Return_Percent=('Portfolio Return %', 'sum')
    ).reset_index()

    updated_summary = updated_summary.rename(columns={
                                            'Book_cost': 'Book cost', 
                                            'Market_value': 'Market value',
                                            'ITD_PnL': 'ITD PnL',
                                            'Income': 'Income',
                                            'Daily_Return_Percent': 'Portfolio Return %'
                                            }
                                        )

    return updated_summary