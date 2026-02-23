"""Result model returned by every bypass strategy."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .config import StrategyType


@dataclass
class BypassResult:
    """
    Encapsulates the HTTP response returned by a successful bypass strategy.

    Attributes:
        url:             The URL that was fetched.
        status_code:     HTTP status code of the response.
        content:         Raw response body as bytes.
        headers:         Response headers as a plain dict.
        strategy_used:   Which strategy ultimately succeeded.
        attempt_count:   Total attempts made (across retries).
        elapsed_seconds: Wall-clock time from first attempt to success.
        timestamp:       UTC datetime when the response was received.
        cookies:         Cookies returned / required for the session.
    """

    url: str
    status_code: int
    content: bytes
    headers: dict[str, str]
    strategy_used: StrategyType
    attempt_count: int
    elapsed_seconds: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cookies: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def text(self) -> str:
        """Decode response body as UTF-8 text."""
        return self.content.decode("utf-8", errors="replace")

    @property
    def ok(self) -> bool:
        """True when the HTTP status code indicates success (2xx)."""
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        """Parse response body as JSON."""
        return json.loads(self.content)

    def __repr__(self) -> str:
        return (
            f"BypassResult(url={self.url!r}, status={self.status_code}, "
            f"strategy={self.strategy_used.value}, elapsed={self.elapsed_seconds:.2f}s)"
        )
