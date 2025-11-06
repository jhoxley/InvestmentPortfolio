from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af

class CurrentHoldingsReport(BaseReport):


    def generate(self, output_filename: str, data, report_args: dict = dict()):
        print("Generating Daily Details Report")
        
        # === Generate raw data for this report ===

        # (1) Get the latest date's data
        latest_date = data['Settle date'].max()
        current_holdings = data[data['Settle date'] == latest_date].copy()
        current_holdings = current_holdings[['Position name', 'Quantity', 'Book cost', 'Market value', 'Weight %']]

        # (2) Add in total income for each position
        agg_holdings = data.groupby('Position name').agg({'Income': 'sum', 'Settle date' : 'min'}).reset_index()
        agg_holdings.rename(columns={'Income': 'Total income', 'Settle date': 'First acquisition date'}, inplace=True)
        current_holdings = current_holdings.merge(agg_holdings, on='Position name', how='left')

        # (3) Enrich with holding period per position
        current_holdings['Holding period years'] = (latest_date - current_holdings['First acquisition date']).dt.days / 365

        # (4) Derive returns metrics as needed
        current_holdings['Total return %'] = ((current_holdings['Market value'] + current_holdings['Total income'] - current_holdings['Book cost']) / current_holdings['Book cost']) * 100
        current_holdings['Annualised return %'] = ((1 + (current_holdings['Total return %'] / 100)) ** (1 / current_holdings['Holding period years']) - 1) * 100
        current_holdings['Total PnL'] = current_holdings['Market value'] + current_holdings['Total income'] - current_holdings['Book cost']

        # (5) Sort by Market Value descending
        current_holdings = current_holdings.sort_values(by='Total PnL', ascending=False)
        
        # === Format and save as CSV ===
        current_holdings.to_excel(output_filename, index=False)

        # === Format and save as visual ===
                
        return
    
    def required_measures(self) -> list[str]:
        return ["ITD PnL", "Daily Return %", "Weight %"]
    
    def report_name(self) -> str:
        return "CurrentHoldingsReport"