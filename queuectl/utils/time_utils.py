"""
QueueCTL Time Utilities Module.

Provides standard UTC ISO-8601 datetimes and duration calculations.
"""

from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Returns current UTC time formatted as ISO-8601 string."""
    return utc_now().isoformat()


def parse_iso(iso_str: Optional[str]) -> Optional[datetime]:
    """Parses an ISO-8601 string into a timezone-aware UTC datetime."""
    if not iso_str:
        return None
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_duration(seconds: float) -> str:
    """Formats duration in seconds to human readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        rem_sec = seconds % 60
        return f"{minutes}m {rem_sec:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
