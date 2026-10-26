"""
Release detector — discovers new Audi products the moment they are CREATED
(long before publication) and auto-starts a monitoring task for each one. The
task itself waits for the product to go live and carts through the normal path.

Discovery = walk Regiondo's global product-ID counter through the booking
widget, which answers for unpublished products too. A keyword (default
"fc-bayern") on the product name decides which new products get a task, so a
new museum tour doesn't trigger a cart.
"""
import asyncio
import json
import re
import logging
from datetime import datetime

from ..database import SessionLocal
from ..models import Task, ReleaseDetector
from .scraper import get_listing_products, widget_lookup, product_view_url
from .monitor import task_manager
from .discord import send_discord_new_event

logger = logging.getLogger(__name__)

# Widget frontier: max IDs walked per scan (catch-up after downtime spreads over
# several scans), and how far past a 404 to look before deciding we're at the
# end — a deleted product leaves a permanent 404 gap in the global counter.
FRONTIER_STEP = 25
FRONTIER_LOOKAHEAD = 2
# Deleted products leave runs of 404s (seen up to 16 in a row). Every few scans,
# while stuck at the frontier, probe further ahead; a hit means "gap", and the
# next scan walks across it.
GAP_PROBE_EVERY = 6
GAP_PROBES = (5, 10, 20, 40)
AUDI_VENDOR = "AUDI AG"  # exact: substring would hit e.g. "Via Claudia Augusta"


def _slug(name: str) -> str:
    """Product name -> the shop's URL-slug style, so one keyword works for both
    sources: "FC BAYERN MÜNCHEN - 1. FC KÖLN (Ingolstadt)" -> "fc-bayern-munchen-1-fc-koln-ingolstadt"."""
    s = name.lower()
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _matches(text: str, keyword: str) -> bool:
    """"+" joins AND-terms: "dortmund+ingolstadt" needs both. Empty = match all."""
    terms = [t for t in (keyword or "").lower().replace(" ", "").split("+") if t]
    return all(t in text.lower() for t in terms)


class ReleaseDetectorManager:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._gap_skip = 0   # extra misses tolerated next scan (set by a gap probe)
        self._scans = 0

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

        start_id = None
        if cfg.frontier_id is None:
            # First activation only: start walking from the newest listed
            # product, so existing products never trigger.
            try:
                start_id = max((i for i in (await get_listing_products()).values() if i), default=None)
            except Exception as e:
                cfg.error_message = f"seed failed: {e}"
                cfg.last_scan_at = datetime.utcnow()
                db.commit()
                await self._broadcast(cfg)
                return interval
            logger.info(f"[Detector] seeded frontier at {start_id}")

        cfg.scan_count = (cfg.scan_count or 0) + 1
        cfg.last_scan_at = datetime.utcnow()
        cfg.error_message = None

        acted = await self._scan_frontier(cfg, start_id)
        if acted:
            cfg.last_new_found_at = datetime.utcnow()
            log = json.loads(cfg.events_log or "[]")
            cfg.events_log = json.dumps((acted + log)[:20])
        db.commit()
        await self._broadcast(cfg, acted)
        return interval

    async def _act(self, url: str, cfg: ReleaseDetector, matched: bool,
                   name: str = "", unreleased: bool = False):
        """Start a task if wanted, always ping Discord. Returns the task id or None."""
        tid = None
        if matched:
            try:
                tid = await self._launch_task(url, cfg)
            except Exception as e:
                logger.error(f"[Detector] failed to launch {url}: {e}")
                cfg.error_message = f"launch failed for {url}: {e}"
        try:
            await send_discord_new_event(url, carted=tid is not None, name=name, unreleased=unreleased)
        except Exception as e:
            logger.warning(f"[Detector] discord ping failed: {e}")
        return tid

    async def _scan_frontier(self, cfg: ReleaseDetector, start_id):
        """Walk the global product counter past the highest ID seen, resolving
        each new ID through the booking widget. A wanted Audi game gets its task
        right away; the task waits until the product is publicly live and then
        carts through the normal path. Normally one 404 request per scan."""
        fid = cfg.frontier_id or start_id
        if fid is None:
            return []
        launched = json.loads(cfg.launched_ids or "{}")
        acted, pid, misses, start = [], fid + 1, 0, fid
        allowed = FRONTIER_LOOKAHEAD + self._gap_skip
        self._scans += 1
        try:
            while pid <= start + max(FRONTIER_STEP, allowed + 5) and misses <= allowed:
                res = await widget_lookup(pid)
                if res is None:
                    misses += 1
                else:
                    misses, fid = 0, pid
                    vendor, name = res
                    if vendor.strip().upper() == AUDI_VENDOR and str(pid) not in launched:
                        url = product_view_url(pid)
                        logger.info(f"[Detector] widget: new Audi product {pid} {name!r}")
                        tid = await self._act(url, cfg, _matches(_slug(name), cfg.keyword),
                                              name=name, unreleased=True)
                        launched[str(pid)] = name
                        if tid is not None:
                            acted.append({"url": url, "name": name,
                                          "at": datetime.utcnow().isoformat(), "task_id": tid})
                pid += 1
            if fid > start:
                self._gap_skip = 0
            elif self._scans % GAP_PROBE_EVERY == 0:
                for off in GAP_PROBES:
                    if await widget_lookup(fid + off) is not None:
                        logger.info(f"[Detector] ID gap after {fid}, crossing up to +{off}")
                        self._gap_skip = off
                        break
        except Exception as e:
            # Keep progress so far; retry the rest next scan.
            logger.warning(f"[Detector] frontier scan stopped at {pid}: {e}")
        cfg.frontier_id = fid
        cfg.launched_ids = json.dumps(launched, sort_keys=True)
        return acted

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
                "frontier_id": cfg.frontier_id,
                "error": cfg.error_message,
                "new": acted or [],
            },
        })


release_detector = ReleaseDetectorManager()
