from .PeriodicSummaryBase import PeriodicSummaryBase

class QuarterlySummaryReport(PeriodicSummaryBase):

    def get_periodicity(self) -> str:
        return "QE"
        
    def report_name(self) -> str:
        return "QuarterlySummaryReport"