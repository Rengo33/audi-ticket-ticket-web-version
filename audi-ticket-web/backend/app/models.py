from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
import enum

from .database import Base


class TaskStatus(str, enum.Enum):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    WAITING = "waiting"
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
    price_category = Column(Integer, default=0)
    auto_checkout = Column(Boolean, default=False)
    billing_profile_id = Column(String(100), nullable=True)  # Comma-separated profile IDs for round-robin

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
    event_id = Column(String(100), nullable=True, index=True)  # Cached from Task.event_id for profile-usage tracking after task deletion

    # Cookie data
    cookie_name = Column(String(100), nullable=False)
    cookie_value = Column(Text, nullable=False)
    cookie_domain = Column(String(200), nullable=False)
    
    # Target
    product_url = Column(String(500), nullable=False)
    checkout_url = Column(String(500), nullable=True)
    
    # Metadata
    quantity = Column(Integer, default=1)
    price_category = Column(Integer, default=0)
    total_time = Column(Float, nullable=True)  # Detection to cart time
    
    # ACO status
    checkout_status = Column(String(30), default="pending")  # pending, running, billing_done, payment_confirmed, completed, failed
    billing_profile_id = Column(Integer, nullable=True, index=True)  # Profile used by ACO; set when dispatcher picks one
    client_secret = Column(Text, nullable=True)  # Stripe PI client secret
    payment_intent_id = Column(String(100), nullable=True)
    payment_method_id = Column(String(100), nullable=True)
    checkout_error = Column(Text, nullable=True)
    invoice_url = Column(Text, nullable=True)  # getTaxInvoicePdf.php?... signed PDF link from success page

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
    price_category = Column(Integer, default=0)
    auto_checkout = Column(Boolean, default=False)
    billing_profile_id = Column(String(100), nullable=True)  # Comma-separated profile IDs for round-robin

    # Schedule
    scheduled_date = Column(DateTime, nullable=False)  # Date/time when task should start (in UTC)
    
    # Status
    status = Column(String(20), default="scheduled")  # scheduled, triggered, completed, failed
    task_id = Column(Integer, nullable=True)  # Reference to created Task when triggered
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    triggered_at = Column(DateTime, nullable=True)


class BillingProfile(Base):
    """Billing profile for auto-checkout."""
    __tablename__ = "billing_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # Profile name e.g. "Leon", "Mate"

    # Personal info
    firstname = Column(String(100), nullable=False)
    lastname = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False)
    telephone = Column(String(50), nullable=False)
    stammnummer = Column(String(100), nullable=False)  # Audi employee number / buyer_field_5
    department = Column(String(200), default="")  # buyer_field_19900

    # Invoice address (always required for Rechnung)
    invoice_recipient = Column(String(200), default="")
    invoice_company = Column(String(200), default="")
    invoice_tax_id = Column(String(100), default="")
    invoice_street = Column(String(300), default="")
    invoice_postcode = Column(String(20), default="")
    invoice_city = Column(String(100), default="")
    invoice_country = Column(String(10), default="DE")

    # Card details (encrypted with Fernet)
    card_number_enc = Column(Text, default="")
    card_exp_month_enc = Column(Text, default="")
    card_exp_year_enc = Column(Text, default="")
    card_cvc_enc = Column(Text, default="")
    card_last4 = Column(String(4), default="")  # For display

    created_at = Column(DateTime, default=func.now())
