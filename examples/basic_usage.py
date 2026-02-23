"""
Basic usage – fetch a Cloudflare-protected URL with automatic strategy fallback.

Run:
    python examples/basic_usage.py
"""

from cf_bypass import BypassEngine, configure_logging


def main() -> None:
    configure_logging(level="INFO")

    engine = BypassEngine()
    print(f"Loaded strategies: {engine.available_strategies}\n")

    result = engine.fetch("https://httpbin.org/get")

    print(f"Status  : {result.status_code}")
    print(f"Strategy: {result.strategy_used}")
    print(f"Elapsed : {result.elapsed_seconds:.2f}s")
    print(f"Body    : {result.text[:300]}")


if __name__ == "__main__":
    main()
