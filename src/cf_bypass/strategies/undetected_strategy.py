"""
Cloudflare bypass strategy using undetected-chromedriver (UC).

Patches the ChromeDriver binary at the byte level so automation flags are
invisible to Cloudflare's bot detection.  Most robust strategy for complex
challenges including Turnstile and hCaptcha (when solving is not required).

Install:  pip install undetected-chromedriver
"""

import time
from typing import Optional

try:
    import undetected_chromedriver as uc  # type: ignore[import]

    _UC_AVAILABLE = True
except ImportError:
    _UC_AVAILABLE = False

from ..exceptions import StrategyError
from ..models.config import BypassConfig, StrategyType
from ..models.result import BypassResult
from .base import BaseBypassStrategy

_CF_TITLE_TRIGGERS = ("just a moment", "cloudflare", "checking your browser")


class UndetectedChromeStrategy(BaseBypassStrategy):
    """
    Browser-level Cloudflare bypass via a patched ChromeDriver.

    Unlike Playwright, the UC driver patches the Chrome binary itself, making
    it the hardest strategy to detect.  Preferred when simpler strategies fail.
    """

    @property
    def name(self) -> str:
        return StrategyType.UNDETECTED.value

    def is_available(self) -> bool:
        return _UC_AVAILABLE

    # ------------------------------------------------------------------

    def fetch(self, url: str, **kwargs: object) -> BypassResult:
        if not self.is_available():
            raise StrategyError(
                "undetected-chromedriver is not installed. "
                "Run: pip install undetected-chromedriver"
            )

        start = time.monotonic()

        for attempt in range(1, self._config.max_retries + 1):
            self._log_attempt(url, attempt)
            driver: Optional[object] = None
            try:
                driver = self._build_driver()
                driver.set_page_load_timeout(self._config.timeout)  # type: ignore[union-attr]
                driver.get(url)  # type: ignore[union-attr]

                self._wait_for_challenge(driver)

                content = driver.page_source.encode("utf-8")  # type: ignore[union-attr]
                cookies = {c["name"]: c["value"] for c in driver.get_cookies()}  # type: ignore[union-attr]

                elapsed = time.monotonic() - start
                self._log_success(url, 200, elapsed)  # UC doesn't expose HTTP status

                return BypassResult(
                    url=url,
                    status_code=200,
                    content=content,
                    headers={},
                    strategy_used=StrategyType.UNDETECTED,
                    attempt_count=attempt,
                    elapsed_seconds=elapsed,
                    cookies=cookies,
                )

            except StrategyError:
                raise
            except Exception as exc:
                self._log_failure(url, str(exc), attempt)
                if attempt < self._config.max_retries:
                    time.sleep(self._config.delay_between_retries)
                else:
                    raise StrategyError(
                        f"UndetectedChrome exhausted {attempt} attempts for {url}: {exc}"
                    ) from exc
            finally:
                if driver is not None:
                    try:
                        driver.quit()  # type: ignore[union-attr]
                    except Exception:
                        pass

        raise StrategyError("UndetectedChrome: unreachable sentinel")  # pragma: no cover

    # ------------------------------------------------------------------

    def _build_driver(self) -> object:
        options = uc.ChromeOptions()

        if self._config.headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")

        if self._config.user_agent:
            options.add_argument(f"--user-agent={self._config.user_agent}")

        if self._config.proxy:
            options.add_argument(f"--proxy-server={self._config.proxy.url}")

        return uc.Chrome(options=options, version_main=None)

    def _wait_for_challenge(self, driver: object, max_wait: int = 15) -> None:
        """Wait up to *max_wait* seconds for any CF challenge to auto-resolve."""
        for elapsed in range(max_wait):
            title = driver.title.lower()  # type: ignore[union-attr]
            if not any(trigger in title for trigger in _CF_TITLE_TRIGGERS):
                return
            self._logger.debug("waiting_for_uc_challenge", elapsed_seconds=elapsed)
            time.sleep(1)

        self._logger.warning("uc_challenge_timeout", max_wait=max_wait)
