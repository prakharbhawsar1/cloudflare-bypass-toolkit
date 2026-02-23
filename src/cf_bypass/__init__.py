"""
cf-bypass-toolkit
=================

Production-grade Cloudflare protection bypass toolkit for Python 3.12+.

Supports three bypass strategies with automatic fallback:

1. **CloudScraper** – HTTP-level; fastest; no browser needed.
2. **Playwright**   – Headless Chromium; handles JS challenges and Turnstile.
3. **UndetectedChrome** – Patched ChromeDriver; most robust against detection.

Quick start::

    from cf_bypass import BypassEngine

    engine = BypassEngine()
    result = engine.fetch("https://example.com")
    print(result.status_code, result.text[:200])
"""

from .core.bypass_engine import BypassEngine
from .core.session_manager import SessionManager
from .exceptions import AllStrategiesFailedError, CFBypassError, StrategyError
from .models.config import BypassConfig, ProxyConfig, StrategyType
from .models.result import BypassResult
from .utils.logging import configure_logging, get_logger

__version__ = "1.0.0"
__author__ = "Prakhar Bhawsar"
__email__ = "prakhar1812.b@gmail.com"

__all__ = [
    # Core
    "BypassEngine",
    "SessionManager",
    # Config
    "BypassConfig",
    "ProxyConfig",
    "StrategyType",
    # Result
    "BypassResult",
    # Exceptions
    "CFBypassError",
    "AllStrategiesFailedError",
    "StrategyError",
    # Logging
    "configure_logging",
    "get_logger",
]
