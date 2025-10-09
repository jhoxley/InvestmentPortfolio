from abc import ABC, abstractmethod
from .BaseReport import BaseReport
import pandas as pd
import numpy as np

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
        data['Settle date'] = pd.to_datetime(data['Settle date'])

        daily_summary = data.groupby('Settle date').agg(
            Total_Book_Cost=('Book cost', 'sum'),
            Total_Market_Value=('Market value', 'sum'),
            Total_Income=('Income', 'sum'),
            Total_PnL=('ITD PnL', 'sum'),
            Total_Portfolio_Return_Percent=('Portfolio Return %', 'sum')
        ).reset_index()

        daily_summary = daily_summary.rename(columns={
                                                'Total_Book_Cost': 'Book cost', 
                                                'Total_Market_Value': 'Market value',
                                                'Total_Income': 'Income',
                                                'Total_PnL': 'ITD PnL',
                                                'Total_Portfolio_Return_Percent': 'Portfolio Return %'
                                                }
                                            )

        # (3) aggregate to desired periodicity
        periodicity = self.get_periodicity()

        summary = daily_summary.groupby(pd.Grouper(key='Settle date', freq=periodicity)).agg(
            Total_Book_Cost=('Book cost', 'max'),
            Open_Market_Value=('Market value', 'first'),
            High_Market_Value=('Market value', 'max'),
            Low_Market_Value=('Market value', 'min'),
            Close_Market_Value=('Market value', 'last'),
            Total_Income=('Income', 'sum'),
            Total_PnL=('ITD PnL', 'last')
        ).reset_index()

        summary = summary.rename(columns={
                                                'Total_Book_Cost': 'Book cost', 
                                                'Open_Market_Value': 'Open Market value',
                                                'High_Market_Value': 'High Market value',                                                
                                                'Low_Market_Value': 'Low Market value',
                                                'Close_Market_Value': 'Close Market value',
                                                'Total_Income': 'Income',
                                                'Total_PnL': 'ITD PnL'
                                                }
                                            )

        # === Format and save as CSV ===
        summary.to_excel(output_filename, index=False)

        # === Format and save as visual ===
        
        return
    
    def required_measures(self) -> list[str]:
        return ["ITD PnL", "Daily Return %", "Weight %"]
    
    
    