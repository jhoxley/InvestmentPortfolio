from abc import ABC, abstractmethod
from typing import List

class BaseReport(ABC):
    @abstractmethod
    def generate(self, output_filename: str, data, report_args: dict = dict()):
        pass

    def report_name(self) -> str:
        return self.__class__.__name__

    @abstractmethod    
    def required_measures(self) -> List[str]:
        return []