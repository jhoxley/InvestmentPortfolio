from .PeriodicSummaryBase import PeriodicSummaryBase

class MonthlySummaryReport(PeriodicSummaryBase):

    def get_periodicity(self) -> str:
        return "ME"
        
    def report_name(self) -> str:
        return "MonthlySummaryReport"