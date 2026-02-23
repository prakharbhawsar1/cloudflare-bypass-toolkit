"""
Cloudflare bypass strategy using Microsoft Playwright.

Launches a real Chromium browser, fully executes JavaScript, and waits for
Cloudflare challenges (IUAM, Turnstile) to resolve automatically.
More reliable than HTTP-level strategies for complex challenges.

Install:  pip install playwright && playwright install chromium
"""

import time
from typing import TYPE_CHECKING, Optional

try:
    from playwright.sync_api import (  # type: ignore[import]
        Browser,
        BrowserContext,
        Page,
        sync_playwright,
    )

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

from ..exceptions import StrategyError
from ..models.config import BypassConfig, StrategyType
from ..models.result import BypassResult
from .base import BaseBypassStrategy

# Cloudflare challenge page fingerprints
_CF_INDICATORS = frozenset(
    [
        "just a moment",
        "checking your browser",
        "cf-browser-verification",
        "ray id",
    ]
)

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# JS injected before page load to mask automation signals
_STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    window.chrome = { runtime: {} };
"""


class PlaywrightStrategy(BaseBypassStrategy):
    """
    Browser-level Cloudflare bypass using Playwright (Chromium).

    Handles JavaScript challenges and Turnstile by waiting for them to
    auto-resolve.  Persists cookies from a successful session into the
    :class:`SessionManager` for subsequent requests.
    """

    @property
    def name(self) -> str:
        return StrategyType.PLAYWRIGHT.value

    def is_available(self) -> bool:
        return _PLAYWRIGHT_AVAILABLE

    # ------------------------------------------------------------------

    def fetch(self, url: str, **kwargs: object) -> BypassResult:
        if not self.is_available():
            raise StrategyError(
                "playwright is not installed. "
                "Run: pip install playwright && playwright install chromium"
            )

        start = time.monotonic()

        for attempt in range(1, self._config.max_retries + 1):
            self._log_attempt(url, attempt)
            try:
                result = self._fetch_with_browser(url, attempt, start)
                return result
            except StrategyError:
                raise
            except Exception as exc:
                self._log_failure(url, str(exc), attempt)
                if attempt < self._config.max_retries:
                    time.sleep(self._config.delay_between_retries)
                else:
                    raise StrategyError(
                        f"Playwright exhausted {attempt} attempts for {url}: {exc}"
                    ) from exc

        raise StrategyError("Playwright: unreachable sentinel")  # pragma: no cover

    # ------------------------------------------------------------------

    def _fetch_with_browser(self, url: str, attempt: int, start: float) -> BypassResult:
        with sync_playwright() as p:
            launch_kwargs: dict = {
                "headless": self._config.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            }
            if self._config.proxy:
                launch_kwargs["proxy"] = {"server": self._config.proxy.url}
                if self._config.proxy.username:
                    launch_kwargs["proxy"]["username"] = self._config.proxy.username
                    launch_kwargs["proxy"]["password"] = self._config.proxy.password or ""

            browser: Browser = p.chromium.launch(**launch_kwargs)

            context: BrowserContext = browser.new_context(
                user_agent=self._config.user_agent or _DEFAULT_UA,
                viewport={"width": 1920, "height": 1080},
                java_script_enabled=True,
                ignore_https_errors=not self._config.verify_ssl,
            )
            context.add_init_script(_STEALTH_SCRIPT)

            page: Page = context.new_page()

            try:
                response = page.goto(
                    url,
                    timeout=self._config.timeout * 1_000,
                    wait_until="networkidle",
                )

                self._wait_for_challenge(page)

                content = page.content().encode("utf-8")
                status_code = response.status if response else 200
                headers = dict(response.all_headers()) if response else {}
                cookies = {c["name"]: c["value"] for c in context.cookies()}

                elapsed = time.monotonic() - start
                self._log_success(url, status_code, elapsed)

                return BypassResult(
                    url=url,
                    status_code=status_code,
                    content=content,
                    headers=headers,
                    strategy_used=StrategyType.PLAYWRIGHT,
                    attempt_count=attempt,
                    elapsed_seconds=elapsed,
                    cookies=cookies,
                )
            finally:
                context.close()
                browser.close()

    def _wait_for_challenge(self, page: "Page", max_wait: int = 15) -> None:
        """Poll until the CF challenge page is gone or max_wait seconds pass."""
        waited = 0
        while waited < max_wait:
            lower = (page.title() + page.content()).lower()
            if not any(indicator in lower for indicator in _CF_INDICATORS):
                return
            self._logger.debug("waiting_for_cf_challenge", waited_seconds=waited)
            page.wait_for_timeout(1_000)
            waited += 1

        self._logger.warning("cf_challenge_timeout", max_wait=max_wait)
