import pandas as pd

# create a python function to create a time series of dates from a start date to an end date skipping weekends and holidays
def create_date_series(start_date, end_date):
    # Create a date range excluding weekends
    date_range = pd.date_range(start=start_date, end=end_date, freq='B')
    
    # Convert to a DataFrame
    date_series = pd.DataFrame(date_range, columns=['Settle date'])
    
    return date_series