from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
import enum

from .database import Base


class TaskStatus(str, enum.Enum):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    STOPPED = "stopped"


class Task(Base):
    """Task model for monitoring jobs."""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Task configuration
    product_url = Column(String(500), nullable=False)
    quantity = Column(Integer, default=1)
    num_threads = Column(Integer, default=1)
    
    # Status
    status = Column(String(20), default=TaskStatus.PENDING.value)
    scan_count = Column(Integer, default=0)
    tickets_available = Column(Integer, default=0)  # Current ticket availability
    last_scan_at = Column(DateTime, nullable=True)  # When last scan was performed
    
    # Results
    event_id = Column(String(100), nullable=True)
    ticket_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Error info
    error_message = Column(Text, nullable=True)


class CartSession(Base):
    """Stored cart sessions for mobile checkout."""
    __tablename__ = "cart_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Link token (for /checkout/{token} URL)
    token = Column(String(64), unique=True, index=True, nullable=False)
    
    # Task reference
    task_id = Column(Integer, nullable=True)
    
    # Cookie data
    cookie_name = Column(String(100), nullable=False)
    cookie_value = Column(Text, nullable=False)
    cookie_domain = Column(String(200), nullable=False)
    
    # Target
    product_url = Column(String(500), nullable=False)
    checkout_url = Column(String(500), nullable=True)
    
    # Metadata
    quantity = Column(Integer, default=1)
    total_time = Column(Float, nullable=True)  # Detection to cart time
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)  # Cart hold expiry
    used_at = Column(DateTime, nullable=True)


class TaskLog(Base):
    """Logs for task activity."""
    __tablename__ = "task_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False, index=True)
    
    level = Column(String(20), default="info")  # info, warning, error, success
    message = Column(Text, nullable=False)
    
    created_at = Column(DateTime, default=func.now())


class ScheduledTask(Base):
    """Scheduled task to automatically start at a specific time."""
    __tablename__ = "scheduled_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Game reference
    game_id = Column(String(200), nullable=False)  # e.g., fc-bayern-munchen-rb-leipzig-ingolstadt-327097
    game_title = Column(String(300), nullable=False)
    product_url = Column(String(500), nullable=False)
    
    # Task configuration
    quantity = Column(Integer, default=4)
    num_threads = Column(Integer, default=5)
    
    # Schedule
    scheduled_date = Column(DateTime, nullable=False)  # Date/time when task should start (in UTC)
    
    # Status
    status = Column(String(20), default="scheduled")  # scheduled, triggered, completed, failed
    task_id = Column(Integer, nullable=True)  # Reference to created Task when triggered
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    triggered_at = Column(DateTime, nullable=True)
