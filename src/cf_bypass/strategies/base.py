"""Abstract base class that every bypass strategy must implement."""

from abc import ABC, abstractmethod

import structlog

from ..models.config import BypassConfig
from ..models.result import BypassResult


class BaseBypassStrategy(ABC):
    """
    Interface (ISP / DIP) for a single Cloudflare bypass strategy.

    Concrete implementations must override `name`, `is_available`, and `fetch`.
    The engine uses `is_available()` at startup to skip strategies whose
    dependencies are not installed, so no ImportError ever reaches the caller.
    """

    def __init__(self, config: BypassConfig) -> None:
        self._config = config
        self._logger: structlog.BoundLogger = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique human-readable identifier for this strategy."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True if this strategy's required third-party packages are
        installed and the strategy can be used immediately.
        """
        ...

    @abstractmethod
    def fetch(self, url: str, **kwargs: object) -> BypassResult:
        """
        Attempt to fetch *url* while bypassing Cloudflare protection.

        Args:
            url:     Target URL.
            **kwargs: Extra parameters forwarded to the underlying HTTP client.

        Returns:
            A populated :class:`BypassResult`.

        Raises:
            :class:`~cf_bypass.exceptions.StrategyError`: Strategy exhausted all retries.
        """
        ...

    # ------------------------------------------------------------------
    # Shared logging helpers (template method pattern)
    # ------------------------------------------------------------------

    def _log_attempt(self, url: str, attempt: int) -> None:
        self._logger.debug(
            "strategy_attempt",
            strategy=self.name,
            url=url,
            attempt=attempt,
            max_retries=self._config.max_retries,
        )

    def _log_success(self, url: str, status_code: int, elapsed: float) -> None:
        self._logger.info(
            "strategy_success",
            strategy=self.name,
            url=url,
            status_code=status_code,
            elapsed_seconds=round(elapsed, 3),
        )

    def _log_failure(self, url: str, error: str, attempt: int) -> None:
        self._logger.warning(
            "strategy_attempt_failed",
            strategy=self.name,
            url=url,
            attempt=attempt,
            error=error,
        )
