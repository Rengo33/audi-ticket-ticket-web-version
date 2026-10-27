"""
FastAPI Main Application
"""
import asyncio
import logging
import logging.handlers
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_db, SessionLocal
from .api import auth, tasks, checkout, websocket, games, billing, push, detector
from .bot.monitor import task_manager
from .bot.release_detector import release_detector
from .bot import web_push
from .models import Task, TaskStatus, ReleaseDetector
from .scheduler import scheduler

settings = get_settings()

# Configure logging
logging.basicConfig(
    format='[%(asctime)s] %(levelname)s: %(message)s',
    level=logging.DEBUG if settings.debug else logging.INFO,
    datefmt='%H:%M:%S'
)
# Also keep logs on disk: data/ is a host bind mount, so this survives container
# rebuilds (docker logs don't) and task deletion (which drops task_logs rows).
os.makedirs("data/logs", exist_ok=True)
_file_log = logging.handlers.RotatingFileHandler(
    "data/logs/backend.log", maxBytes=10_000_000, backupCount=10, encoding="utf-8")
_file_log.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', '%Y-%m-%d %H:%M:%S'))
logging.getLogger().addHandler(_file_log)


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

    # Resume the release detector if it was active before the restart.
    db = SessionLocal()
    try:
        cfg = db.query(ReleaseDetector).filter(ReleaseDetector.id == 1).first()
        if cfg and cfg.active:
            logging.info("Resuming release detector after restart")
            await release_detector.start(db)
    finally:
        db.close()

    # Watchdog: reconcile DB rows in 'running'/'waiting' against the live
    # task_manager every minute. A crashed watcher (poisoned DB session,
    # network blow-up) can leave a row marked 'running' with no in-memory
    # worker; without this, the task is permanently stranded.
    watchdog_task = asyncio.create_task(_task_watchdog())

    yield

    # Shutdown
    logging.info("Shutting down...")
    watchdog_task.cancel()
    await scheduler.stop()
    await web_push.stop_worker()


async def _task_watchdog():
    while True:
        try:
            await asyncio.sleep(60)
            db = SessionLocal()
            try:
                stale = db.query(Task).filter(
                    Task.status.in_([TaskStatus.RUNNING.value, TaskStatus.WAITING.value])
                ).all()
                for task in stale:
                    if task.id not in task_manager.active_tasks:
                        logging.warning(f"Watchdog: task {task.id} is {task.status} in DB but has no worker — marking failed")
                        task.status = TaskStatus.FAILED.value
                        task.error_message = (task.error_message or "") + " | Watchdog: no live worker"
                db.commit()
            finally:
                db.close()
        except asyncio.CancelledError:
            return
        except Exception as e:
            logging.error(f"Watchdog tick failed: {e}")


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
app.include_router(detector.router, prefix="/api")
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
