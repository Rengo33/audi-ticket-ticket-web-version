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


class NextGameResponse(BaseModel):
    opponent: str
    location: str
    match_date: Optional[str]
    match_time: Optional[str]
    kickoff_utc: Optional[str]


def _kickoff_utc(game: dict) -> Optional[datetime]:
    """Combine match_date (YYYY-MM-DD) + match_time (HH:MM) as Europe/Berlin, return UTC naive."""
    md, mt = game.get("match_date"), game.get("match_time")
    if not md or not mt:
        return None
    try:
        local = datetime.fromisoformat(f"{md}T{mt}:00").replace(tzinfo=ZoneInfo("Europe/Berlin"))
        return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    except ValueError:
        return None


async def _ensure_games_cache() -> list:
    """Return games list from cache or refresh if stale. Falls back to stale cache on scrape error."""
    global _games_cache
    now = datetime.utcnow()
    if _games_cache["updated_at"] and (now - _games_cache["updated_at"]).total_seconds() < CACHE_TTL:
        return _games_cache["data"]
    try:
        games = await get_bayern_games()
        _games_cache["data"] = games
        _games_cache["updated_at"] = now
        logger.info(f"Refreshed games cache: {len(games)} games")
        return games
    except Exception as e:
        logger.error(f"Error fetching games: {e}")
        if _games_cache["data"]:
            return _games_cache["data"]
        raise HTTPException(status_code=500, detail="Failed to fetch games")


@router.get("/next", response_model=Optional[NextGameResponse])
async def next_game():
    """Public headline for the Login scoreboard — next upcoming FCB fixture."""
    try:
        games = await _ensure_games_cache()
    except HTTPException:
        return None
    now_utc = datetime.utcnow()
    upcoming = [(g, _kickoff_utc(g)) for g in games]
    upcoming = [(g, k) for g, k in upcoming if k and k > now_utc]
    if not upcoming:
        return None
    g, k = min(upcoming, key=lambda gk: gk[1])
    return NextGameResponse(
        opponent=g["opponent"],
        location=g["location"],
        match_date=g.get("match_date"),
        match_time=g.get("match_time"),
        kickoff_utc=k.isoformat() + "Z",
    )


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
    price_categories: Optional[list] = None
    is_scheduled: bool = False
    scheduled_count: int = 0
    scheduled_task_id: Optional[int] = None


class ScheduleRequest(BaseModel):
    game_id: str
    quantity: int = 4
    num_threads: int = 5
    price_category: int = 0
    auto_checkout: bool = False
    billing_profile_id: Optional[str] = None


class ScheduledTaskResponse(BaseModel):
    id: int
    game_id: str
    game_title: str
    product_url: str
    quantity: int
    num_threads: int
    price_category: int = 0
    scheduled_date: str
    status: str
    task_id: Optional[int]
    created_at: str

    @classmethod
    def from_model(cls, s) -> 'ScheduledTaskResponse':
        return cls(
            id=s.id, game_id=s.game_id, game_title=s.game_title,
            product_url=s.product_url, quantity=s.quantity,
            num_threads=s.num_threads, price_category=s.price_category or 0,
            scheduled_date=s.scheduled_date.isoformat(), status=s.status,
            task_id=s.task_id, created_at=s.created_at.isoformat()
        )


@router.get("", response_model=List[GameResponse])
async def list_games(
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Get all FC Bayern games with their schedule status."""
    games = await _ensure_games_cache()

    # Get scheduled tasks (group by game_id)
    scheduled = db.query(ScheduledTask).filter(
        ScheduledTask.status.in_(["scheduled", "triggered"])
    ).all()
    scheduled_by_game = {}
    for s in scheduled:
        scheduled_by_game.setdefault(s.game_id, []).append(s)

    # Build response
    result = []
    for g in games:
        game_scheduled = scheduled_by_game.get(g['id'], [])

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
            is_scheduled=len(game_scheduled) > 0,
            scheduled_count=len(game_scheduled),
            scheduled_task_id=game_scheduled[0].id if game_scheduled else None,
            image_url=g.get('image_url'),
            price_categories=g.get('price_categories')
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
    games = await _ensure_games_cache()
    game = next((g for g in games if g['id'] == request.game_id), None)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if not game['sale_date']:
        raise HTTPException(status_code=400, detail="Game has no sale date")
    
    # Parse sale date and set time to 5:55 AM German time (= 03:55 UTC in summer)
    sale_date = date.fromisoformat(game['sale_date'])
    german_tz = ZoneInfo("Europe/Berlin")

    # Create datetime at 5:55 AM German time
    scheduled_local = datetime(sale_date.year, sale_date.month, sale_date.day, 5, 55, 0, tzinfo=german_tz)

    # Convert to UTC for storage
    scheduled_utc = scheduled_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    
    # Create scheduled task
    scheduled_task = ScheduledTask(
        game_id=game['id'],
        game_title=game['title'],
        product_url=game['url'],
        quantity=request.quantity,
        num_threads=request.num_threads,
        price_category=request.price_category,
        auto_checkout=request.auto_checkout,
        billing_profile_id=request.billing_profile_id,
        scheduled_date=scheduled_utc,
        status="scheduled"
    )
    
    db.add(scheduled_task)
    db.commit()
    db.refresh(scheduled_task)
    
    logger.info(f"Scheduled task for {game['title']} at {scheduled_utc} UTC (5:55 AM German)")
    
    return ScheduledTaskResponse.from_model(scheduled_task)


@router.get("/scheduled", response_model=List[ScheduledTaskResponse])
async def list_scheduled(
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Get all scheduled tasks."""
    scheduled = db.query(ScheduledTask).order_by(ScheduledTask.scheduled_date).all()
    
    return [ScheduledTaskResponse.from_model(s) for s in scheduled]


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
    
    if scheduled.status == "triggered" and scheduled.task_id:
        from ..bot.monitor import task_manager
        await task_manager.stop_task(scheduled.task_id, db)
    elif scheduled.status != "scheduled":
        raise HTTPException(status_code=400, detail="Task already completed")

    db.delete(scheduled)
    db.commit()

    return {"success": True}
