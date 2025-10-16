from .PeriodicSummaryBase import PeriodicSummaryBase

class AnnualSummaryReport(PeriodicSummaryBase):

    def get_periodicity(self) -> str:
        return "YE"
        
    def report_name(self) -> str:
        return "AnnualSummaryReport"