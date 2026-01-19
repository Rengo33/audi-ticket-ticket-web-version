"""
Scheduler for automatically triggering tasks at scheduled times.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import ScheduledTask, Task, TaskStatus
from .bot.monitor import task_manager

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Background scheduler for starting tasks at scheduled times."""
    
    def __init__(self):
        self.running = False
        self._task = None
    
    async def start(self):
        """Start the scheduler background task."""
        if self.running:
            return
        
        self.running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info("Task scheduler started")
    
    async def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Task scheduler stopped")
    
    async def _run_scheduler(self):
        """Main scheduler loop - checks every 30 seconds for due tasks."""
        while self.running:
            try:
                await self._check_scheduled_tasks()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _check_scheduled_tasks(self):
        """Check for tasks that need to be triggered."""
        db = SessionLocal()
        
        try:
            now = datetime.utcnow()
            
            # Find scheduled tasks that are due (within 1 minute window)
            due_tasks = db.query(ScheduledTask).filter(
                ScheduledTask.status == "scheduled",
                ScheduledTask.scheduled_date <= now + timedelta(minutes=1),
                ScheduledTask.scheduled_date >= now - timedelta(minutes=5)  # Don't trigger very old tasks
            ).all()
            
            for scheduled in due_tasks:
                logger.info(f"Triggering scheduled task: {scheduled.game_title}")
                
                try:
                    # Create the actual task
                    task = Task(
                        product_url=scheduled.product_url,
                        quantity=scheduled.quantity,
                        num_threads=scheduled.num_threads,
                        status=TaskStatus.PENDING.value
                    )
                    db.add(task)
                    db.commit()
                    db.refresh(task)
                    
                    # Update scheduled task
                    scheduled.status = "triggered"
                    scheduled.triggered_at = now
                    scheduled.task_id = task.id
                    db.commit()
                    
                    # Start the task (pass task object, not task.id)
                    success = await task_manager.start_task(task, db)
                    
                    if success:
                        logger.info(f"Successfully started task {task.id} for {scheduled.game_title}")
                    else:
                        logger.error(f"Failed to start task {task.id} for {scheduled.game_title}")
                        scheduled.status = "failed"
                        db.commit()
                        
                except Exception as e:
                    logger.error(f"Error triggering task for {scheduled.game_title}: {e}")
                    scheduled.status = "failed"
                    db.commit()
            
            # Mark very old scheduled tasks as failed
            old_tasks = db.query(ScheduledTask).filter(
                ScheduledTask.status == "scheduled",
                ScheduledTask.scheduled_date < now - timedelta(minutes=10)
            ).all()
            
            for old in old_tasks:
                logger.warning(f"Marking overdue scheduled task as failed: {old.game_title}")
                old.status = "failed"
                db.commit()
                
        except Exception as e:
            logger.error(f"Error checking scheduled tasks: {e}")
            db.rollback()
        finally:
            db.close()


# Global scheduler instance
scheduler = TaskScheduler()
