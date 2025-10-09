import pandas as pd
import yfinance as yf
import os

class MarketDataApi(object):
    
    def get_time_series_internal(self, start_date, end_date, ticker, pxmultiplier=1.0):
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
        

    def get_time_series(self, start_date, end_date, ticker, pxmultiplier=1.0):
        cache_file = f"cache_{ticker}.parquet"
        if os.path.exists(cache_file):
            df = pd.read_parquet(cache_file)
            print("Loaded DataFrame from cache. Testing date range coverage...")
            loaded_first_date = df['Settle date'].min().to_pydatetime().date()
            loaded_last_date = df['Settle date'].max().to_pydatetime().date()
            if loaded_first_date <= pd.to_datetime(start_date).date() and loaded_last_date >= pd.to_datetime(end_date).date():
                print("Cache covers the requested date range.")
                return df[(df['Settle date'] >= start_date) & (df['Settle date'] <= end_date)]
            else:
                print(f"Cache does not cover the requested date range. Cache covers {loaded_first_date} to {loaded_last_date}. Requested is {start_date} to {end_date}. Fetching new data...")
            
        df = self.get_time_series_internal(start_date,end_date,ticker,pxmultiplier)
        df.to_parquet(cache_file)
        print("Saved DataFrame to cache.")
        return df