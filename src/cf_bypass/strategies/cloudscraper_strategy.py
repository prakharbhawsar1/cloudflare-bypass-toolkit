"""
Cloudflare bypass strategy using the `cloudscraper` library.

Operates entirely at the HTTP layer (no real browser).
Fastest strategy; works against CF Anti-Bot Page (JS IUAM) and basic bot
detection.  Falls through to browser-based strategies when a Turnstile /
CAPTCHA challenge is served.
"""

import time
from typing import Optional

try:
    import cloudscraper  # type: ignore[import]

    _CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    _CLOUDSCRAPER_AVAILABLE = False

from ..exceptions import StrategyError
from ..models.config import BypassConfig, StrategyType
from ..models.result import BypassResult
from .base import BaseBypassStrategy


class CloudScraperStrategy(BaseBypassStrategy):
    """
    HTTP-level Cloudflare bypass via *cloudscraper*.

    Mimics a real browser's TLS fingerprint and solves lightweight
    JavaScript challenges without launching a browser process.
    """

    def __init__(self, config: BypassConfig) -> None:
        super().__init__(config)
        self._scraper: Optional[object] = None  # lazy-init

    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return StrategyType.CLOUDSCRAPER.value

    def is_available(self) -> bool:
        return _CLOUDSCRAPER_AVAILABLE

    # ------------------------------------------------------------------

    def fetch(self, url: str, **kwargs: object) -> BypassResult:
        if not self.is_available():
            raise StrategyError(
                "cloudscraper is not installed. "
                "Run: pip install cloudscraper"
            )

        start = time.monotonic()

        for attempt in range(1, self._config.max_retries + 1):
            self._log_attempt(url, attempt)
            try:
                scraper = self._get_scraper()
                response = scraper.get(  # type: ignore[union-attr]
                    url,
                    timeout=self._config.timeout,
                    verify=self._config.verify_ssl,
                    **kwargs,
                )
                elapsed = time.monotonic() - start
                self._log_success(url, response.status_code, elapsed)

                return BypassResult(
                    url=url,
                    status_code=response.status_code,
                    content=response.content,
                    headers=dict(response.headers),
                    strategy_used=StrategyType.CLOUDSCRAPER,
                    attempt_count=attempt,
                    elapsed_seconds=elapsed,
                    cookies=dict(response.cookies),
                )

            except Exception as exc:
                self._log_failure(url, str(exc), attempt)
                if attempt < self._config.max_retries:
                    time.sleep(self._config.delay_between_retries)
                else:
                    raise StrategyError(
                        f"CloudScraper exhausted {attempt} attempts for {url}: {exc}"
                    ) from exc

        raise StrategyError("CloudScraper: unreachable sentinel")  # pragma: no cover

    # ------------------------------------------------------------------

    def _get_scraper(self) -> object:
        """Lazily create and cache a CloudScraper session."""
        if self._scraper is None:
            self._scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False},
                delay=5,
            )
            if self._config.proxy:
                proxy_url = self._config.proxy.url
                self._scraper.proxies.update({"http": proxy_url, "https": proxy_url})  # type: ignore[union-attr]

            if self._config.user_agent:
                self._scraper.headers.update({"User-Agent": self._config.user_agent})  # type: ignore[union-attr]

        return self._scraper
