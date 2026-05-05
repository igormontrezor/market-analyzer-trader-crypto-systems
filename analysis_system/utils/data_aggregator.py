from dataclasses import dataclass, field
from typing import Optional
import pandas as pd

@dataclass
class DataAggregator:
    data: Optional[pd.DataFrame] = None

    def add(self, series: pd.Series, name: str):
        series = series.rename(name)
        if self.data is None:
            self.data = series.to_frame()
        elif name in self.data.columns:
            return
        else:
            self.data = self.data.join(series, how="outer")
        return self.data.fillna(0, inplace=True)

    def get(self):
        return self.data.sort_index() if self.data is not None else pd.DataFrame()
