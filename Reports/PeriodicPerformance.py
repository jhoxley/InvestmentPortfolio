from abc import ABC, abstractmethod
from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af
import matplotlib.pyplot as plt

class PeriodicPerformanceReport(BaseReport):

    def report_name(self) -> str:
        return "PeriodicPerformanceReport"

    def create_periodic_performance(self, data: pd.DataFrame, granularity: str, pivot_column: str, lookback: int = -1) -> pd.DataFrame:
        # Select appropriate columns
        data = data[['Settle date', pivot_column, 'Market value', 'Income', 'Book cost']]

        # Aggregate all values on a daily basis first
        data = data.groupby(['Settle date', pivot_column]).agg({
            'Market value': 'sum',
            'Income': 'sum',
            'Book cost': 'sum'
        }).reset_index()

        # Make income a cumulative sum over time
        data['Income'] = data.groupby(['Settle date', pivot_column])['Income'].cumsum()

        # Calculate pivot value
        data['Pivot value'] = data['Market value'] + data['Income'] - data['Book cost']

        # Drop intermediary columns
        data = data[['Settle date', pivot_column, 'Pivot value']]

        # Aggregate to desired periodicity
        data = data.groupby([pd.Grouper(key='Settle date', freq=granularity), pivot_column]).agg({
            'Pivot value': 'last'
        }).reset_index()
        
        # Pivot by desired column
        pivot_df = data.pivot(index='Settle date', columns=pivot_column, values=['Pivot value'])
        
        if lookback is not None and lookback > 0:
            pivot_df = pivot_df.tail(lookback)

        return pivot_df
    
    def render_Graph(self, data: pd.DataFrame, output_filename: str, granularity: str, lb: int, pivot_column: str):
        fig, ax = plt.subplots(figsize=(16,12))
        data.plot.line(ax=ax, cmap='gist_rainbow', alpha=0.8)

        ax.set_title(f'Periodic Performance by {pivot_column} - {granularity} Granularity - {"all" if lb == -1 else f"{lb} days"} history')
        ax.set_ylabel('PnL (£)')   
        ax.set_xlabel('Date')
        ax.grid(axis='y', linestyle='--', alpha=0.7, linewidth=0.8, which='major')
        ax.grid(axis='y', linestyle='--', alpha=0.4, linewidth=0.4, which='minor')

        ncols = min(len(data.columns), 2)
        ax.legend(title=pivot_column, loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=ncols, fontsize='small')

        plt.tight_layout()
        plt.savefig(output_filename, dpi=300)
        plt.close(fig)

    def generate(self, output_filename: str, data, report_args: dict = dict()):
        print("Generating Periodic Performance Report")
        
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
                    self.render_Graph(ds, graph_filename, g, lb, pv)
