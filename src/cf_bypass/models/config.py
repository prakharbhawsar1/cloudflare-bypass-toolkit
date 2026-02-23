"""Configuration models for cf-bypass-toolkit."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    """Available Cloudflare bypass strategies, ordered by speed (fastest first)."""

    CLOUDSCRAPER = "cloudscraper"
    PLAYWRIGHT = "playwright"
    UNDETECTED = "undetected"


class ProxyConfig(BaseModel):
    """Proxy server configuration."""

    host: str
    port: int = Field(ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"

    @property
    def url(self) -> str:
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"


class BypassConfig(BaseModel):
    """
    Global configuration for the BypassEngine.

    Attributes:
        strategies:              Ordered list of strategies to try (first = highest priority).
        max_retries:             How many times each strategy retries before giving up.
        timeout:                 Per-request timeout in seconds.
        headless:                Run browser-based strategies in headless mode.
        session_dir:             Directory where bypass sessions (cookies) are persisted.
        proxy:                   Optional proxy server to route traffic through.
        user_agent:              Override the default User-Agent header.
        verify_ssl:              Verify SSL certificates (disable only for testing).
        delay_between_retries:   Seconds to wait between retry attempts.
    """

    strategies: list[StrategyType] = Field(
        default=[
            StrategyType.CLOUDSCRAPER,
            StrategyType.PLAYWRIGHT,
            StrategyType.UNDETECTED,
        ]
    )
    max_retries: int = Field(default=3, ge=1, le=10)
    timeout: int = Field(default=30, ge=5, le=120)
    headless: bool = True
    session_dir: str = ".cf_sessions"
    proxy: Optional[ProxyConfig] = None
    user_agent: Optional[str] = None
    verify_ssl: bool = True
    delay_between_retries: float = Field(default=2.0, ge=0.0, le=30.0)
