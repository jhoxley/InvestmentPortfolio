from .BaseReport import BaseReport
import pandas as pd
import numpy as np
import AnalysisFuncs as af

class MultiReport(BaseReport):

    #create a constructor that takes a list of BaseReport objects
    def __init__(self, reports: list[BaseReport]):
        self.reports = reports

    def generate(self, output_filename: str, data, report_args: dict = dict()):
        print("Generating Multi Report")
        
        for report in self.reports:
            report_filename = output_filename.replace(".xlsx", f"_{report.report_name()}.xlsx")
            report.generate(report_filename, data, report_args)
        
        return
    
    def required_measures(self) -> list[str]:
        measures = set()
        for report in self.reports:
            measures.update(report.required_measures())
        return list(measures)
    
    def get_report_name(self) -> str:
        return "MultiReport: " + ", ".join([report.report_name() for report in self.reports])