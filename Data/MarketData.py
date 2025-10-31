import pandas as pd
import yfinance as yf
import os

class MarketDataApi(object):
    
    def get_ticker_currency(self, ticker: str) -> str | None:
        t = yf.Ticker(ticker)
        # fast_info is lightweight and preferred
        try:
            cur = t.fast_info.get("currency")  # dict-like
        except Exception:
            cur = None
        # fallback to .info / .get_info()
        if not cur:
            try:
                info = t.info or t.get_info()
                cur = info.get("currency")
            except Exception:
                cur = None
        return cur

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
            # filter d3 to remove zero close prices. They don't make sense and more likely missing/bad data.
            d3 = d3[d3['Close'] != 0].reset_index(drop=True)

            px_ccy = self.get_ticker_currency(ticker)
            if px_ccy is not None and px_ccy.upper() != 'GBP': # pxmultiplier handles pence like GBp
                print(f"Converting {ticker} prices from {px_ccy} to GBP")
                fx_ticker = f"GBP{px_ccy}=X"
                fx_data = yf.download(fx_ticker, start=start_date, end=end_date, auto_adjust=True)
                # handle missing or unexpected fx_data formats
                try:
                    if fx_data is None or fx_data.empty:
                        raise ValueError("no fx data")
                    try:
                        fx_close = fx_data[('Close', fx_ticker)]
                    except Exception:
                        fx_close = fx_data['Close']
                    fx_df = pd.DataFrame({'Settle date': pd.to_datetime(fx_close.index), 'FX': fx_close.values})
                except Exception as fxe:
                    print(f"Warning: FX data for {fx_ticker} not available, skipping conversion. Error: {fxe}")
                    fx_df = pd.DataFrame({'Settle date': d3['Settle date'], 'FX': 1.0})
                d3 = d3.merge(fx_df, on='Settle date', how='left').sort_values('Settle date')
                d3['FX'] = d3['FX'].ffill().bfill().fillna(1.0)
                d3['Close'] = d3['Close'] / d3['FX']
            return d3
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame({'Settle date': pd.date_range(start=start_date, end=end_date, freq='B'), 'Close': 0})
        

    def get_time_series(self, start_date, end_date, ticker, pxmultiplier=1.0):
        cache_file = f"cache_{ticker}.parquet"
        if start_date >= end_date:
            print(f"Start date {start_date} is after or equal to end date {end_date}. Adjusting dates.")
            start_date = end_date - pd.Timedelta(days=5)
        if os.path.exists(cache_file):
            df = pd.read_parquet(cache_file)
            loaded_first_date = df['Settle date'].min().to_pydatetime().date()
            loaded_last_date = df['Settle date'].max().to_pydatetime().date()
            if loaded_first_date <= pd.to_datetime(start_date).date() and loaded_last_date >= pd.to_datetime(end_date).date():
                print(f"Cache covers the requested date range. Returning cached timeseries for {ticker}.")
                return df[(df['Settle date'] >= start_date) & (df['Settle date'] <= end_date)]
            else:
                print(f"Cache does not cover the requested date range. Cache covers {loaded_first_date} to {loaded_last_date}. Requested is {start_date} to {end_date}. Fetching new data...")
                # create early date range if needed
                if loaded_first_date > pd.to_datetime(start_date).date():
                    df_early = self.get_time_series_internal(start_date, loaded_first_date - pd.Timedelta(days=1), ticker, pxmultiplier)
                    df = pd.concat([df_early, df], ignore_index=True)
                    print(f"Prepended {len(df_early)} rows to cache for {ticker}. Earliest date is now {df['Settle date'].min().to_pydatetime().date()}.")
                # create late date range if needed
                if loaded_last_date < pd.to_datetime(end_date).date():
                    df_late = self.get_time_series_internal(loaded_last_date + pd.Timedelta(days=1), end_date, ticker, pxmultiplier)
                    df = pd.concat([df, df_late], ignore_index=True)
                    print(f"Appended {len(df_late)} rows to cache for {ticker}. Latest date is now {df['Settle date'].max().to_pydatetime().date()}.")
                df = df.sort_values(by='Settle date').reset_index(drop=True)
                df.to_parquet(cache_file)
        else:
            print(f"No cache found for {ticker}. Fetching data...")
            df = self.get_time_series_internal(start_date,end_date,ticker,pxmultiplier)
            df.to_parquet(cache_file)
            print("Saved DataFrame to cache.")
        return df