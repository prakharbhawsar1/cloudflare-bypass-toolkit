"""Unit tests for SessionManager."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from cf_bypass.core.session_manager import SessionManager


class TestSessionManagerSaveAndLoad:
    def test_save_persists_file_to_disk(self, tmp_path, sample_cookies):
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save("https://example.com", sample_cookies)
        assert any(tmp_path.glob("session_*.json"))

    def test_load_returns_saved_cookies(self, tmp_path, sample_cookies):
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save("https://example.com", sample_cookies)
        loaded = mgr.load("https://example.com")
        assert loaded == sample_cookies

    def test_load_returns_none_for_unknown_url(self, tmp_path):
        mgr = SessionManager(session_dir=str(tmp_path))
        assert mgr.load("https://not-saved.example.com") is None

    def test_different_urls_get_separate_sessions(self, tmp_path):
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save("https://site-a.com", {"token": "aaa"})
        mgr.save("https://site-b.com", {"token": "bbb"})

        assert mgr.load("https://site-a.com") == {"token": "aaa"}
        assert mgr.load("https://site-b.com") == {"token": "bbb"}

    def test_same_url_overwritten_on_second_save(self, tmp_path):
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save("https://example.com", {"token": "old"})
        mgr.save("https://example.com", {"token": "new"})
        assert mgr.load("https://example.com") == {"token": "new"}


class TestSessionManagerExpiry:
    def test_expired_session_returns_none(self, tmp_path, sample_cookies):
        mgr = SessionManager(session_dir=str(tmp_path), ttl_hours=0)
        mgr.save("https://example.com", sample_cookies)
        # ttl=0 means any session is immediately expired
        result = mgr.load("https://example.com")
        assert result is None

    def test_expired_session_file_is_removed(self, tmp_path, sample_cookies):
        mgr = SessionManager(session_dir=str(tmp_path), ttl_hours=0)
        mgr.save("https://example.com", sample_cookies)
        mgr.load("https://example.com")  # triggers expiry cleanup
        assert not any(tmp_path.glob("session_*.json"))

    def test_corrupt_session_file_is_removed(self, tmp_path):
        mgr = SessionManager(session_dir=str(tmp_path))
        path = mgr._path_for("https://example.com")
        path.write_text("not valid json", encoding="utf-8")

        result = mgr.load("https://example.com")
        assert result is None
        assert not path.exists()


class TestSessionManagerClear:
    def test_clear_specific_url(self, tmp_path, sample_cookies):
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save("https://example.com", sample_cookies)

        cleared = mgr.clear("https://example.com")
        assert cleared == 1
        assert mgr.load("https://example.com") is None

    def test_clear_nonexistent_url_returns_zero(self, tmp_path):
        mgr = SessionManager(session_dir=str(tmp_path))
        assert mgr.clear("https://no-session.example.com") == 0

    def test_clear_all_removes_every_session(self, tmp_path):
        mgr = SessionManager(session_dir=str(tmp_path))
        mgr.save("https://a.com", {"k": "1"})
        mgr.save("https://b.com", {"k": "2"})
        mgr.save("https://c.com", {"k": "3"})

        cleared = mgr.clear()
        assert cleared == 3
        assert not any(tmp_path.glob("session_*.json"))
