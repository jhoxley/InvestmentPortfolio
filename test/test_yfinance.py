import yfinance as yf

try:
    ticker = yf.Ticker("BMRS271")  # Apple Inc.
    print(ticker)
    print('getting history:')
    data = yf.download("BMRS271", period="6mo", interval="1d")
    print(data)
except Exception as e:
    print(f"Error: {e}")