"""
FastAPI Main Application
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_db
from .api import auth, tasks, checkout, websocket, games
from .bot.monitor import task_manager
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
    
    # Start the task scheduler
    await scheduler.start()
    logging.info("Task scheduler started")
    
    yield
    
    # Shutdown
    logging.info("Shutting down...")
    await scheduler.stop()


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
