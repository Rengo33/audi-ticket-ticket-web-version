"""
FastAPI Main Application
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_db, SessionLocal
from .api import auth, tasks, checkout, websocket, games, billing, push
from .bot.monitor import task_manager
from .bot import web_push
from .models import Task, TaskStatus
from .scheduler import scheduler

settings = get_settings()

# Configure logging
logging.basicConfig(
    format='[%(asctime)s] %(levelname)s: %(message)s',
    level=logging.DEBUG if settings.debug else logging.INFO,
    datefmt='%H:%M:%S'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logging.info("Starting Audi Ticket Bot Web...")
    init_db()
    
    # Set WebSocket broadcast callback
    task_manager.set_ws_broadcast(websocket.broadcast_message)

    # Resume any task that was mid-cycle when the service last died. The
    # re-cart timer lives in-memory, so a RUNNING or WAITING task from before
    # the restart has no background worker unless we re-subscribe it here.
    db = SessionLocal()
    try:
        stale = db.query(Task).filter(
            Task.status.in_([TaskStatus.RUNNING.value, TaskStatus.WAITING.value])
        ).all()
        for task in stale:
            logging.info(f"Resuming task {task.id} (was {task.status}) after restart")
            await task_manager.start_task(task, db)
    finally:
        db.close()

    # Start the task scheduler
    await scheduler.start()
    logging.info("Task scheduler started")

    yield

    # Shutdown
    logging.info("Shutting down...")
    await scheduler.stop()
    await web_push.stop_worker()


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    lifespan=lifespan
)

# CORS - allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(games.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(push.router, prefix="/api")
app.include_router(checkout.router)
app.include_router(websocket.router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "2.0.0"
    }


@app.get("/api/status")
async def get_status():
    """Get bot status."""
    return {
        "active_tasks": len(task_manager.active_tasks),
        "task_ids": list(task_manager.active_tasks.keys())
    }
