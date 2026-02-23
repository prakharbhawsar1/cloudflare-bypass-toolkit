"""Unit tests for individual bypass strategies."""

from unittest.mock import MagicMock, patch

import pytest

from cf_bypass.exceptions import StrategyError
from cf_bypass.models.config import BypassConfig, StrategyType
from cf_bypass.models.result import BypassResult
from cf_bypass.strategies.cloudscraper_strategy import CloudScraperStrategy


def _zero_delay_config(tmp_path, retries: int = 1) -> BypassConfig:
    return BypassConfig(
        max_retries=retries,
        delay_between_retries=0.0,
        session_dir=str(tmp_path / "sessions"),
        strategies=[StrategyType.CLOUDSCRAPER],
    )


def _mock_response(status: int = 200, content: bytes = b"<html>OK</html>") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.content = content
    resp.headers = {"Content-Type": "text/html"}
    resp.cookies = {}
    return resp


# ---------------------------------------------------------------------------
# CloudScraperStrategy
# ---------------------------------------------------------------------------

class TestCloudScraperStrategy:

    def test_is_available_when_installed(self, tmp_path):
        with patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True):
            s = CloudScraperStrategy(_zero_delay_config(tmp_path))
            assert s.is_available() is True

    def test_is_unavailable_when_not_installed(self, tmp_path):
        with patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", False):
            s = CloudScraperStrategy(_zero_delay_config(tmp_path))
            assert s.is_available() is False

    def test_fetch_raises_when_not_installed(self, tmp_path):
        with patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", False):
            s = CloudScraperStrategy(_zero_delay_config(tmp_path))
            with pytest.raises(StrategyError, match="not installed"):
                s.fetch("https://example.com")

    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    def test_fetch_returns_bypass_result(self, tmp_path):
        config = _zero_delay_config(tmp_path)
        with patch("cloudscraper.create_scraper") as mock_create:
            mock_scraper = MagicMock()
            mock_scraper.get.return_value = _mock_response()
            mock_create.return_value = mock_scraper

            s = CloudScraperStrategy(config)
            result = s.fetch("https://example.com")

        assert isinstance(result, BypassResult)
        assert result.status_code == 200
        assert result.strategy_used == StrategyType.CLOUDSCRAPER
        assert result.content == b"<html>OK</html>"
        assert result.attempt_count == 1

    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    def test_fetch_retries_on_transient_error(self, tmp_path):
        config = _zero_delay_config(tmp_path, retries=3)
        success_resp = _mock_response()

        with patch("cloudscraper.create_scraper") as mock_create:
            mock_scraper = MagicMock()
            mock_scraper.get.side_effect = [
                ConnectionError("timeout"),
                ConnectionError("timeout"),
                success_resp,
            ]
            mock_create.return_value = mock_scraper

            s = CloudScraperStrategy(config)
            result = s.fetch("https://example.com")

        assert result.ok is True
        assert result.attempt_count == 3

    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    def test_fetch_raises_strategy_error_after_exhausting_retries(self, tmp_path):
        config = _zero_delay_config(tmp_path, retries=2)

        with patch("cloudscraper.create_scraper") as mock_create:
            mock_scraper = MagicMock()
            mock_scraper.get.side_effect = ConnectionError("always fails")
            mock_create.return_value = mock_scraper

            s = CloudScraperStrategy(config)
            with pytest.raises(StrategyError, match="exhausted"):
                s.fetch("https://example.com")

    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    def test_proxy_is_applied_to_scraper_session(self, tmp_path):
        from cf_bypass.models.config import ProxyConfig

        config = BypassConfig(
            max_retries=1,
            delay_between_retries=0.0,
            session_dir=str(tmp_path),
            strategies=[StrategyType.CLOUDSCRAPER],
            proxy=ProxyConfig(host="proxy.example.com", port=8080),
        )
        with patch("cloudscraper.create_scraper") as mock_create:
            mock_scraper = MagicMock()
            mock_scraper.get.return_value = _mock_response()
            mock_create.return_value = mock_scraper

            s = CloudScraperStrategy(config)
            s.fetch("https://example.com")

        mock_scraper.proxies.update.assert_called_once()

    @patch("cf_bypass.strategies.cloudscraper_strategy._CLOUDSCRAPER_AVAILABLE", True)
    def test_result_text_property(self, tmp_path):
        with patch("cloudscraper.create_scraper") as mock_create:
            mock_scraper = MagicMock()
            mock_scraper.get.return_value = _mock_response(content=b"hello world")
            mock_create.return_value = mock_scraper

            s = CloudScraperStrategy(_zero_delay_config(tmp_path))
            result = s.fetch("https://example.com")

        assert result.text == "hello world"
