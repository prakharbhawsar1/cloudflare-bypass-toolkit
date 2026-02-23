"""
BypassEngine – the central orchestrator for cf-bypass-toolkit.

Tries each configured strategy in priority order, falls through to the next
on failure, and raises AllStrategiesFailedError only when all are exhausted.
Persists successful sessions via SessionManager to avoid redundant challenges.
"""

from typing import Optional

import structlog

from ..exceptions import AllStrategiesFailedError, StrategyError
from ..models.config import BypassConfig, StrategyType
from ..models.result import BypassResult
from ..strategies.base import BaseBypassStrategy
from ..strategies.cloudscraper_strategy import CloudScraperStrategy
from ..strategies.playwright_strategy import PlaywrightStrategy
from ..strategies.undetected_strategy import UndetectedChromeStrategy
from .session_manager import SessionManager

logger = structlog.get_logger(__name__)

# Registry: StrategyType → concrete class (Open/Closed principle – add new
# strategies here without modifying the engine logic).
_STRATEGY_REGISTRY: dict[StrategyType, type[BaseBypassStrategy]] = {
    StrategyType.CLOUDSCRAPER: CloudScraperStrategy,
    StrategyType.PLAYWRIGHT: PlaywrightStrategy,
    StrategyType.UNDETECTED: UndetectedChromeStrategy,
}


class BypassEngine:
    """
    Orchestrates multiple Cloudflare bypass strategies with automatic fallback.

    Usage::

        engine = BypassEngine()
        result = engine.fetch("https://example.com")
        print(result.text)

    Custom config::

        from cf_bypass import BypassConfig, ProxyConfig, StrategyType

        config = BypassConfig(
            strategies=[StrategyType.PLAYWRIGHT, StrategyType.UNDETECTED],
            proxy=ProxyConfig(host="proxy.example.com", port=8080),
            headless=False,
        )
        engine = BypassEngine(config)
    """

    def __init__(
        self,
        config: Optional[BypassConfig] = None,
        session_manager: Optional[SessionManager] = None,
    ) -> None:
        self._config = config or BypassConfig()
        self._session_manager = session_manager or SessionManager(self._config.session_dir)
        self._strategies = self._initialise_strategies()
        self._log = structlog.get_logger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, url: str, use_cached_session: bool = True, **kwargs: object) -> BypassResult:
        """
        Fetch *url*, bypassing Cloudflare protection.

        Tries each strategy in the configured order.  On success, persists
        cookies via the SessionManager for future reuse.

        Args:
            url:                 Target URL.
            use_cached_session:  If True, inject stored cookies before fetching
                                 (not yet wired to all strategies – planned).
            **kwargs:            Forwarded to the underlying HTTP/browser client.

        Returns:
            :class:`BypassResult` with the full response.

        Raises:
            :class:`~cf_bypass.exceptions.AllStrategiesFailedError`: Every strategy failed.
        """
        self._log.info(
            "engine_fetch_start",
            url=url,
            strategies=[s.name for s in self._strategies],
        )

        errors: list[tuple[str, str]] = []

        for strategy in self._strategies:
            try:
                result = strategy.fetch(url, **kwargs)

                if result.cookies:
                    self._session_manager.save(url, result.cookies)

                self._log.info(
                    "engine_fetch_success",
                    url=url,
                    strategy=strategy.name,
                    status_code=result.status_code,
                    elapsed_seconds=round(result.elapsed_seconds, 3),
                )
                return result

            except StrategyError as exc:
                errors.append((strategy.name, str(exc)))
                self._log.warning(
                    "engine_strategy_exhausted",
                    strategy=strategy.name,
                    url=url,
                    error=str(exc),
                )

        error_detail = " | ".join(f"[{name}] {msg}" for name, msg in errors)
        raise AllStrategiesFailedError(
            f"All {len(self._strategies)} strategies failed for {url!r}. "
            f"Details: {error_detail}"
        )

    @property
    def available_strategies(self) -> list[str]:
        """Names of strategies that are installed and ready to use."""
        return [s.name for s in self._strategies]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _initialise_strategies(self) -> list[BaseBypassStrategy]:
        strategies: list[BaseBypassStrategy] = []

        for strategy_type in self._config.strategies:
            klass = _STRATEGY_REGISTRY.get(strategy_type)
            if klass is None:
                logger.warning("unknown_strategy_type", strategy=strategy_type)
                continue

            instance = klass(self._config)
            if instance.is_available():
                strategies.append(instance)
            else:
                logger.warning(
                    "strategy_dependencies_missing",
                    strategy=strategy_type.value,
                    hint=f"Install required package for '{strategy_type.value}'",
                )

        if not strategies:
            raise AllStrategiesFailedError(
                "No bypass strategies are available. "
                "Install at least one: cloudscraper, playwright, or undetected-chromedriver."
            )

        return strategies
