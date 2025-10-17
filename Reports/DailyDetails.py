from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af
import matplotlib.pyplot as plt

class DailyDetailsReport(BaseReport):

    def graph_market_value_by_position(self, daily_details: pd.DataFrame, output_filename: str):
        graphDf = daily_details[['Settle date', 'Position name', 'Market value']]
        graphDf = graphDf.pivot(index='Settle date', columns='Position name', values='Market value').fillna(0)
        graphDf = graphDf.drop(columns=['Cash'], errors='ignore')  # Remove cash column if present

        fig,ax = plt.subplots(figsize=(12,8))
        graphDf.plot.area(ax=ax, cmap='tab20', alpha=0.7)

        ax.set_title('Daily Market Value by Position')
        ax.set_ylabel('Market Value (£)')   
        ax.set_xlabel('Date')
        ax.grid(axis='y', linestyle='--', alpha=0.7, linewidth=0.8, which='major')
        ax.grid(axis='y', linestyle='--', alpha=0.4, linewidth=0.4, which='minor')

        ncols = min(len(graphDf.columns), 2)
        ax.legend(title='Position name', loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=ncols, fontsize='small')

        plt.tight_layout()
        plt.savefig(output_filename)
        plt.close(fig)

    def graph_weight_by_position(self, daily_details: pd.DataFrame, output_filename: str):
        graphDf = daily_details[['Settle date', 'Position name', 'Weight %']]
        graphDf = graphDf.pivot(index='Settle date', columns='Position name', values='Weight %').fillna(0)
        graphDf = graphDf.drop(columns=['Cash'], errors='ignore')  # Remove cash column if present
        
        fig,ax = plt.subplots(figsize=(12,8))
        graphDf.plot.area(ax=ax, cmap='tab20', alpha=0.7)

        ax.set_title('Daily Position Weighting')
        ax.set_ylabel('Portfolio Weight (%)')   
        ax.set_xlabel('Date')
        ax.grid(axis='y', linestyle='--', alpha=0.7, linewidth=0.8, which='major')
        ax.grid(axis='y', linestyle='--', alpha=0.4, linewidth=0.4, which='minor')

        ncols = min(len(graphDf.columns), 2)
        ax.legend(title='Position name', loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=ncols, fontsize='small')

        plt.tight_layout()
        plt.savefig(output_filename)
        plt.close(fig)

    def generate(self, output_filename: str, data, report_args: dict = dict()):
        print("Generating Daily Details Report")
        
        # === Generate raw data for this report ===

        # (1) calculate the weighted, daily return for each position
        data['Portfolio Return %'] = data['Daily Return %'] * (data['Weight %'] / 100)

        # (3) calculate composite returns (ITD, 1Y, 3Y, 5Y, Ann. ITD) for each position
        daily_details = af.calculate_composite_returns(data)
        
        # === Format and save as CSV ===
        daily_details.to_excel(output_filename, index=False)

        # === Format and save as visual ===
        graph_market_value_filename = output_filename.replace('.xlsx', '_MarketValueByPosition.png')
        self.graph_market_value_by_position(daily_details, graph_market_value_filename)

        graph_weight_filename = output_filename.replace('.xlsx', '_WeightByPosition.png')
        self.graph_weight_by_position(daily_details, graph_weight_filename)
        
        return
    
    def required_measures(self) -> list[str]:
        return ["ITD PnL", "Daily Return %", "Weight %"]
    
    def report_name(self) -> str:
        return "DailyDetailsReport"