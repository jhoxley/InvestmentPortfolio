from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af

class DailySummaryReport(BaseReport):

    def generate(self, output_filename: str, data, report_args: dict = dict()):
        print("Generating Daily Summary Report")
        
        # === Generate raw data for this report ===

        # (1) calculate the weighted, daily return for each position
        data['Portfolio Return %'] = data['Daily Return %'] * (data['Weight %'] / 100)

        # (2) group positions by settle date
        daily_summary = af.create_daily_summary(data)

        # (4) calculate composite returns (ITD, 1Y, 3Y, 5Y, Ann. ITD) for each position
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

        # === Format and save as CSV ===
        daily_summary.to_excel(output_filename, index=False)

        # === Format and save as visual ===
        
        return
    
    def required_measures(self) -> list[str]:
        return ["ITD PnL", "Daily Return %", "Weight %"]
    
    def report_name(self) -> str:
        return "DailySummaryReport"