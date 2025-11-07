from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

class CurrentHoldingsReport(BaseReport):

    def graph_market_value_by_theme(self, by_theme: pd.DataFrame, output_filename: str):
        graphDf = by_theme[['Theme', 'Market value']]
        #graphDf['Theme'] = graphDf['Theme'].astype(str)
        #graphDf.set_index('Theme', inplace=True)

        fig,ax = plt.subplots(figsize=(12,8))
        cmap = plt.cm.get_cmap('tab20')
        # sample the colormap to get distinct RGBA colors for each slice
        colors = cmap(np.linspace(0, 1, len(graphDf)))
        hex_list = [mcolors.to_hex(c) for c in colors]
        wedges, texts, autotexts = ax.pie(
            graphDf['Market value'],
            labels=graphDf['Theme'],
            autopct="%1.1f%%",
            startangle=90,
            colors=hex_list[:len(graphDf)],
            pctdistance=0.75
        )
        ax.set_title(f'Market Value by Theme')
        ax.axis("equal")  # keep the pie circular

        ncols = min(len(graphDf), 2)
        ax.legend(title='Theme', loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=ncols, fontsize='small')
        ax.legend(title='Theme', loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=ncols, fontsize='small')

        plt.tight_layout()
        plt.savefig(output_filename, dpi=300)
        plt.close(fig)

    def generate(self, output_filename: str, data, report_args: dict = dict()):
        print("Generating Current Holdings Report")
        
        # === Generate raw data for this report ===

        # (1) Get the latest date's data
        latest_date = data['Settle date'].max()
        current_holdings = data[data['Settle date'] == latest_date].copy()
        current_holdings = current_holdings[['Position name', 'Theme', 'Quantity', 'Book cost', 'Market value', 'Weight %']]

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
        
        # (6) Aggregate by theme for summary
        by_theme = current_holdings.groupby('Theme').agg({
            'Book cost': 'sum',
            'Market value': 'sum',
            'Total income': 'sum',
            'Total PnL': 'sum',
            'Weight %': 'sum'
        }).reset_index()

        # === Format and save as CSV ===
        with pd.ExcelWriter(output_filename, engine='openpyxl') as writer:
            current_holdings.to_excel(writer, sheet_name='Current Holdings', index=False)
            by_theme.to_excel(writer, sheet_name='Themes', index=False)

        by_theme['Total return %'] = ((by_theme['Market value'] + by_theme['Total income'] - by_theme['Book cost']) / by_theme['Book cost']) * 100
        by_theme = by_theme.sort_values(by='Market value', ascending=False)

        graph_market_value_filename = output_filename.replace('.xlsx', '_MarketValueByTheme.png')
        self.graph_market_value_by_theme(by_theme, graph_market_value_filename)
                
        return
    
    def required_measures(self) -> list[str]:
        return ["ITD PnL", "Daily Return %", "Weight %"]
    
    def report_name(self) -> str:
        return "CurrentHoldingsReport"
    