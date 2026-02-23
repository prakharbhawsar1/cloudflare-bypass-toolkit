"""
Persistent cookie / session store for bypass results.

Serialises Cloudflare clearance cookies to disk so subsequent requests to
the same domain can skip the challenge phase entirely.
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_TTL_HOURS = 1


class SessionManager:
    """
    Manages on-disk Cloudflare bypass sessions (cookies).

    Each domain gets its own JSON file keyed by a hash of the URL.
    Sessions older than *ttl_hours* are treated as expired and discarded.

    Example::

        mgr = SessionManager()
        mgr.save("https://example.com", {"cf_clearance": "abc123"})
        cookies = mgr.load("https://example.com")
    """

    def __init__(
        self,
        session_dir: str = ".cf_sessions",
        ttl_hours: int = _DEFAULT_TTL_HOURS,
    ) -> None:
        self._dir = Path(session_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ttl = timedelta(hours=ttl_hours)
        self._log = structlog.get_logger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, url: str, cookies: dict[str, str]) -> None:
        """Persist *cookies* for *url* to disk."""
        path = self._path_for(url)
        payload = {
            "url": url,
            "cookies": cookies,
            "saved_at": datetime.utcnow().isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._log.debug("session_saved", url=url, path=str(path), cookie_count=len(cookies))

    def load(self, url: str) -> Optional[dict[str, str]]:
        """
        Return stored cookies for *url* if the session is still valid.

        Returns None if no session exists or it has expired.
        """
        path = self._path_for(url)
        if not path.exists():
            return None

        try:
            data: dict = json.loads(path.read_text(encoding="utf-8"))
            saved_at = datetime.fromisoformat(data["saved_at"])

            if datetime.utcnow() - saved_at > self._ttl:
                self._log.debug("session_expired", url=url)
                path.unlink(missing_ok=True)
                return None

            self._log.debug("session_loaded", url=url)
            return data["cookies"]

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            self._log.warning("session_corrupt", url=url, error=str(exc))
            path.unlink(missing_ok=True)
            return None

    def clear(self, url: Optional[str] = None) -> int:
        """
        Remove session files.

        Args:
            url: Clear only this URL's session.  If omitted, clears all.

        Returns:
            Number of session files deleted.
        """
        if url is not None:
            path = self._path_for(url)
            if path.exists():
                path.unlink()
                return 1
            return 0

        count = sum(1 for p in self._dir.glob("session_*.json") if p.unlink() or True)
        self._log.info("all_sessions_cleared", count=count)
        return count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path_for(self, url: str) -> Path:
        key = hashlib.sha256(url.encode()).hexdigest()[:16]
        return self._dir / f"session_{key}.json"
