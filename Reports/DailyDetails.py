from .BaseReport import BaseReport
import pandas as pd
import numpy as np

class DailyDetailsReport(BaseReport):

    def generate(self, output_filename: str, data):
        print("Generating Daily Details Report")
        
        # === Generate raw data for this report ===

        # (1) calculate the weighted, daily return for each position
        data['Portfolio Return %'] = data['Daily Return %'] * (data['Weight %'] / 100)

        # (3) calculate composite returns (ITD, 1Y, 3Y, 5Y, Ann. ITD) for each position
        ts = []

        for _, group_df in data.groupby('Position name'):
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
        
        daily_details = pd.concat(ts, ignore_index=True).sort_values(by=['Settle date', 'Position name']).reset_index(drop=True)

        # === Format and save as CSV ===
        daily_details.to_excel(output_filename, index=False)

        # === Format and save as visual ===
        
        return
    
    def required_measures(self) -> list[str]:
        return ["ITD PnL", "Daily Return %", "Weight %"]
    
    def get_report_name(self) -> str:
        return "DailyDetailsReport"