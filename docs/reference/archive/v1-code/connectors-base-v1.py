"""Base connector interface for SONAR data sources.

Every connector implementation (FRED, ECB SDW, IGCP, etc.) must subclass
:class:`BaseConnector` and implement the abstract methods.

The connector lifecycle is:
    1. ``__init__`` — configure with credentials/options from settings
    2. ``fetch`` — retrieve data from external source (async)
    3. ``validate`` — check data quality, return warning flags
    4. ``store`` — persist to database, return rows affected

Connectors should:
    - Be stateless between calls (idempotent)
    - Respect external rate limits
    - Log structured events at INFO level for each fetch
    - Raise specific ``SONARError`` subclasses on failure
    - Never log sensitive credentials

Example:
    >>> from sonar.connectors.fred import FREDConnector
    >>> connector = FREDConnector(settings)
    >>> result = await connector.fetch(series_id="DGS10", start=date(2026, 1, 1))
    >>> warnings = connector.validate(result)
    >>> rows = connector.store(result)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

from sonar.exceptions import (
    ConfigurationError,
    DataUnavailableError,
    ExternalServiceError,
)
from sonar.settings import Settings

logger = structlog.get_logger(__name__)


class DataTier(int, Enum):
    """Tier classification for data sources.

    Tier 1: Free, MVP essential (FRED, ECB SDW, etc.)
    Tier 2: Enhanced coverage (Trading Economics, FactSet)
    Tier 3: Professional (Bloomberg, Refinitiv)
    Tier 4: Experimental / specialized
    """

    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4


class FetchStatus(str, Enum):
    """Status of a fetch operation."""

    SUCCESS = "success"
    PARTIAL = "partial"          # some data, with warnings
    FAILED = "failed"
    STALE = "stale"              # data too old to be useful


class FetchResult(BaseModel):
    """Structured result of a connector fetch.

    Attributes:
        data: The actual data payload. Format is connector-specific
            but should be a dict with meaningful keys.
        source: Connector name (e.g. "fred", "ecb_sdw").
        fetched_at: When we retrieved the data (UTC).
        data_as_of: Date the data refers to (from the source).
        status: Overall fetch status.
        confidence: Quality score 0-1.
        warnings: Human-readable quality flags.
        metadata: Additional source-specific context (URL, request params, etc.).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    data: dict[str, Any]
    source: str
    fetched_at: datetime
    data_as_of: date | None = None
    status: FetchStatus = FetchStatus.SUCCESS
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass
class StoreResult:
    """Result of persisting a fetch to the database."""

    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    table: str

    @property
    def total(self) -> int:
        return self.rows_inserted + self.rows_updated + self.rows_skipped


class BaseConnector(ABC):
    """Abstract base class for SONAR data connectors.

    Subclasses must:
        - Set class attributes ``name`` and ``tier``
        - Implement ``fetch``, ``validate``, ``store``
        - Use structured logging throughout
        - Respect source rate limits via ``_throttle``

    Subclasses should:
        - Override ``_build_client`` if needing custom HTTP config
        - Override ``__init__`` if needing additional configuration
    """

    # Subclasses MUST override these
    name: str
    tier: DataTier
    base_url: str | None = None
    description: str = ""

    def __init__(self, settings: Settings) -> None:
        """Initialize connector with SONAR settings.

        Args:
            settings: Application settings including credentials.

        Raises:
            ConfigurationError: If required credentials are missing.
        """
        if not self.name:
            raise ConfigurationError(
                f"Connector {self.__class__.__name__} must define class attribute 'name'"
            )
        if not self.tier:
            raise ConfigurationError(
                f"Connector {self.__class__.__name__} must define class attribute 'tier'"
            )

        self.settings = settings
        self.logger = structlog.get_logger(f"connector.{self.name}")
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate connector-specific configuration.

        Subclasses should override to check their required credentials.
        Raise ConfigurationError if invalid.
        """

    # ------------------------------------------------------------------------
    # Abstract methods — subclasses MUST implement
    # ------------------------------------------------------------------------

    @abstractmethod
    async def fetch(self, **kwargs: Any) -> FetchResult:
        """Fetch data from the external source.

        Args:
            **kwargs: Connector-specific parameters (series_id, date range, etc.)

        Returns:
            FetchResult with data and metadata.

        Raises:
            DataUnavailableError: Source returned no data for the request.
            ExternalServiceError: Source is unreachable or errored.
        """

    @abstractmethod
    def validate(self, result: FetchResult) -> list[str]:
        """Validate fetched data quality.

        Args:
            result: Fetched data from :meth:`fetch`.

        Returns:
            List of warning flags. Empty list = no issues.
            Common flags:
                - "STALE": data older than expected
                - "OUT_OF_RANGE": values outside historical norms
                - "INCOMPLETE": some fields missing
                - "CROSS_VALIDATION_FAIL": divergence from reference
        """

    @abstractmethod
    def store(self, result: FetchResult) -> StoreResult:
        """Persist fetched data to the database.

        Args:
            result: Validated fetch result.

        Returns:
            StoreResult with row counts.

        Raises:
            DatabaseError: If persistence fails.
        """

    # ------------------------------------------------------------------------
    # Common helpers — available to all subclasses
    # ------------------------------------------------------------------------

    async def fetch_validate_store(self, **kwargs: Any) -> StoreResult:
        """Full lifecycle: fetch + validate + store.

        Convenience method. Subclasses should usually not override.
        """
        self.logger.info("connector_fetch_start", **kwargs)

        try:
            result = await self.fetch(**kwargs)
        except (DataUnavailableError, ExternalServiceError):
            self.logger.exception("connector_fetch_failed", **kwargs)
            raise

        warnings = self.validate(result)
        if warnings:
            self.logger.warning(
                "connector_validation_warnings",
                warnings=warnings,
                source=self.name,
                data_as_of=str(result.data_as_of),
            )

        store_result = self.store(result)
        self.logger.info(
            "connector_fetch_complete",
            source=self.name,
            rows_inserted=store_result.rows_inserted,
            rows_updated=store_result.rows_updated,
            warnings_count=len(warnings),
        )
        return store_result

    def _throttle(self, seconds: float = 1.0) -> None:
        """Rate limit helper. Override in subclass for more sophisticated logic."""
        import time
        time.sleep(seconds)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} tier={self.tier.value}>"


# ===========================================================================
# Example skeleton for a new connector
# ===========================================================================
# Copy this as a starting point for a new connector implementation.
#
#
# from sonar.connectors.base import BaseConnector, DataTier, FetchResult, StoreResult
# from sonar.exceptions import DataUnavailableError, ExternalServiceError
# import httpx
#
#
# class ExampleConnector(BaseConnector):
#     """Connector for Example Data Source.
#
#     Source URL: https://example.com/api
#     Rate limits: 100 req/min
#     Authentication: API key in header
#     """
#
#     name = "example"
#     tier = DataTier.ONE
#     base_url = "https://example.com/api/v1"
#     description = "Example external data source"
#
#     def _validate_config(self) -> None:
#         if not self.settings.example_api_key:
#             raise ConfigurationError(
#                 "EXAMPLE_API_KEY not set — required for ExampleConnector"
#             )
#
#     async def fetch(self, *, series_id: str, **kwargs: Any) -> FetchResult:
#         headers = {"X-API-Key": self.settings.example_api_key.get_secret_value()}
#         url = f"{self.base_url}/series/{series_id}"
#
#         async with httpx.AsyncClient(timeout=30.0) as client:
#             try:
#                 response = await client.get(url, headers=headers)
#                 response.raise_for_status()
#             except httpx.HTTPStatusError as e:
#                 if e.response.status_code == 404:
#                     raise DataUnavailableError(
#                         f"Series {series_id} not found at example.com"
#                     ) from e
#                 raise ExternalServiceError(f"Example API returned {e.response.status_code}") from e
#             except httpx.RequestError as e:
#                 raise ExternalServiceError(f"Example API unreachable: {e}") from e
#
#         payload = response.json()
#         return FetchResult(
#             data=payload,
#             source=self.name,
#             fetched_at=datetime.now(tz=UTC),
#             data_as_of=date.fromisoformat(payload["as_of"]),
#             confidence=1.0,
#             metadata={"url": str(url), "status_code": response.status_code},
#         )
#
#     def validate(self, result: FetchResult) -> list[str]:
#         warnings = []
#         if not result.data.get("values"):
#             warnings.append("INCOMPLETE")
#         if result.data_as_of and (date.today() - result.data_as_of).days > 7:
#             warnings.append("STALE")
#         return warnings
#
#     def store(self, result: FetchResult) -> StoreResult:
#         # Implement DB persistence
#         ...
