from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af
import matplotlib.pyplot as plt

class DailyDetailsReport(BaseReport):

    def graph_market_value_by_position(self, daily_details: pd.DataFrame, output_filename: str, pivot_column: str):
        graphDf = daily_details[['Settle date', pivot_column, 'Market value']]
        graphDf = graphDf.pivot(index='Settle date', columns=pivot_column, values='Market value').fillna(0)
        graphDf = graphDf.drop(columns=['Cash'], errors='ignore')  # Remove cash column if present

        fig,ax = plt.subplots(figsize=(12,8))
        graphDf.plot.area(ax=ax, cmap='tab20', alpha=0.7)

        ax.set_title(f'Daily Market Value by {pivot_column}')
        ax.set_ylabel('Market Value (£)')   
        ax.set_xlabel('Date')
        ax.grid(axis='y', linestyle='--', alpha=0.7, linewidth=0.8, which='major')
        ax.grid(axis='y', linestyle='--', alpha=0.4, linewidth=0.4, which='minor')

        ncols = min(len(graphDf.columns), 2)
        ax.legend(title=pivot_column, loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=ncols, fontsize='small')

        plt.tight_layout()
        plt.savefig(output_filename, dpi=300)
        plt.close(fig)

    def graph_weight_by_position(self, daily_details: pd.DataFrame, output_filename: str, pivot_column: str):
        graphDf = daily_details[['Settle date', pivot_column, 'Weight %']]
        graphDf = graphDf.pivot(index='Settle date', columns=pivot_column, values='Weight %').fillna(0)
        graphDf = graphDf.drop(columns=['Cash'], errors='ignore')  # Remove cash column if present
        
        fig,ax = plt.subplots(figsize=(12,8))
        graphDf.plot.area(ax=ax, cmap='tab20', alpha=0.7)

        ax.set_title('Daily Position Weighting')
        ax.set_ylabel('Portfolio Weight (%)')   
        ax.set_xlabel('Date')
        ax.grid(axis='y', linestyle='--', alpha=0.7, linewidth=0.8, which='major')
        ax.grid(axis='y', linestyle='--', alpha=0.4, linewidth=0.4, which='minor')

        ncols = min(len(graphDf.columns), 2)
        ax.legend(title=pivot_column, loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=ncols, fontsize='small')

        plt.tight_layout()
        plt.savefig(output_filename, dpi=300)
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
        self.graph_market_value_by_position(daily_details, graph_market_value_filename, 'Position name')

        graph_weight_filename = output_filename.replace('.xlsx', '_WeightByPosition.png')
        self.graph_weight_by_position(daily_details, graph_weight_filename, 'Position name')

        daily_by_theme = daily_details.copy()
        daily_by_theme = daily_by_theme.groupby(['Settle date', 'Theme'], as_index=False).agg({
            'Market value': 'sum',
            'Weight %': 'sum'
        })

        graph_market_value_filename = output_filename.replace('.xlsx', '_MarketValueByTheme.png')
        self.graph_market_value_by_position(daily_by_theme, graph_market_value_filename, 'Theme')

        graph_weight_filename = output_filename.replace('.xlsx', '_WeightByTheme.png')
        self.graph_weight_by_position(daily_by_theme, graph_weight_filename, 'Theme')
        
        return
    
    def required_measures(self) -> list[str]:
        return ["ITD PnL", "Daily Return %", "Weight %"]
    
    def report_name(self) -> str:
        return "DailyDetailsReport"