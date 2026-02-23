"""Shared pytest fixtures."""

import pytest

from cf_bypass.models.config import BypassConfig, StrategyType
from cf_bypass.core.session_manager import SessionManager


@pytest.fixture
def zero_delay_config(tmp_path):
    """Minimal config with instant retries (no sleep) for fast tests."""
    return BypassConfig(
        max_retries=1,
        delay_between_retries=0.0,
        session_dir=str(tmp_path / "sessions"),
        strategies=[StrategyType.CLOUDSCRAPER],
    )


@pytest.fixture
def session_manager(tmp_path):
    return SessionManager(session_dir=str(tmp_path / "sessions"))


@pytest.fixture
def sample_cookies():
    return {"cf_clearance": "sample_token_abc123", "__cfduid": "d1234567890"}
