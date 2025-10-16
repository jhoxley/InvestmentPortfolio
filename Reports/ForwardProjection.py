from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af
import DataGeneration as df

class ForwardProjectionReport(BaseReport):

    def generate(self, output_filename: str, data, report_args: dict[str,str] = dict()):
        print("Generating Forward Projection Report")
        if report_args.get("fwd_periods") is None:
            raise ValueError("fwd_periods argument is required for Forward Projection Report")
        
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

        # project forward
        proj_return_itd_daily = daily_summary['ITD Portfolio Return %'].iloc[-1] / 100.0
        proj_1y_return_daily = (((daily_summary['Portfolio Return %'].rolling(window=260 * 1).apply(lambda x: ((1 + x / 100).cumprod().iloc[-1] - 1)).iloc[-1]) + 1.0) ** (1/(260*1))) - 1.0
        proj_3y_return_daily = (((daily_summary['Portfolio Return %'].rolling(window=260 * 3).apply(lambda x: ((1 + x / 100).cumprod().iloc[-1] - 1)).iloc[-1]) + 1.0) ** (1/(260*3))) - 1.0
        proj_5y_return_daily = (((daily_summary['Portfolio Return %'].rolling(window=260 * 5).apply(lambda x: ((1 + x / 100).cumprod().iloc[-1] - 1)).iloc[-1]) + 1.0) ** (1/(260*5))) - 1.0

        first_date = np.datetime64(daily_summary['Settle date'].min(), 'D')
        last_date = np.datetime64(daily_summary['Settle date'].max(), 'D')
        last_market_value = daily_summary['Market value'].iloc[-1]

        proj_return_itd_daily = ((1 + proj_return_itd_daily) ** (1 / np.busday_count(first_date, last_date))) - 1

        fwd_periods = int(report_args["fwd_periods"])

        print(f'Projecting forward {fwd_periods} business days using ITD daily return of {proj_return_itd_daily:.6f}%, 1Y={proj_1y_return_daily:.6f}, 3Y={proj_3y_return_daily:.6f}, 5Y={proj_5y_return_daily:.6f} and a last market value of {last_market_value:.2f} on {last_date}')

        projection = df.create_date_series(last_date + np.timedelta64(1, 'D'), last_date + np.timedelta64(report_args["fwd_periods"], 'D'))
        projection['Proj. Market Value (ITD)'] = last_market_value * (1 + proj_return_itd_daily) ** np.busday_count(last_date, projection['Settle date'].values.astype('datetime64[D]'))
        projection['Proj. Market Value (1Y)'] = last_market_value * (1 + proj_1y_return_daily) ** np.busday_count(last_date, projection['Settle date'].values.astype('datetime64[D]'))
        projection['Proj. Market Value (3Y)'] = last_market_value * (1 + proj_3y_return_daily) ** np.busday_count(last_date, projection['Settle date'].values.astype('datetime64[D]'))
        projection['Proj. Market Value (5Y)'] = last_market_value * (1 + proj_5y_return_daily) ** np.busday_count(last_date, projection['Settle date'].values.astype('datetime64[D]'))

        # union results together
        daily_summary = pd.concat([daily_summary, projection], axis=0, ignore_index=True, sort=True)

        # summarize if requested
        if report_args.get("periodicity") is not None:
            periodicity = str(report_args.get("periodicity"))
            daily_summary = daily_summary.groupby(pd.Grouper(key='Settle date', freq=periodicity)).agg(
                Total_Book_Cost=('Book cost', 'last'),
                Total_Capital=('Capital', 'last'),
                Close_Market_Value=('Market value', 'last'),
                Proj_Market_Value_ITD=('Proj. Market Value (ITD)', 'last'),
                Proj_Market_Value_1Y=('Proj. Market Value (1Y)', 'last'),
                Proj_Market_Value_3Y=('Proj. Market Value (3Y)', 'last'),
                Proj_Market_Value_5Y=('Proj. Market Value (5Y)', 'last')
            ).reset_index()

            daily_summary = daily_summary.rename(columns={
                                                'Total_Book_Cost': 'Book cost', 
                                                'Total_Capital': 'Capital',
                                                'Close_Market_Value': 'Market value',
                                                'Proj_Market_Value_ITD': 'Proj. Market Value (ITD)',
                                                'Proj_Market_Value_1Y': 'Proj. Market Value (1Y)',
                                                'Proj_Market_Value_3Y': 'Proj. Market Value (3Y)',
                                                'Proj_Market_Value_5Y': 'Proj. Market Value (5Y)'
                                                }
                                            )

        # === Format and save as CSV ===
        daily_summary = daily_summary[['Settle date', 'Capital', 'Book cost', 'Market value','Proj. Market Value (ITD)', 'Proj. Market Value (1Y)', 'Proj. Market Value (3Y)', 'Proj. Market Value (5Y)']].sort_values(by='Settle date')
        daily_summary.to_excel(output_filename, index=False)

        # === Format and save as visual ===
        
        return
    
    def required_measures(self) -> list[str]:
        return ["ITD PnL", "Daily Return %", "Weight %"]
    
    def report_name(self) -> str:
        return "ForwardProjectionReport"