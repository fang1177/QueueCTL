"""
QueueCTL Base Repository Module.

Provides standard clean architecture data access interface.
"""

from typing import Generic, TypeVar, Optional, List, Type
from sqlalchemy.orm import Session
from queuectl.database.connection import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic repository providing basic CRUD operations."""

    def __init__(self, session: Session, model_cls: Type[T]):
        self.session = session
        self.model_cls = model_cls

    def get_by_id(self, item_id: Any) -> Optional[T]:
        """Fetch item by primary key."""
        return self.session.get(self.model_cls, item_id)

    def list_all(self) -> List[T]:
        """Fetch all items."""
        return self.session.query(self.model_cls).all()

    def add(self, entity: T) -> T:
        """Add new entity to session."""
        self.session.add(entity)
        return entity

    def delete(self, entity: T) -> None:
        """Delete entity from session."""
        self.session.delete(entity)
