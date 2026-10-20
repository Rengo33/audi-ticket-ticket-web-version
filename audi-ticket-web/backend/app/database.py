from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.exc import OperationalError
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


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    """Rollback journal (not WAL). WAL keeps committed-but-uncheckpointed data in
    a separate -wal/-shm pair; on a Docker bind mount that pair desyncs when the
    container is recreated on redeploy, and SQLite drops the uncheckpointed
    frames — i.e. every `docker compose up --build` silently wiped recent cart
    sessions / billing profiles. This app is single-writer (one uvicorn, a few
    async tasks), so WAL's concurrency buys little; DELETE journals straight into
    the main db file and survives container churn.
    PRAGMA foreign_keys is OFF by default — turning it on honors our cascades.
    ponytail: single-writer app; revisit WAL + a shutdown checkpoint only if DB
    contention ever shows up."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=DELETE")
    cur.execute("PRAGMA synchronous=FULL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


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
    """Add a column to an existing table if it doesn't exist (SQLite).
    Tolerates concurrent boots: if a sibling worker added the column between
    inspect() and ALTER, the OperationalError ('duplicate column') is fine."""
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    if column_name in columns:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
        logger.info(f"Added column {column_name} to {table_name}")
    except OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise


def _add_index_if_missing(name: str, table: str, columns: str):
    """Create a covering index on hot-path filters. CREATE INDEX IF NOT EXISTS
    is idempotent at the SQL level, but we still skip the SQL round-trip if
    the inspector already knows about it."""
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    if any(idx['name'] == name for idx in inspector.get_indexes(table)):
        return
    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({columns})"))
        logger.info(f"Created index {name} on {table}({columns})")
    except OperationalError as e:
        logger.warning(f"Index {name} create skipped: {e}")


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
    _add_column_if_missing("cart_sessions", "invoice_url", "TEXT")
    _add_column_if_missing("cart_sessions", "billing_profile_id", "INTEGER")
    _add_column_if_missing("cart_sessions", "event_id", "VARCHAR(100)")
    _add_column_if_missing("release_detector", "frontier_id", "INTEGER")
    _add_column_if_missing("release_detector", "launched_ids", "TEXT DEFAULT '{}'")

    # Hot-path indexes — scheduler ticks every 30 s and the cart/log queries
    # filter on these columns on every dashboard render.
    _add_index_if_missing("ix_tasks_status", "tasks", "status")
    _add_index_if_missing("ix_scheduled_tasks_status_date", "scheduled_tasks", "status, scheduled_date")
    _add_index_if_missing("ix_cart_sessions_lookup", "cart_sessions", "task_id, checkout_status, expires_at")
    _add_index_if_missing("ix_task_logs_task_created", "task_logs", "task_id, created_at")
