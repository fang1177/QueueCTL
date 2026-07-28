"""
QueueCTL Configuration Repository Module.

Manages reading and updating runtime system configurations stored in SQLite.
"""

from typing import Dict, Optional
from sqlalchemy.orm import Session

from queuectl.models.config import ConfigItem
from queuectl.utils.time_utils import utc_now


class ConfigRepository:
    """Data repository for dynamic runtime system configuration."""

    def __init__(self, session: Session):
        self.session = session

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Fetch config value by key."""
        item = self.session.get(ConfigItem, key)
        return item.value if item else default

    def set(self, key: str, value: str) -> ConfigItem:
        """Sets or updates configuration key-value pair."""
        item = self.session.get(ConfigItem, key)
        now = utc_now()
        if not item:
            item = ConfigItem(key=key, value=value, updated_at=now)
            self.session.add(item)
        else:
            item.value = value
            item.updated_at = now
        self.session.flush()
        return item

    def get_all(self) -> Dict[str, str]:
        """Return all runtime configuration key-value pairs."""
        items = self.session.query(ConfigItem).all()
        return {item.key: item.value for item in items}
