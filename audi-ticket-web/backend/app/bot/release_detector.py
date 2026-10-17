"""
Release detector — watches the shop listing for newly-published products and
auto-starts a monitoring task for each one (reusing the normal ATC/ACO path).

Discovery = diff the listing's product-URL set against what we've seen. New URL
= new event. A keyword substring (default "fc-bayern") decides which new
products to act on, so a new museum tour doesn't trigger a cart.
"""
import asyncio
import json
import logging
from datetime import datetime

from ..database import SessionLocal
from ..models import Task, ReleaseDetector
from .scraper import get_listing_product_urls
from .monitor import task_manager
from .discord import send_discord_new_event

logger = logging.getLogger(__name__)

# If a scan suddenly sees more new URLs than this, treat it as an anomaly
# (first seed, listing glitch, shop rebuild) and reseed WITHOUT auto-carting —
# never mass-fire tasks.
MAX_NEW_PER_SCAN = 8


class ReleaseDetectorManager:
    def __init__(self):
        self._task: asyncio.Task | None = None

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def _get_cfg(self, db) -> ReleaseDetector:
        cfg = db.query(ReleaseDetector).filter(ReleaseDetector.id == 1).first()
        if not cfg:
            cfg = ReleaseDetector(id=1)
            db.add(cfg)
            db.commit()
            db.refresh(cfg)
        return cfg

    async def start(self, db) -> bool:
        cfg = self._get_cfg(db)
        cfg.active = True
        cfg.error_message = None
        db.commit()
        if not self.is_running():
            self._task = asyncio.create_task(self._loop())
        return True

    async def stop(self, db) -> bool:
        cfg = self._get_cfg(db)
        cfg.active = False
        db.commit()
        if self._task:
            self._task.cancel()
            self._task = None
        return True

    async def _launch_task(self, url: str, cfg: ReleaseDetector, db) -> int:
        task = Task(
            product_url=url,
            quantity=cfg.quantity or 1,
            num_threads=cfg.num_threads or 1,
            price_category=cfg.price_category or 0,
            auto_checkout=bool(cfg.auto_checkout),
            billing_profile_id=cfg.billing_profile_id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        await task_manager.start_task(task, db)
        logger.info(f"[Detector] new product {url} -> task {task.id}")
        return task.id

    async def _loop(self):
        logger.info("[Detector] loop started")
        try:
            while True:
                interval = 10.0
                db = SessionLocal()
                try:
                    cfg = self._get_cfg(db)
                    if not cfg.active:
                        logger.info("[Detector] inactive — loop exiting")
                        return
                    interval = max(3.0, cfg.poll_interval or 10.0)
                    known = set(json.loads(cfg.known_urls or "[]"))

                    try:
                        urls = set(await get_listing_product_urls())
                    except Exception as e:
                        cfg.error_message = f"scrape failed: {e}"
                        cfg.last_scan_at = datetime.utcnow()
                        db.commit()
                        await self._broadcast(cfg)
                        await asyncio.sleep(interval)
                        continue

                    cfg.scan_count = (cfg.scan_count or 0) + 1
                    cfg.last_scan_at = datetime.utcnow()
                    cfg.error_message = None

                    acted = []
                    new = sorted(urls - known) if known else []
                    if not known:
                        # First scan after activation: seed only, never cart what
                        # already exists.
                        logger.info(f"[Detector] seeded {len(urls)} existing products")
                    elif len(new) > MAX_NEW_PER_SCAN:
                        # Anomaly (listing glitch / shop rebuild). Absorb into known
                        # via the union below, but don't fire tasks or pings.
                        logger.warning(
                            f"[Detector] {len(new)} new URLs in one scan — anomaly, "
                            f"absorbing without acting"
                        )
                        cfg.error_message = f"absorbed {len(new)} new at once (not carted)"
                    else:
                        # "+" joins AND-terms: "dortmund+ingolstadt" matches a URL
                        # containing BOTH. No terms (empty keyword) matches every
                        # new product.
                        terms = [t for t in (cfg.keyword or "").lower().replace(" ", "").split("+") if t]
                        for url in new:
                            lu = url.lower()
                            matched = all(t in lu for t in terms)
                            tid = None
                            if matched:
                                try:
                                    tid = await self._launch_task(url, cfg, db)
                                except Exception as e:
                                    logger.error(f"[Detector] failed to launch {url}: {e}")
                            # A found event always pings Discord; carted flag shows
                            # whether it matched the filter and a task started.
                            try:
                                await send_discord_new_event(url, carted=tid is not None)
                            except Exception as e:
                                logger.warning(f"[Detector] discord ping failed: {e}")
                            if tid is not None:
                                acted.append({
                                    "url": url,
                                    "at": datetime.utcnow().isoformat(),
                                    "task_id": tid,
                                })

                    if acted:
                        cfg.last_new_found_at = datetime.utcnow()
                        log = json.loads(cfg.events_log or "[]")
                        cfg.events_log = json.dumps((acted + log)[:20])

                    # UNION, never overwrite: once a URL is known it stays known, so
                    # a scrape that transiently misses products can't resurface them
                    # as "new". `known` only ever grows.
                    cfg.known_urls = json.dumps(sorted(known | urls))
                    db.commit()
                    await self._broadcast(cfg, acted)
                finally:
                    db.close()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("[Detector] loop cancelled")
            raise
        except Exception as e:
            logger.error(f"[Detector] loop crashed: {e}")
            # Mark inactive so the watchdog/UI reflects reality.
            db = SessionLocal()
            try:
                cfg = self._get_cfg(db)
                cfg.error_message = f"loop crashed: {e}"
                db.commit()
            finally:
                db.close()

    async def _broadcast(self, cfg: ReleaseDetector, acted=None):
        await task_manager.broadcast({
            "type": "detector_update",
            "data": {
                "active": cfg.active,
                "scan_count": cfg.scan_count,
                "last_scan_at": cfg.last_scan_at.isoformat() if cfg.last_scan_at else None,
                "last_new_found_at": cfg.last_new_found_at.isoformat() if cfg.last_new_found_at else None,
                "known_count": len(json.loads(cfg.known_urls or "[]")),
                "error": cfg.error_message,
                "new": acted or [],
            },
        })


release_detector = ReleaseDetectorManager()
