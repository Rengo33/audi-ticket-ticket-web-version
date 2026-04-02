from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging

logger = logging.getLogger(__name__)

from .config import get_settings

settings = get_settings()

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}  # SQLite specific
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column_if_missing(table_name: str, column_name: str, column_type: str):
    """Add a column to an existing table if it doesn't exist (SQLite)."""
    inspector = inspect(engine)
    if table_name in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns(table_name)]
        if column_name not in columns:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
            logger.info(f"Added column {column_name} to {table_name}")


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    # Migrations for existing databases
    _add_column_if_missing("tasks", "tickets_available", "INTEGER DEFAULT 0")
    _add_column_if_missing("tasks", "last_scan_at", "DATETIME")
    _add_column_if_missing("tasks", "price_category", "INTEGER DEFAULT 0")
    _add_column_if_missing("scheduled_tasks", "price_category", "INTEGER DEFAULT 0")
    _add_column_if_missing("cart_sessions", "price_category", "INTEGER DEFAULT 0")
    # ACO migrations
    _add_column_if_missing("tasks", "auto_checkout", "BOOLEAN DEFAULT 0")
    _add_column_if_missing("tasks", "billing_profile_id", "INTEGER")
    _add_column_if_missing("scheduled_tasks", "auto_checkout", "BOOLEAN DEFAULT 0")
    _add_column_if_missing("scheduled_tasks", "billing_profile_id", "INTEGER")
    _add_column_if_missing("cart_sessions", "checkout_status", "VARCHAR(30) DEFAULT 'pending'")
    _add_column_if_missing("cart_sessions", "client_secret", "TEXT")
    _add_column_if_missing("cart_sessions", "payment_intent_id", "VARCHAR(100)")
    _add_column_if_missing("cart_sessions", "payment_method_id", "VARCHAR(100)")
    _add_column_if_missing("cart_sessions", "checkout_error", "TEXT")
