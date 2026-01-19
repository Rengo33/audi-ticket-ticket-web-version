"""
Task manager for running multiple monitoring tasks.
"""
import asyncio
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from ..models import Task, TaskStatus, CartSession, TaskLog
from ..config import get_settings
from ..database import SessionLocal
from .core import AudiTicketBot, CookieData
from .discord import send_discord_notification, send_discord_cart_success

logger = logging.getLogger(__name__)
settings = get_settings()


class TaskManager:
    """
    Manages multiple monitoring tasks.
    Each task runs in its own async coroutine.
    """
    
    def __init__(self):
        self.active_tasks: Dict[int, asyncio.Task] = {}
        self.task_data: Dict[int, dict] = {}  # Store previous data per task
        self._ws_broadcast: Optional[Callable] = None
    
    def set_ws_broadcast(self, callback: Callable):
        """Set WebSocket broadcast callback."""
        self._ws_broadcast = callback
    
    async def broadcast(self, message: dict):
        """Broadcast message to WebSocket clients."""
        if self._ws_broadcast:
            await self._ws_broadcast(message)
    
    async def start_task(self, task: Task, db: Session) -> bool:
        """Start a monitoring task."""
        logger.info(f"TaskManager.start_task called for task {task.id}")
        
        if task.id in self.active_tasks:
            logger.warning(f"Task {task.id} already in active_tasks, returning False")
            return False
        
        # Update task status
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.utcnow()
        db.commit()
        logger.info(f"Task {task.id} status updated to RUNNING in DB")
        
        # Create and store the async task - don't pass db, it will create its own
        async_task = asyncio.create_task(
            self._run_monitor(task.id, task.product_url, task.quantity, task.num_threads)
        )
        self.active_tasks[task.id] = async_task
        self.task_data[task.id] = {"previous_data": None}
        logger.info(f"Task {task.id} async task created and stored")
        
        await self.broadcast({
            "type": "task_update",
            "data": {"task_id": task.id, "status": "running"}
        })
        
        return True
    
    async def stop_task(self, task_id: int, db: Session) -> bool:
        """Stop a running task."""
        was_active = task_id in self.active_tasks
        
        if was_active:
            # Cancel the async task
            self.active_tasks[task_id].cancel()
            
            try:
                await self.active_tasks[task_id]
            except asyncio.CancelledError:
                pass
            
            del self.active_tasks[task_id]
            if task_id in self.task_data:
                del self.task_data[task_id]
        
        # Update DB regardless (in case of stale state)
        task = db.query(Task).filter(Task.id == task_id).first()
        if task and task.status == TaskStatus.RUNNING.value:
            task.status = TaskStatus.STOPPED.value
            task.completed_at = datetime.utcnow()
            db.commit()
            
            await self.broadcast({
                "type": "task_update",
                "data": {"task_id": task_id, "status": "stopped"}
            })
            return True
        
        return was_active
        
        return True
    
    async def _log(self, task_id: int, level: str, message: str, db: Session):
        """Add log entry for task."""
        try:
            log = TaskLog(task_id=task_id, level=level, message=message)
            db.add(log)
            db.commit()
            logger.info(f"[Task {task_id}] DB log committed: {message}")
        except Exception as e:
            logger.error(f"[Task {task_id}] DB log error: {e}")
            db.rollback()
        
        try:
            await self.broadcast({
                "type": "log",
                "data": {
                    "task_id": task_id,
                    "level": level,
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
        except Exception as e:
            logger.error(f"[Task {task_id}] Broadcast error: {e}")
    
    async def _run_monitor(
        self,
        task_id: int,
        product_url: str,
        quantity: int,
        num_threads: int
    ):
        """Main monitoring loop for a task."""
        logger.info(f"[Task {task_id}] _run_monitor started for {product_url}")
        
        # Create own database session for this long-running task
        db = SessionLocal()
        
        try:
            logger.info(f"[Task {task_id}] Creating bot instance...")
            async with AudiTicketBot() as bot:
                logger.info(f"[Task {task_id}] Bot created, logging start message...")
                await self._log(task_id, "info", f"Started monitoring: {product_url}", db)
                
                # Extract event details
                event_id, ticket_id = await bot.extract_event_details(product_url)
                
                if not event_id or not ticket_id:
                    await self._log(task_id, "error", "Could not extract Event/Ticket ID", db)
                    await self._mark_failed(task_id, "Could not extract Event/Ticket ID", db)
                    return
                
                # Store IDs in task
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.event_id = event_id
                    task.ticket_id = ticket_id
                    db.commit()
                
                await self._log(task_id, "info", f"Event ID: {event_id}, Ticket ID: {ticket_id}", db)
                
                scan_count = 0
                previous_data = None
                no_tickets_logged = False
                
                while True:
                    data = await bot.get_available_tickets(event_id, ticket_id)
                    scan_count += 1
                    
                    # Calculate total available tickets (only count positive values!)
                    total_available = 0
                    if data:
                        try:
                            total_available = sum(
                                sum(max(0, t.get('qty_available', 0)) for t in tickets)
                                for tickets in data.values()
                            )
                        except Exception:
                            total_available = 0
                    
                    # Update DB with scan info on every scan (for real-time status)
                    task = db.query(Task).filter(Task.id == task_id).first()
                    if task:
                        task.scan_count = scan_count
                        task.tickets_available = total_available
                        task.last_scan_at = datetime.utcnow()
                        db.commit()
                    
                    # Broadcast scan update to WebSocket clients
                    await self.broadcast({
                        "type": "scan_update",
                        "data": {
                            "task_id": task_id,
                            "scan_count": scan_count,
                            "tickets_available": total_available,
                            "last_scan_at": datetime.utcnow().isoformat()
                        }
                    })
                    
                    # Log status periodically or on first scan
                    if scan_count == 1 or scan_count % 50 == 0:
                        if total_available > 0:
                            await self._log(task_id, "info", f"Scan #{scan_count}: {total_available} tickets available", db)
                            no_tickets_logged = False
                        else:
                            if not no_tickets_logged or scan_count == 1:
                                await self._log(task_id, "info", f"Scan #{scan_count}: No tickets available - waiting for release...", db)
                                no_tickets_logged = True
                    
                    # Only process if there are actually available tickets
                    if data and total_available > 0 and data != previous_data:
                        process_start_time = time.time()
                        previous_data = data
                        no_tickets_logged = False
                        
                        await self._log(task_id, "info", f"Change detected! {total_available} tickets available - processing...", db)
                        
                        # Send Discord notification (async, non-blocking)
                        asyncio.create_task(
                            send_discord_notification(data, product_url)
                        )
                        
                        # Try to buy tickets
                        for date, tickets in data.items():
                            for ticket in tickets:
                                qty_available = ticket['qty_available']
                                if qty_available >= quantity:  # Only try if enough tickets available
                                    await self._log(
                                        task_id, "info",
                                        f"Attempting to buy {quantity} ticket(s) for {date} @ {ticket['time']} ({qty_available} available)", db
                                    )
                                    
                                    time_encoded = quote(ticket['time'], safe='')
                                    time_short = ticket['time'][:5]
                                    variation = ticket['variations'][0] if ticket['variations'] else None
                                    
                                    if not variation:
                                        continue
                                    
                                    option_number = await bot.get_option_number(
                                        event_id, variation, date, time_encoded
                                    )
                                    
                                    if option_number:
                                        # Limit concurrent attempts to available tickets divided by quantity
                                        # This prevents creating more carts than can actually be filled
                                        max_possible_carts = qty_available // quantity
                                        actual_threads = min(num_threads, max(1, max_possible_carts))
                                        
                                        await self._log(
                                            task_id, "info",
                                            f"Running {actual_threads} ATC thread(s) (limited by {max_possible_carts} possible carts)", db
                                        )
                                        
                                        # Run ATC attempts concurrently
                                        tasks = []
                                        for _ in range(actual_threads):
                                            tasks.append(
                                                self._attempt_atc(
                                                    task_id, bot, event_id, date,
                                                    time_short, variation, option_number,
                                                    quantity, product_url, process_start_time, db
                                                )
                                            )
                                        
                                        results = await asyncio.gather(*tasks, return_exceptions=True)
                                        
                                        # Check if any succeeded
                                        if any(r is True for r in results if not isinstance(r, Exception)):
                                            await self._log(
                                                task_id, "success",
                                                "Successfully carted! Sleeping 17 min then will re-cart...", db
                                            )
                                            
                                            # Update task status to success
                                            task = db.query(Task).filter(Task.id == task_id).first()
                                            if task:
                                                task.status = TaskStatus.SUCCESS.value
                                                task.completed_at = datetime.utcnow()
                                                db.commit()
                                            
                                            # Broadcast task update
                                            await self.broadcast({
                                                "type": "task_update",
                                                "data": {"task_id": task_id, "status": "success"}
                                            })
                                            
                                            # Sleep to hold cart (17 minutes)
                                            await asyncio.sleep(settings.cart_hold_time)
                                            
                                            # After cart hold time, restart the task to re-cart
                                            logger.info(f"Task {task_id} cart hold complete, restarting to re-cart...")
                                            await self._log(
                                                task_id, "info",
                                                "Cart hold expired, restarting to re-cart items...", db
                                            )
                                            
                                            # Reset task status to running for re-cart
                                            task = db.query(Task).filter(Task.id == task_id).first()
                                            if task:
                                                task.status = TaskStatus.RUNNING.value
                                                task.completed_at = None
                                                db.commit()
                                            
                                            await self.broadcast({
                                                "type": "task_update",
                                                "data": {"task_id": task_id, "status": "running"}
                                            })
                                            
                                            # Continue the loop to scan again
                                            scan_count = 0  # Reset scan count for new cycle
                                            previous_data = None
                                            no_tickets_logged = False
                                            continue  # Continue the while True loop
                                        
                                        break
                            else:
                                continue
                            break
                    
                    elif data is None or (data and len(data) == 0):
                        # Rate limited, error, or no tickets available
                        await asyncio.sleep(5)
                    
                    # Normal scan interval
                    await asyncio.sleep(settings.default_scan_interval)
                    
        except asyncio.CancelledError:
            logger.info(f"Task {task_id} cancelled")
            raise
        except Exception as e:
            import traceback
            logger.error(f"Task {task_id} error: {e}")
            logger.error(f"Task {task_id} traceback: {traceback.format_exc()}")
            await self._mark_failed(task_id, str(e), db)
        finally:
            # Always clean up from active_tasks when monitor exits
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
                logger.info(f"Task {task_id} removed from active_tasks")
            if task_id in self.task_data:
                del self.task_data[task_id]
            db.close()
    
    async def _attempt_atc(
        self,
        task_id: int,
        bot: AudiTicketBot,
        event_id: str,
        date: str,
        time_short: str,
        variation: str,
        option_number: str,
        quantity: int,
        product_url: str,
        start_time: float,
        db: Session
    ) -> bool:
        """Attempt to add to cart (single thread)."""
        # Create new session for this attempt
        async with AudiTicketBot() as atc_bot:
            success, cookie, error = await atc_bot.add_to_cart(
                event_id, date, time_short, variation,
                option_number, quantity, product_url
            )
            
            if success and cookie:
                total_time = time.time() - start_time
                
                await self._log(
                    task_id, "success",
                    f"Cookie secured: {cookie.name} (Time: {total_time:.2f}s)", db
                )
                
                # Store cart session
                token = secrets.token_urlsafe(32)
                cart_session = CartSession(
                    token=token,
                    task_id=task_id,
                    cookie_name=cookie.name,
                    cookie_value=cookie.value,
                    cookie_domain=cookie.domain,
                    product_url=product_url,
                    checkout_url=f"https://audidefuehrungen2.regiondo.de/checkout/cart",
                    quantity=quantity,
                    total_time=total_time,
                    expires_at=datetime.utcnow() + timedelta(seconds=settings.cart_hold_time)
                )
                db.add(cart_session)
                db.commit()
                
                # Broadcast success
                await self.broadcast({
                    "type": "cart_success",
                    "data": {
                        "task_id": task_id,
                        "token": token,
                        "quantity": quantity,
                        "total_time": total_time
                    }
                })
                
                # Send Discord notification
                await send_discord_cart_success(
                    product_url, cookie, quantity, total_time, token
                )
                
                return True
            else:
                if error:
                    await self._log(task_id, "warning", f"ATC failed: {error}", db)
                return False
    
    async def _mark_failed(self, task_id: int, error: str, db: Session):
        """Mark task as failed."""
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = error
            task.completed_at = datetime.utcnow()
            db.commit()
        
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
        
        await self.broadcast({
            "type": "task_update",
            "data": {"task_id": task_id, "status": "failed", "error": error}
        })


# Global task manager instance
task_manager = TaskManager()
