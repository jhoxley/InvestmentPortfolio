from abc import ABC, abstractmethod
from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af

class PeriodicPerformanceReport(BaseReport):

    def report_name(self) -> str:
        return "PeriodicPerformanceReport"

    def create_periodic_performance(self, data: pd.DataFrame, granularity: str, pivot_column: str, lookback: int = -1) -> pd.DataFrame:
        # Select appropriate columns
        data = data[['Settle date', pivot_column, 'Market value', 'Income']]

        # Aggregate to desired periodicity
        data = data.groupby(pd.Grouper(key='Settle date', freq=granularity)).agg({
            'Market value': 'sum',
            'Income': 'sum'
        }).reset_index()

        # (4) Pivot by desired column
        pivot_df = data[['Settle date', pivot_column]].drop_duplicates()
        
        if lookback is not None and lookback > 0:
            pivot_df = pivot_df.tail(lookback)

        return pivot_df

    def generate(self, output_filename: str, data, report_args: dict = dict()):
        print("Generating Daily Summary Report")
        
        # === Generate raw data for this report ===

        # (1) calculate the weighted, daily return for each position
        

        # ( ) Run graphing at different granularities
        for g in ('D', 'ME', 'QE', 'YE'):
            print(' Granularity: ' + g)
            for pv in ('Position name', 'Theme'):
                print(f'  {pv}:')
                for lb in (-1, 52 * 5 * 3):
                    print(f"   Generating periodic performance for granularity '{g}', pivot column '{pv}', {'all' if lb == -1 else f'{lb} days'} history")
                    ds = data.copy()
                    ds = self.create_periodic_performance(ds, g, pv, lb)
                    graph_filename = output_filename.replace('.xlsx', f'_PeriodicPerformance_{g}_by_{pv.replace(" ","")}_{"all" if lb == -1 else f"{lb}_days"}_history.png')
                    print(f"   Graphing to {graph_filename}")
