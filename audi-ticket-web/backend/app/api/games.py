"""
API endpoints for FC Bayern games and scheduled tasks.
"""
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..auth import get_current_user
from ..models import ScheduledTask, Task, TaskStatus
from ..bot.scraper import get_bayern_games

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/games", tags=["games"])

# Cache for games (refresh every 15 minutes)
_games_cache = {
    "data": [],
    "updated_at": None
}
CACHE_TTL = 900  # 15 minutes


class GameResponse(BaseModel):
    id: str
    title: str
    opponent: str
    location: str
    url: str
    image_url: Optional[str]
    match_date: Optional[str]
    match_time: Optional[str]
    sale_date: Optional[str]
    sale_time: str
    is_available: bool
    status: str
    is_scheduled: bool = False
    scheduled_task_id: Optional[int] = None


class ScheduleRequest(BaseModel):
    game_id: str
    quantity: int = 4
    num_threads: int = 5


class ScheduledTaskResponse(BaseModel):
    id: int
    game_id: str
    game_title: str
    product_url: str
    quantity: int
    num_threads: int
    scheduled_date: str
    status: str
    task_id: Optional[int]
    created_at: str


@router.get("", response_model=List[GameResponse])
async def list_games(
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Get all FC Bayern games with their schedule status."""
    global _games_cache
    
    # Check cache
    now = datetime.utcnow()
    if _games_cache["updated_at"] and (now - _games_cache["updated_at"]).seconds < CACHE_TTL:
        games = _games_cache["data"]
    else:
        # Refresh cache
        try:
            games = await get_bayern_games()
            _games_cache["data"] = games
            _games_cache["updated_at"] = now
            logger.info(f"Refreshed games cache: {len(games)} games")
        except Exception as e:
            logger.error(f"Error fetching games: {e}")
            # Return cached data if available
            if _games_cache["data"]:
                games = _games_cache["data"]
            else:
                raise HTTPException(status_code=500, detail="Failed to fetch games")
    
    # Get scheduled tasks
    scheduled = db.query(ScheduledTask).filter(
        ScheduledTask.status.in_(["scheduled", "triggered"])
    ).all()
    scheduled_map = {s.game_id: s for s in scheduled}
    
    # Build response
    result = []
    for g in games:
        is_scheduled = g['id'] in scheduled_map
        scheduled_task = scheduled_map.get(g['id'])
        
        result.append(GameResponse(
            id=g['id'],
            title=g['title'],
            opponent=g['opponent'],
            location=g['location'],
            url=g['url'],
            match_date=g['match_date'],
            match_time=g['match_time'],
            sale_date=g['sale_date'],
            sale_time=g['sale_time'],
            is_available=g['is_available'],
            status=g['status'],
            is_scheduled=is_scheduled,
            scheduled_task_id=scheduled_task.id if scheduled_task else None,
            image_url=g.get('image_url')
        ))
    
    # Sort by sale date (closest first)
    result.sort(key=lambda x: x.sale_date or "9999-99-99")
    
    return result


@router.post("/refresh")
async def refresh_games(
    _: bool = Depends(get_current_user)
):
    """Force refresh the games cache."""
    global _games_cache
    
    try:
        games = await get_bayern_games()
        _games_cache["data"] = games
        _games_cache["updated_at"] = datetime.utcnow()
        return {"success": True, "count": len(games)}
    except Exception as e:
        logger.error(f"Error refreshing games: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule", response_model=ScheduledTaskResponse)
async def schedule_game(
    request: ScheduleRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Schedule a task for a game's sale date."""
    global _games_cache
    
    # Find the game
    game = None
    for g in _games_cache.get("data", []):
        if g['id'] == request.game_id:
            game = g
            break
    
    if not game:
        # Try to refresh and find
        games = await get_bayern_games()
        _games_cache["data"] = games
        _games_cache["updated_at"] = datetime.utcnow()
        
        for g in games:
            if g['id'] == request.game_id:
                game = g
                break
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if not game['sale_date']:
        raise HTTPException(status_code=400, detail="Game has no sale date")
    
    # Check if already scheduled
    existing = db.query(ScheduledTask).filter(
        ScheduledTask.game_id == request.game_id,
        ScheduledTask.status == "scheduled"
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Game already scheduled")
    
    # Parse sale date and set time to 7:00 AM German time
    sale_date = date.fromisoformat(game['sale_date'])
    german_tz = ZoneInfo("Europe/Berlin")
    
    # Create datetime at 7:00 AM German time
    scheduled_local = datetime(sale_date.year, sale_date.month, sale_date.day, 7, 0, 0, tzinfo=german_tz)
    
    # Convert to UTC for storage
    scheduled_utc = scheduled_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    
    # Create scheduled task
    scheduled_task = ScheduledTask(
        game_id=game['id'],
        game_title=game['title'],
        product_url=game['url'],
        quantity=request.quantity,
        num_threads=request.num_threads,
        scheduled_date=scheduled_utc,
        status="scheduled"
    )
    
    db.add(scheduled_task)
    db.commit()
    db.refresh(scheduled_task)
    
    logger.info(f"Scheduled task for {game['title']} at {scheduled_utc} UTC (7:00 AM German)")
    
    return ScheduledTaskResponse(
        id=scheduled_task.id,
        game_id=scheduled_task.game_id,
        game_title=scheduled_task.game_title,
        product_url=scheduled_task.product_url,
        quantity=scheduled_task.quantity,
        num_threads=scheduled_task.num_threads,
        scheduled_date=scheduled_task.scheduled_date.isoformat(),
        status=scheduled_task.status,
        task_id=scheduled_task.task_id,
        created_at=scheduled_task.created_at.isoformat()
    )


@router.get("/scheduled", response_model=List[ScheduledTaskResponse])
async def list_scheduled(
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Get all scheduled tasks."""
    scheduled = db.query(ScheduledTask).order_by(ScheduledTask.scheduled_date).all()
    
    return [
        ScheduledTaskResponse(
            id=s.id,
            game_id=s.game_id,
            game_title=s.game_title,
            product_url=s.product_url,
            quantity=s.quantity,
            num_threads=s.num_threads,
            scheduled_date=s.scheduled_date.isoformat(),
            status=s.status,
            task_id=s.task_id,
            created_at=s.created_at.isoformat()
        )
        for s in scheduled
    ]


@router.delete("/scheduled/{scheduled_id}")
async def cancel_scheduled(
    scheduled_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Cancel a scheduled task."""
    scheduled = db.query(ScheduledTask).filter(ScheduledTask.id == scheduled_id).first()
    
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    
    if scheduled.status != "scheduled":
        raise HTTPException(status_code=400, detail="Task already triggered or completed")
    
    db.delete(scheduled)
    db.commit()
    
    return {"success": True}
