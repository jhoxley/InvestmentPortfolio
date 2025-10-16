from abc import ABC, abstractmethod
from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af

class PeriodicSummaryBase(BaseReport):

    @abstractmethod
    def get_periodicity(self) -> str:
        return "D"

    def generate(self, output_filename: str, data):
        print("Generating " + self.report_name())
        
        # === Generate raw data for this report ===

        # (1) calculate the weighted, daily return for each position
        data['Portfolio Return %'] = data['Daily Return %'] * (data['Weight %'] / 100)

        # (2) group positions by settle date
        daily_summary = af.create_daily_summary(data)

        # (3) Add in composite returns
        daily_summary['Portfolio Return %'] = daily_summary['Portfolio Return %'].fillna(0)
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

        # (4) aggregate to desired periodicity
        periodicity = self.get_periodicity()

        summary = daily_summary.groupby(pd.Grouper(key='Settle date', freq=periodicity)).agg(
            Total_Book_Cost=('Book cost', 'max'),
            Total_Capital=('Capital', 'last'),
            Open_Market_Value=('Market value', 'first'),
            High_Market_Value=('Market value', 'max'),
            Low_Market_Value=('Market value', 'min'),
            Close_Market_Value=('Market value', 'last'),
            Total_Income=('Income', 'sum'),
            Total_PnL=('ITD PnL', 'last'),
            ITD_Return=('Ann. ITD Portfolio Return %', 'last'),
            Return_1Y=('1Y Portfolio Return %', 'last'),
            Return_3Y=('3Y Portfolio Return %', 'last'),
            Return_5Y=('5Y Portfolio Return %', 'last'),
        ).reset_index()

        summary = summary.rename(columns={
                                                'Total_Book_Cost': 'Book cost', 
                                                'Total_Capital': 'Close Capital',
                                                'Open_Market_Value': 'Open Market value',
                                                'High_Market_Value': 'High Market value',                                                
                                                'Low_Market_Value': 'Low Market value',
                                                'Close_Market_Value': 'Close Market value',
                                                'Total_Income': 'Income',
                                                'Total_PnL': 'ITD PnL',
                                                'ITD_Return': 'ITD Return %',
                                                'Return_1Y': '1Y Return %',
                                                'Return_3Y': '3Y Return %',
                                                'Return_5Y': '5Y Return %'
                                                }
                                            )

        # === Format and save as CSV ===
        summary.to_excel(output_filename, index=False)

        # === Format and save as visual ===
        
        return
    
    def required_measures(self) -> list[str]:
        return ["ITD PnL", "Daily Return %", "Weight %"]
    
    
    