"""BaseConnector ABC + Observation pydantic model for L0 data sources."""

from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel, Field


class Observation(BaseModel):
    country_code: str = Field(pattern=r"^[A-Z]{3}$")
    observation_date: date
    tenor_years: float = Field(gt=0, le=50)
    yield_bps: int
    source: str
    source_series_id: str


class BaseConnector(ABC):
    @abstractmethod
    async def fetch_series(self, series_id: str, start: date, end: date) -> list[Observation]: ...

    @abstractmethod
    async def aclose(self) -> None: ...
