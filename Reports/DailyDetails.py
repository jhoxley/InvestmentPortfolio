from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af

class DailyDetailsReport(BaseReport):

    def generate(self, output_filename: str, data):
        print("Generating Daily Details Report")
        
        # === Generate raw data for this report ===

        # (1) calculate the weighted, daily return for each position
        data['Portfolio Return %'] = data['Daily Return %'] * (data['Weight %'] / 100)

        # (3) calculate composite returns (ITD, 1Y, 3Y, 5Y, Ann. ITD) for each position
        daily_details = af.calculate_composite_returns(data)
        
        # === Format and save as CSV ===
        daily_details.to_excel(output_filename, index=False)

        # === Format and save as visual ===
        
        return
    
    def required_measures(self) -> list[str]:
        return ["ITD PnL", "Daily Return %", "Weight %"]
    
    def get_report_name(self) -> str:
        return "DailyDetailsReport"