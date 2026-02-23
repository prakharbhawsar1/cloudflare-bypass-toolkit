"""
Concurrent fetching – use a thread pool to bypass multiple URLs in parallel.

Browser-based strategies block on I/O, so threading gives real parallelism
here (unlike CPU-bound work where the GIL would be a bottleneck).

Run:
    python examples/concurrent_fetch.py
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

from cf_bypass import BypassEngine, BypassConfig, configure_logging
from cf_bypass.models.config import StrategyType


URLS = [
    "https://httpbin.org/get",
    "https://httpbin.org/ip",
    "https://httpbin.org/headers",
    "https://httpbin.org/user-agent",
]


def fetch_one(engine: BypassEngine, url: str) -> tuple[str, int, float]:
    result = engine.fetch(url)
    return url, result.status_code, result.elapsed_seconds


def main() -> None:
    configure_logging(level="INFO")

    config = BypassConfig(
        strategies=[StrategyType.CLOUDSCRAPER],
        max_retries=2,
    )
    engine = BypassEngine(config)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_one, engine, url): url for url in URLS}

        for future in as_completed(futures):
            try:
                url, status, elapsed = future.result()
                print(f"[{status}] {url}  ({elapsed:.2f}s)")
            except Exception as exc:
                print(f"[ERROR] {futures[future]}: {exc}")


if __name__ == "__main__":
    main()
