"""
Task management endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from ..models import Task, TaskStatus, TaskLog, CartSession
from ..schemas import TaskCreate, TaskResponse, TaskListResponse, TaskLogResponse
from ..bot.monitor import task_manager

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Create a new monitoring task."""
    # Validate URL
    if "audidefuehrungen2.regiondo.de" not in task_data.product_url:
        raise HTTPException(400, "Invalid product URL")
    
    # Validate quantity
    if not 1 <= task_data.quantity <= 4:
        raise HTTPException(400, "Quantity must be between 1 and 4")
    
    # Create task
    task = Task(
        product_url=task_data.product_url,
        quantity=task_data.quantity,
        num_threads=task_data.num_threads
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return task


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """List all tasks."""
    tasks = db.query(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    total = db.query(Task).count()
    
    # Enrich tasks with cart tokens if available
    task_responses = []
    for task in tasks:
        task_dict = {
            "id": task.id,
            "product_url": task.product_url,
            "quantity": task.quantity,
            "num_threads": task.num_threads,
            "status": task.status,
            "scan_count": task.scan_count,
            "tickets_available": task.tickets_available or 0,
            "last_scan_at": task.last_scan_at,
            "event_id": task.event_id,
            "ticket_id": task.ticket_id,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "error_message": task.error_message,
            "cart_token": None
        }
        
        # Get the most recent active cart session for this task
        if task.status == TaskStatus.SUCCESS.value:
            cart = db.query(CartSession).filter(
                CartSession.task_id == task.id
            ).order_by(CartSession.created_at.desc()).first()
            if cart:
                task_dict["cart_token"] = cart.token
        
        task_responses.append(TaskResponse(**task_dict))
    
    return TaskListResponse(tasks=task_responses, total=total)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Get a specific task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/{task_id}/start")
async def start_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Start a task."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Refresh DB session to avoid stale data
    db.expire_all()
    
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    
    logger.info(f"Starting task {task_id}, current status: {task.status}")
    logger.info(f"Active tasks in manager: {list(task_manager.active_tasks.keys())}")
    
    # Check if task_id is in active_tasks but the task might be done
    if task_id in task_manager.active_tasks:
        async_task = task_manager.active_tasks[task_id]
        if async_task.done():
            # Clean up stale task
            logger.info(f"Task {task_id} async task was done, cleaning up stale entry")
            del task_manager.active_tasks[task_id]
            if task_id in task_manager.task_data:
                del task_manager.task_data[task_id]
        else:
            logger.info(f"Task {task_id} already running in task_manager, returning success")
            return {"success": True, "message": "Task already running"}
    
    # Also check DB status but be more careful - only skip if really running
    if task.status == TaskStatus.RUNNING.value:
        # Double check it's actually running in task_manager
        if task_id in task_manager.active_tasks:
            logger.info(f"Task {task_id} marked as running in DB and in active_tasks, returning success")
            return {"success": True, "message": "Task already running"}
        else:
            # DB says running but no active task - fix the inconsistency
            logger.warning(f"Task {task_id} marked as running in DB but not in active_tasks - resetting status")
            task.status = TaskStatus.PENDING.value
            db.commit()
    
    success = await task_manager.start_task(task, db)
    logger.info(f"task_manager.start_task returned: {success}")
    
    if not success:
        # Task might have been started by another request - check again
        if task_id in task_manager.active_tasks:
            return {"success": True, "message": "Task already running"}
        logger.error(f"Failed to start task {task_id}")
        raise HTTPException(500, "Failed to start task")
    
    return {"success": True, "message": "Task started"}


@router.post("/{task_id}/stop")
async def stop_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Stop a running task."""
    success = await task_manager.stop_task(task_id, db)
    
    if not success:
        raise HTTPException(400, "Task is not running")
    
    return {"success": True, "message": "Task stopped"}


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Delete a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    
    # Stop if running
    if task.status == TaskStatus.RUNNING.value:
        await task_manager.stop_task(task_id, db)
    
    # Delete logs
    db.query(TaskLog).filter(TaskLog.task_id == task_id).delete()
    
    # Delete task
    db.delete(task)
    db.commit()
    
    return {"success": True, "message": "Task deleted"}


@router.get("/{task_id}/logs", response_model=List[TaskLogResponse])
async def get_task_logs(
    task_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Get logs for a task."""
    logs = db.query(TaskLog)\
        .filter(TaskLog.task_id == task_id)\
        .order_by(TaskLog.created_at.desc())\
        .limit(limit)\
        .all()
    
    return logs
