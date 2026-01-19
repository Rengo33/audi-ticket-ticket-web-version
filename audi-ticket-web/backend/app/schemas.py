from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional, List
from .models import TaskStatus


# --- Auth ---
class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str


# --- Task ---
class TaskCreate(BaseModel):
    product_url: str
    quantity: int = 1
    num_threads: int = 1


class TaskResponse(BaseModel):
    id: int
    product_url: str
    quantity: int
    num_threads: int
    status: str
    scan_count: int
    tickets_available: int = 0  # Current ticket availability
    last_scan_at: Optional[datetime] = None  # When last scan was performed
    event_id: Optional[str]
    ticket_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    cart_token: Optional[str] = None  # For checkout link when success
    
    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int


# --- Cart Session ---
class CartSessionResponse(BaseModel):
    id: int
    token: str
    task_id: Optional[int]
    product_url: str
    checkout_url: Optional[str]
    quantity: int
    total_time: Optional[float]
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# --- Task Log ---
class TaskLogResponse(BaseModel):
    id: int
    task_id: int
    level: str
    message: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# --- WebSocket Messages ---
class WSMessage(BaseModel):
    type: str  # task_update, log, cart_success, error
    data: dict
