"""Custom exceptions for cf-bypass-toolkit."""


class CFBypassError(Exception):
    """Base exception for all Cloudflare bypass errors."""


class AllStrategiesFailedError(CFBypassError):
    """Raised when every configured bypass strategy has been exhausted."""


class StrategyError(CFBypassError):
    """Raised when a specific bypass strategy fails."""


class SessionExpiredError(CFBypassError):
    """Raised when a stored bypass session/cookie set has expired."""


class ProxyError(CFBypassError):
    """Raised when a proxy connection cannot be established."""


class ConfigurationError(CFBypassError):
    """Raised when the bypass configuration is invalid."""
