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
from .scraper import get_listing_products, _normalize
from .monitor import task_manager
from .discord import send_discord_new_event

logger = logging.getLogger(__name__)

# If a scan suddenly sees more new URLs than this, treat it as an anomaly
# (first seed, listing glitch, shop rebuild) and reseed WITHOUT auto-carting —
# never mass-fire tasks.
MAX_NEW_PER_SCAN = 8


def _load_known(raw) -> dict:
    """known_urls JSON -> {url: entity_id | None}. Accepts the legacy plain URL
    list (IDs unknown -> next scan reseeds with IDs)."""
    data = json.loads(raw or "{}")
    if isinstance(data, list):
        return {_normalize(u): None for u in data}
    return {_normalize(u): i for u, i in data.items()}


def _classify(known: dict, products: dict):
    """-> (new, reappeared). New = unseen URL whose ID is above every ID seen so
    far. Unseen URLs with an old or unknown ID are reappearances. No known IDs
    yet -> nothing is new (seed)."""
    max_id = max((i for i in known.values() if i), default=None)
    unseen = [u for u in products if u not in known]
    if max_id is None:
        return [], []
    new = sorted(u for u in unseen if products[u] is not None and products[u] > max_id)
    return new, [u for u in unseen if u not in new]


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

    async def _launch_task(self, url: str, cfg: ReleaseDetector) -> int:
        """Create + start a task in its OWN session, so a failed launch (e.g. a
        SQLite lock on commit) can't leave the detector's session in a failed
        transaction and take the whole loop down with it."""
        db = SessionLocal()
        try:
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
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def _scan_once(self, db) -> float:
        """One detector iteration. Returns the sleep interval; raises
        StopAsyncIteration when the detector was switched off."""
        cfg = self._get_cfg(db)
        if not cfg.active:
            raise StopAsyncIteration
        interval = max(3.0, cfg.poll_interval or 10.0)
        known = _load_known(cfg.known_urls)          # {url: entity_id | None}
        max_id = max((i for i in known.values() if i), default=None)

        try:
            products = await get_listing_products()
        except Exception as e:
            # Partial/failed listing: skip the round entirely — never seed or
            # diff on an incomplete product set.
            cfg.error_message = f"scrape failed: {e}"
            cfg.last_scan_at = datetime.utcnow()
            db.commit()
            await self._broadcast(cfg)
            return interval

        cfg.scan_count = (cfg.scan_count or 0) + 1
        cfg.last_scan_at = datetime.utcnow()
        cfg.error_message = None

        # "New" is decided by entity ID, not by URL diff. Regiondo's product ID
        # is a global, monotonically increasing counter: a real release always
        # gets an ID above everything we've seen. Old products that drop out of
        # the listing and come back (dated tours toggle with availability) keep
        # their old, lower ID — those are absorbed silently: no task, no ping.
        acted = []
        if max_id is None:
            # First scan after activation (or legacy list without IDs): seed only.
            logger.info(f"[Detector] seeded {len(products)} existing products (max id "
                        f"{max((i for i in products.values() if i), default='?')})")
        new, reappeared = _classify(known, products)
        if reappeared:
            logger.info(f"[Detector] {len(reappeared)} old product(s) reappeared, ignored")

        if len(new) > MAX_NEW_PER_SCAN:
            # Anomaly (shop rebuild / mass import): absorb, don't fire.
            logger.warning(f"[Detector] {len(new)} new IDs in one scan — absorbing without acting")
            cfg.error_message = f"absorbed {len(new)} new at once (not carted)"
            new = []

        # "+" joins AND-terms: "dortmund+ingolstadt" matches a URL containing
        # BOTH. No terms (empty keyword) matches every new product.
        terms = [t for t in (cfg.keyword or "").lower().replace(" ", "").split("+") if t]
        for url in new:
            lu = url.lower()
            tid = None
            if all(t in lu for t in terms):
                try:
                    tid = await self._launch_task(url, cfg)
                except Exception as e:
                    logger.error(f"[Detector] failed to launch {url}: {e}")
                    cfg.error_message = f"launch failed for {url}: {e}"
            # A genuinely new event always pings Discord; carted flag shows
            # whether it matched the filter and a task started.
            try:
                await send_discord_new_event(url, carted=tid is not None)
            except Exception as e:
                logger.warning(f"[Detector] discord ping failed: {e}")
            if tid is not None:
                acted.append({"url": url, "at": datetime.utcnow().isoformat(), "task_id": tid})

        if acted:
            cfg.last_new_found_at = datetime.utcnow()
            log = json.loads(cfg.events_log or "[]")
            cfg.events_log = json.dumps((acted + log)[:20])

        # Union, never shrink; keep the best-known ID per URL.
        for u, i in products.items():
            if known.get(u) is None:
                known[u] = i
        cfg.known_urls = json.dumps(known, sort_keys=True)
        db.commit()
        await self._broadcast(cfg, acted)
        return interval

    async def _loop(self):
        logger.info("[Detector] loop started")
        try:
            while True:
                interval = 10.0
                db = SessionLocal()
                try:
                    interval = await self._scan_once(db)
                except StopAsyncIteration:
                    logger.info("[Detector] inactive — loop exiting")
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    # One bad iteration (DB lock, unexpected HTML) must not kill
                    # the detector: roll back, record, try again next tick.
                    logger.error(f"[Detector] scan iteration failed: {e}")
                    db.rollback()
                    try:
                        cfg = self._get_cfg(db)
                        cfg.error_message = f"scan failed: {e}"
                        db.commit()
                    except Exception:
                        db.rollback()
                finally:
                    db.close()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("[Detector] loop cancelled")
            raise
        except Exception as e:
            # Truly unexpected: stop cleanly and say so, so the UI never shows
            # "active" for a dead loop.
            logger.error(f"[Detector] loop crashed: {e}")
            db = SessionLocal()
            try:
                cfg = self._get_cfg(db)
                cfg.active = False
                cfg.error_message = f"loop crashed (stopped): {e}"
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
