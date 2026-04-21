import yfinance as yf

try:
    ticker = yf.Ticker("AAPL")  # Apple Inc.
    print(ticker)
    print('getting history:')
    data = yf.download("AAPL", period="1mo", interval="1d")
    print(data)
except Exception as e:
    print(f"Error: {e}")