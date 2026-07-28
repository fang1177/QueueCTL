"""
QueueCTL SQLite Database Connection Module.

Configures SQLAlchemy 2.0 Engine with WAL mode, busy timeout,
foreign key constraints, and session context managers.
"""

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def _configure_sqlite_engine(db_path: str):
    """Creates SQLAlchemy engine configured specifically for SQLite concurrency."""
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    db_url = f"sqlite:///{db_file.as_posix()}"
    
    # timeout=30 gives SQLite 30 seconds to wait for file locks to clear
    engine = create_engine(
        db_url,
        connect_args={
            "timeout": 30.0,
            "check_same_thread": False,
        },
        echo=False,
        future=True,
    )

    # Configure SQLite PRAGMAs on every new connection
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # Enable Write-Ahead Logging (WAL) for high concurrency
        cursor.execute("PRAGMA journal_mode=WAL;")
        # Set busy timeout to 5000ms so concurrent transactions wait rather than failing immediately
        cursor.execute("PRAGMA busy_timeout=5000;")
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON;")
        # Normal synchronous mode for good performance while keeping WAL safe
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

    return engine


class DatabaseManager:
    """Thread-safe and process-safe database manager for QueueCTL."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.engine = _configure_sqlite_engine(db_path)
        self.SessionFactory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def create_tables(self):
        """Creates all schema tables if they do not exist."""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Transactional context manager for DB sessions."""
        session = self.SessionFactory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


_db_manager_instance = None


def get_db_manager(db_path: str) -> DatabaseManager:
    """Returns singleton DatabaseManager instance for given db_path."""
    global _db_manager_instance
    if _db_manager_instance is None or _db_manager_instance.db_path != db_path:
        _db_manager_instance = DatabaseManager(db_path)
    return _db_manager_instance
