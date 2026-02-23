"""Unit tests for BypassEngine orchestration logic."""

from unittest.mock import MagicMock, patch

import pytest

from cf_bypass import BypassConfig, BypassEngine
from cf_bypass.exceptions import AllStrategiesFailedError, StrategyError
from cf_bypass.models.config import StrategyType
from cf_bypass.models.result import BypassResult


def _make_result(strategy: StrategyType = StrategyType.CLOUDSCRAPER) -> BypassResult:
    return BypassResult(
        url="https://example.com",
        status_code=200,
        content=b"<html>OK</html>",
        headers={"Content-Type": "text/html"},
        strategy_used=strategy,
        attempt_count=1,
        elapsed_seconds=0.42,
        cookies={"cf_clearance": "token"},
    )


def _cloudscraper_config(tmp_path) -> BypassConfig:
    return BypassConfig(
        max_retries=1,
        delay_between_retries=0.0,
        session_dir=str(tmp_path / "sessions"),
        strategies=[StrategyType.CLOUDSCRAPER],
    )


# ---------------------------------------------------------------------------
# Engine initialisation
# ---------------------------------------------------------------------------

class TestBypassEngineInit:
    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    def test_available_strategies_populated(self, tmp_path):
        engine = BypassEngine(_cloudscraper_config(tmp_path))
        assert "cloudscraper" in engine.available_strategies

    def test_raises_when_no_strategy_available(self, tmp_path):
        with (
            patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", False),
            patch("cf_bypass.strategies.playwright_strategy._PLAYWRIGHT_AVAILABLE", False),
            patch("cf_bypass.strategies.undetected_strategy._UC_AVAILABLE", False),
        ):
            with pytest.raises(AllStrategiesFailedError, match="No bypass strategies"):
                BypassEngine(_cloudscraper_config(tmp_path))


# ---------------------------------------------------------------------------
# fetch() – happy path
# ---------------------------------------------------------------------------

class TestBypassEngineFetch:
    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    def test_returns_result_from_first_succeeding_strategy(self, tmp_path):
        expected = _make_result()
        with patch(
            "cf_bypass.strategies.cloudscraper_strategy.CloudScraperStrategy.fetch",
            return_value=expected,
        ):
            engine = BypassEngine(_cloudscraper_config(tmp_path))
            result = engine.fetch("https://example.com")

        assert result is expected
        assert result.status_code == 200

    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    def test_cookies_persisted_to_session_manager(self, tmp_path):
        expected = _make_result()
        with patch(
            "cf_bypass.strategies.cloudscraper_strategy.CloudScraperStrategy.fetch",
            return_value=expected,
        ):
            engine = BypassEngine(_cloudscraper_config(tmp_path))
            engine.fetch("https://example.com")

        # Cookies should now be in the session store
        loaded = engine._session_manager.load("https://example.com")
        assert loaded == {"cf_clearance": "token"}

    # ---------------------------------------------------------------------------
    # fetch() – fallback behaviour
    # ---------------------------------------------------------------------------

    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    @patch("cf_bypass.strategies.playwright_strategy._PLAYWRIGHT_AVAILABLE", True)
    def test_falls_back_to_second_strategy(self, tmp_path):
        config = BypassConfig(
            max_retries=1,
            delay_between_retries=0.0,
            session_dir=str(tmp_path / "sessions"),
            strategies=[StrategyType.CLOUDSCRAPER, StrategyType.PLAYWRIGHT],
        )
        playwright_result = _make_result(StrategyType.PLAYWRIGHT)

        with (
            patch(
                "cf_bypass.strategies.cloudscraper_strategy.CloudScraperStrategy.fetch",
                side_effect=StrategyError("CS failed"),
            ),
            patch(
                "cf_bypass.strategies.playwright_strategy.PlaywrightStrategy.fetch",
                return_value=playwright_result,
            ),
        ):
            engine = BypassEngine(config)
            result = engine.fetch("https://example.com")

        assert result.strategy_used == StrategyType.PLAYWRIGHT

    # ---------------------------------------------------------------------------
    # fetch() – all fail
    # ---------------------------------------------------------------------------

    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    def test_raises_all_strategies_failed_when_every_strategy_fails(self, tmp_path):
        with patch(
            "cf_bypass.strategies.cloudscraper_strategy.CloudScraperStrategy.fetch",
            side_effect=StrategyError("always fails"),
        ):
            engine = BypassEngine(_cloudscraper_config(tmp_path))
            with pytest.raises(AllStrategiesFailedError):
                engine.fetch("https://example.com")

    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    def test_error_message_contains_strategy_name(self, tmp_path):
        with patch(
            "cf_bypass.strategies.cloudscraper_strategy.CloudScraperStrategy.fetch",
            side_effect=StrategyError("connection refused"),
        ):
            engine = BypassEngine(_cloudscraper_config(tmp_path))
            with pytest.raises(AllStrategiesFailedError, match="cloudscraper"):
                engine.fetch("https://example.com")
