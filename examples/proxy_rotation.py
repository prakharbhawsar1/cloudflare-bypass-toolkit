"""
Proxy rotation – cycle through a pool of proxies per request.

Replace the PROXY_POOL list with your actual proxy addresses.

Run:
    python examples/proxy_rotation.py
"""

import itertools

from cf_bypass import BypassEngine, BypassConfig, configure_logging
from cf_bypass.models.config import ProxyConfig, StrategyType


# Replace with real proxies: (host, port, user, password)
PROXY_POOL = [
    ("proxy1.example.com", 8080, "user", "pass"),
    ("proxy2.example.com", 8080, "user", "pass"),
    ("proxy3.example.com", 8080, "user", "pass"),
]

TARGETS = [
    "https://httpbin.org/ip",
    "https://httpbin.org/get",
]


def main() -> None:
    configure_logging()

    proxy_cycle = itertools.cycle(PROXY_POOL)

    for url in TARGETS:
        host, port, user, pwd = next(proxy_cycle)

        config = BypassConfig(
            strategies=[StrategyType.CLOUDSCRAPER, StrategyType.PLAYWRIGHT],
            proxy=ProxyConfig(host=host, port=port, username=user, password=pwd),
            max_retries=2,
        )
        engine = BypassEngine(config)

        try:
            result = engine.fetch(url)
            print(f"[{result.status_code}] {url} via {host}:{port}")
        except Exception as exc:
            print(f"[FAIL] {url} via {host}:{port} → {exc}")


if __name__ == "__main__":
    main()
