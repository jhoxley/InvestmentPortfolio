import pandas as pd
import datetime as dt

# create a python function to create a daily summary of the portfolio
def create_daily_summary(df):
    # Ensure 'Settle date' is in datetime format
    df['Settle date'] = pd.to_datetime(df['Settle date'])
    
    # Group by 'Settle date' and aggregate
    daily_summary = df.groupby('Settle date').agg(
        Total_Book_Cost=('Book cost', 'sum'),
        Total_Market_Value=('Market value', 'sum'),
        Total_PnL=('ITD PnL', 'sum')
    ).reset_index()

    #daily_summary['Total Return %'] = (daily_summary['Total_Market_Value'] + daily_summary['Total_Book_Cost']) / -daily_summary['Total_Book_Cost']
    
    #daily_summary['Daily Return %'] = (daily_summary['Total_Market_Value'] - daily_summary['Total_Market_Value'].shift(1)) / -daily_summary['Total_Book_Cost']

    daily_summary = daily_summary.rename(columns={
                                            'Total_Book_Cost': 'Book cost', 
                                            'Total_Market_Value': 'Market value',
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
                                            'ITD PnL': 'Total_ITD_PnL'
                                            }
                                        )
    # Merge the daily summary with the main dataframe
    df = pd.merge(df, daily_summary, on='Settle date', how='left')
    
    # Calculate the portfolio weight for each position
    df['Portfolio Weight %'] =(df['Market value'] / df['Total_Market_Value']) * 100
    
    # Drop the temporary total columns
    df = df.drop(columns=['Total_Book_Cost', 'Total_Market_Value', 'Total_ITD_PnL'])

    return df

# create a python function given a dataframe returns the cumulative quantity and value by settle date
def cumulative_by_settle_date(df):
    # Ensure 'Settle Date' is in datetime format
    #df['Settle date'] = pd.to_datetime(df['Settle date'])
    
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
    # group 'df' by 'Position Name' and calculate daily returns and sort by 'Settle date'
    #df['Daily Return %'] = df.sort_values(by=['Position Name', 'Settle date']).groupby('Position Name')['Close'].pct_change()

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


