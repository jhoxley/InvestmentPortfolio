import pandas as pd
import datetime as dt


def create_holding_dataframe(dfTransactions, dfIncome, dsDateSeries, dfClosePrices, positionName):
    """
        create_holding_dataframe
        Creates a DataFrame of holdings by merging transactions, income, date series, and close prices.
    """

    # Fold all data in together
    dfFinal = pd.merge(dsDateSeries, dfTransactions, on='Settle date', how='left').sort_values(by='Settle date')
    # multiply the 'Value (£)' by the sign of the 'Quantity' to ensure correct direction of values
    dfFinal['Value (£)'] = dfFinal['Value (£)'] * dfFinal['Quantity'].apply(lambda x: 1.0 if x >= 0.0 else -1.0)
    dfFinal = dfFinal.groupby('Settle date').agg(
        Cumulative_Quantity=('Quantity', 'sum'),
        Cumulative_Value=('Value (£)', 'sum')
    ).reset_index()
    dfFinal['Quantity'] = dfFinal['Cumulative_Quantity'].cumsum()
    dfFinal['Book cost'] = dfFinal['Cumulative_Value'].cumsum()
    dfFinal = dfFinal.drop(columns=['Cumulative_Quantity','Cumulative_Value'], errors='ignore')
    # (1) we want (Settle date, Quantity, Book Cost) over all dates

    # alias dfIncome columns
    dfIncome = dfIncome.groupby('Settle date').agg(
        Income_Qty=('Quantity', 'sum'),
        Income=('Value (£)', 'sum')
    ).reset_index()
    dfIncome = dfIncome.rename(columns={'Income_Qty': 'Income Qty'})
    
    dfFinal = pd.merge(dfFinal, dfIncome, on='Settle date', how='left').fillna(0)
    # (2) we want (Settle date, Quantity, Book Cost, Income Qty, Income) over all dates

    dfFinal = pd.merge(dfFinal, dfClosePrices, on='Settle date', how='left').ffill()
    # (3) we want (Settle date, Quantity, Book Cost, Income Qty, Income, Close) over all dates

    # Add in capital
    dfLodgements = dfTransactions[dfTransactions['Reference'].str.startswith('L')][['Settle date', 'Value (£)']].rename(columns={'Value (£)': 'Capital'})
    dfSubscriptions = dfTransactions[dfTransactions['Reference'].str.lower().isin(['fpc', 'card web', 'contrib', 'bacs'])][['Settle date', 'Value (£)']].rename(columns={'Value (£)': 'Capital'})
    
    if dfLodgements.empty:
        dfLodgements = pd.DataFrame(columns=['Settle date', 'Capital'])
    if dfSubscriptions.empty:
        dfSubscriptions = pd.DataFrame(columns=['Settle date', 'Capital'])

    dfCapital = pd.concat([dfLodgements, dfSubscriptions], ignore_index=True, sort=False).groupby('Settle date').agg(
        Capital=('Capital', 'sum')
    ).reset_index()

    dfFinal = dfFinal.infer_objects(copy=False)
    dfCapital = dfCapital.infer_objects(copy=False)
    dfFinal = pd.merge(dfFinal, dfCapital, on='Settle date', how='left').fillna(0)
    dfFinal['Capital'] = dfFinal['Capital'].cumsum()

    # Filter negative quantities - we dont go short here
    dfFinal['Quantity'] = dfFinal['Quantity'].apply(lambda x: max(x, 0))

    # Calculate derived columns
    dfFinal['Market value'] = dfFinal['Quantity'] * dfFinal['Close']
    dfFinal['Day PnL'] = dfFinal['Market value'].diff().fillna(0)
    dfFinal['ITD PnL'] = dfFinal['Day PnL'] + dfFinal['Income']
    dfFinal['ITD PnL'] = dfFinal['ITD PnL'].cumsum()

    # Add static columns
    dfFinal['Position name'] = positionName

    # reorder colummns
    dfFinal = dfFinal[['Settle date', 'Position name', 'Capital', 'Quantity', 'Book cost', 'Income Qty', 'Income', 'Close', 
                       'Market value', 'Day PnL', 'ITD PnL']]   

    # Ensure the 'Settle date' is in datetime format
    dfFinal['Settle date'] = pd.to_datetime(dfFinal['Settle date'])

    # Ensure the 'Position name' is a string
    dfFinal['Position name'] = dfFinal['Position name'].astype(str)

    # Ensure numeric columns are in the correct format
    numeric_columns = ['Quantity', 'Capital', 'Book cost', 'Income Qty', 'Income', 'Close', 'Market value', 'Day PnL', 'ITD PnL']
    for col in numeric_columns:     
        dfFinal[col] = pd.to_numeric(dfFinal[col], errors='coerce').astype('float')

    # Return results
    return dfFinal


def create_portfolio(dfHoldings):
    """
        create_portfolio
        Merges multiple holdings dataFrames into a single portfolio DataFrame.
    """
    return pd.concat(dfHoldings, ignore_index=True).sort_values(by='Settle date')



def drop_unwanted_columns(df, columns_to_keep):
    """
    Drops any column not in the specified list from the DataFrame.
    
    Parameters:
    df (DataFrame): The DataFrame from which to drop columns.
    columns_to_keep (list): List of column names to drop.
    
    Returns:
    DataFrame: The DataFrame with specified columns kept, all else dropped.
    """
    columns_to_drop = [col for col in df.columns if col not in columns_to_keep]
    result = df.drop(columns=columns_to_drop, errors='ignore')
    if result.columns.empty:
        return pd.DataFrame()  # Return an empty DataFrame if no columns are left
    else:
        return result
