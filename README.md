# cf-bypass-toolkit

> Production-grade Cloudflare protection bypass toolkit for Python 3.12+

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)
![Linting](https://img.shields.io/badge/linting-ruff-orange.svg)

A modular, extensible toolkit for programmatically accessing Cloudflare-protected endpoints. Built with the **Strategy Pattern**, it automatically falls through to stronger bypass methods when lighter ones are insufficient — with zero changes to calling code.

---

## Features

- **Three bypass strategies** — HTTP-level, Playwright browser, and patched ChromeDriver
- **Automatic fallback** — tries each strategy in priority order until one succeeds
- **Session persistence** — stores clearance cookies to disk; skips the challenge on repeat visits
- **Proxy support** — per-request proxy config with optional credentials
- **Structured logging** — `structlog` JSON output ready for log aggregators (Datadog, Loki, etc.)
- **Pydantic v2 config** — type-safe, validated configuration
- **Full test suite** — unit-tested with `pytest`; strategies mocked at the network boundary
- **SOLID architecture** — new strategies plug in without touching existing code

---

## Architecture

```
cf_bypass/
├── core/
│   ├── bypass_engine.py      # Orchestrator — tries strategies, handles fallback
│   └── session_manager.py    # Cookie persistence (SHA-256 keyed JSON files)
├── strategies/
│   ├── base.py               # Abstract interface (Liskov / ISP)
│   ├── cloudscraper_strategy.py   # HTTP-level; fastest; no browser
│   ├── playwright_strategy.py     # Headless Chromium; handles Turnstile
│   └── undetected_strategy.py     # Patched ChromeDriver; most robust
├── models/
│   ├── config.py             # BypassConfig, ProxyConfig (Pydantic v2)
│   └── result.py             # BypassResult dataclass
├── utils/
│   └── logging.py            # structlog setup (TTY colour / JSON)
└── exceptions.py             # CFBypassError hierarchy
```

### Strategy fallback flow

```
engine.fetch(url)
       │
       ▼
 CloudScraper ──(fail)──► Playwright ──(fail)──► UndetectedChrome
       │                       │                        │
    success                 success                  success / AllStrategiesFailedError
       │                       │                        │
       └───────────────────────┴────────────────────────┘
                               │
                      BypassResult returned
                      cookies persisted to disk
```

| Strategy | Speed | Browser | Works against |
|---|---|---|---|
| CloudScraper | Fast | No | IUAM JS challenge, basic bot detection |
| Playwright | Medium | Headless Chromium | Turnstile, JS challenges |
| UndetectedChrome | Slower | Patched Chrome | All of the above + advanced fingerprinting |

---

## Installation

```bash
git clone https://github.com/prakharbhawsar1/cloudflare-bypass-toolkit
cd cloudflare-bypass-toolkit
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Install Playwright browsers (only needed for the Playwright strategy)
playwright install chromium
```

---

## Quick start

```python
from cf_bypass import BypassEngine, configure_logging

configure_logging(level="INFO")

engine = BypassEngine()
result = engine.fetch("https://example.com")

print(result.status_code)   # 200
print(result.text[:500])
print(result.strategy_used) # StrategyType.CLOUDSCRAPER
```

---

## Custom configuration

```python
from cf_bypass import BypassEngine, BypassConfig, ProxyConfig
from cf_bypass.models.config import StrategyType

config = BypassConfig(
    # Only use browser-based strategies
    strategies=[StrategyType.PLAYWRIGHT, StrategyType.UNDETECTED],

    # Retry each strategy up to 3 times before falling through
    max_retries=3,

    # Route all traffic through a proxy
    proxy=ProxyConfig(
        host="proxy.example.com",
        port=8080,
        username="user",
        password="secret",
    ),

    # Keep browser windows visible (useful for debugging)
    headless=False,

    # Store session cookies in a custom directory
    session_dir="/tmp/my_cf_sessions",
)

engine = BypassEngine(config)
result = engine.fetch("https://target-site.com")
```

---

## Concurrent fetching

Browser strategies block the thread (browser I/O), so a thread pool gives
real parallelism without `asyncio` complexity:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from cf_bypass import BypassEngine

engine = BypassEngine()
urls = ["https://site-a.com", "https://site-b.com", "https://site-c.com"]

with ThreadPoolExecutor(max_workers=4) as pool:
    futures = {pool.submit(engine.fetch, url): url for url in urls}
    for future in as_completed(futures):
        result = future.result()
        print(result.status_code, result.strategy_used)
```

---

## Session persistence

Clearance cookies are automatically saved after a successful bypass and
loaded on subsequent requests to the same domain (TTL: 1 hour by default):

```python
from cf_bypass.core.session_manager import SessionManager

mgr = SessionManager(session_dir=".cf_sessions", ttl_hours=2)

# Manual save / load
mgr.save("https://example.com", {"cf_clearance": "abc123"})
cookies = mgr.load("https://example.com")  # None if expired

# Clear all cached sessions
mgr.clear()
```

---

## Running tests

### Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # only needed for Playwright strategy
```

### Unit tests (fast, no network, runs by default)

```bash
pytest                              # all unit tests
pytest -v tests/test_strategies.py  # specific file
pytest --cov                        # with coverage report
```

### Local manual testing

```bash
# Optional: copy .env.example → .env and add proxy credentials
cp .env.example .env

# Run against your own target
python local_test.py
```

Edit `local_test.py` to set your target URL, strategy, and proxy.
Set `HEADLESS = False` to watch the browser solve the challenge live.

```
tests/
├── conftest.py               # shared fixtures
├── test_bypass_engine.py     # engine orchestration & fallback logic
├── test_session_manager.py   # persistence, expiry, corruption handling
└── test_strategies.py        # CloudScraper strategy (mocked at network level)
```

---

## Adding a new strategy

1. Create `src/cf_bypass/strategies/my_strategy.py` extending `BaseBypassStrategy`
2. Implement `name`, `is_available()`, and `fetch()`
3. Register it in `_STRATEGY_REGISTRY` inside `bypass_engine.py`
4. Add the enum value to `StrategyType`

The engine picks it up automatically — no other files change.

---

## Structured logs (sample)

```json
{"event": "engine_fetch_start",  "url": "https://example.com", "strategies": ["cloudscraper"]}
{"event": "strategy_attempt",    "strategy": "cloudscraper", "attempt": 1, "max_retries": 3}
{"event": "strategy_success",    "strategy": "cloudscraper", "status_code": 200, "elapsed_seconds": 0.83}
{"event": "engine_fetch_success","url": "https://example.com", "strategy": "cloudscraper"}
```

---

## Disclaimer

This toolkit is intended **strictly for development and testing purposes** —
for example, testing your own Cloudflare-protected services, CI pipelines,
or authorised penetration testing engagements. Always comply with a
website's Terms of Service and `robots.txt` before scraping. The author
accepts no responsibility for misuse of this software.

---

## License

MIT © [Prakhar Bhawsar](mailto:prakhar1812.b@gmail.com)
