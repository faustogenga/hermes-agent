"""
Timezone-aware clock for Hermes.

Provides a single ``now()`` helper that returns a timezone-aware datetime
based on the user's configured IANA timezone (e.g. ``Asia/Kolkata``).

Resolution order:
  1. ``HERMES_TIMEZONE`` environment variable
  2. ``timezone`` key in ``~/.hermes/config.yaml``
  3. Falls back to the server's local time (``datetime.now().astimezone()``)

Invalid timezone values log a warning and fall back safely — Hermes never
crashes due to a bad timezone string.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from hermes_constants import get_config_path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python 3.8 fallback (shouldn't be needed — Hermes requires 3.9+)
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

# Cached state — resolved once, reused until the env/config signature changes.
# Call reset_cache() to force re-resolution immediately after a config write.
_cached_tz: Optional[ZoneInfo] = None
_cached_tz_name: Optional[str] = None
_cached_signature: Optional[Tuple[str, str, Optional[int]]] = None
_cache_resolved: bool = False


def reset_cache() -> None:
    """Clear the cached timezone so the next ``now()`` reflects fresh config/env."""
    global _cached_tz, _cached_tz_name, _cached_signature, _cache_resolved
    _cached_tz = None
    _cached_tz_name = None
    _cached_signature = None
    _cache_resolved = False


def _get_config_mtime_ns(config_path: Path) -> Optional[int]:
    """Return config mtime in ns, or None when the file is absent/unreadable."""
    try:
        return config_path.stat().st_mtime_ns
    except OSError:
        return None


def _get_timezone_signature() -> Tuple[str, str, Optional[int]]:
    """Return a cheap fingerprint for env/config timezone inputs.

    Shape:
      (env_timezone, config_path, config_mtime_ns)

    When HERMES_TIMEZONE is set, it fully overrides config timezone, so only the
    env value matters for freshness. Otherwise the config path + mtime determines
    whether we need to re-read config.yaml.
    """
    tz_env = os.getenv("HERMES_TIMEZONE", "").strip()
    if tz_env:
        return (tz_env, "", None)

    config_path = get_config_path()
    return ("", str(config_path), _get_config_mtime_ns(config_path))


def _resolve_timezone_name() -> str:
    """Read the configured IANA timezone string (or empty string).

    This does file I/O when falling through to config.yaml, so callers
    should cache the result rather than calling on every ``now()``.
    """
    # 1. Environment variable (highest priority — set by Supervisor, etc.)
    tz_env = os.getenv("HERMES_TIMEZONE", "").strip()
    if tz_env:
        return tz_env

    # 2. config.yaml ``timezone`` key
    try:
        import yaml
        config_path = get_config_path()
        if config_path.exists():
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            tz_cfg = cfg.get("timezone", "")
            if isinstance(tz_cfg, str) and tz_cfg.strip():
                return tz_cfg.strip()
    except Exception:
        pass

    return ""


def _get_zoneinfo(name: str) -> Optional[ZoneInfo]:
    """Validate and return a ZoneInfo, or None if invalid."""
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (KeyError, Exception) as exc:
        logger.warning(
            "Invalid timezone '%s': %s. Falling back to server local time.",
            name, exc,
        )
        return None


def get_timezone() -> Optional[ZoneInfo]:
    """Return the user's configured ZoneInfo, or None (meaning server-local).

    The resolved timezone is cached, but the cache auto-refreshes when either
    ``HERMES_TIMEZONE`` changes or ``config.yaml``'s mtime changes. This keeps
    long-lived gateway/scheduler processes aligned with dashboard config edits
    without requiring an explicit restart.
    """
    global _cached_tz, _cached_tz_name, _cached_signature, _cache_resolved
    signature = _get_timezone_signature()
    if not _cache_resolved or _cached_signature != signature:
        _cached_tz_name = _resolve_timezone_name()
        _cached_tz = _get_zoneinfo(_cached_tz_name)
        _cached_signature = signature
        _cache_resolved = True
    return _cached_tz


def now() -> datetime:
    """
    Return the current time as a timezone-aware datetime.

    If a valid timezone is configured, returns wall-clock time in that zone.
    Otherwise returns the server's local time (via ``astimezone()``).
    """
    tz = get_timezone()
    if tz is not None:
        return datetime.now(tz)
    # No timezone configured — use server-local (still tz-aware)
    return datetime.now().astimezone()


