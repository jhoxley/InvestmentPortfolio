from .PeriodicSummaryBase import PeriodicSummaryBase

class QuarterlySummaryReport(PeriodicSummaryBase):

    def get_periodicity(self) -> str:
        return "QE"
        
    def get_report_name(self) -> str:
        return "QuarterlySummaryReport"