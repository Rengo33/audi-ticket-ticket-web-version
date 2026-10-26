# --- widget frontier ---
import asyncio, json
from types import SimpleNamespace
from app.bot import release_detector as rd

assert rd._slug("FC BAYERN MÜNCHEN - 1. FC KÖLN (Ingolstadt)") == "fc-bayern-munchen-1-fc-koln-ingolstadt"
assert rd._matches(rd._slug("FC BAYERN MÜNCHEN - 1. FC KÖLN (Ingolstadt)"), "fc-bayern+ingolstadt")
assert not rd._matches("fc-bayern-munchen-1-fc-koln-neckarsulm", "fc-bayern+ingolstadt")

shop = {101: ("Other", "x"), 102: ("AUDI AG", "FC BAYERN MÜNCHEN - 1. FC KÖLN (Ingolstadt)"),
        104: ("AUDI AG", "Audi Racing Simulator")}  # 103 = deleted gap
async def fake_lookup(pid): return shop.get(pid)
started = []
async def fake_act(url, cfg, matched, name="", unreleased=False):
    started.append((url, matched)); return 7 if matched else None
rd.widget_lookup = fake_lookup
m = rd.ReleaseDetectorManager(); m._act = fake_act
cfg = SimpleNamespace(frontier_id=None, launched_ids="{}", keyword="fc-bayern")
acted = asyncio.run(m._scan_frontier(cfg, 100))
assert cfg.frontier_id == 104, cfg.frontier_id            # walked across the 103 gap
assert [a["task_id"] for a in acted] == [7]               # only the wanted game got a task
assert set(json.loads(cfg.launched_ids)) == {"102", "104"}
started.clear(); asyncio.run(m._scan_frontier(cfg, 100))
assert started == []                                      # no re-launch on the next scan

# 16-ID deleted gap (as seen in the real data): stuck first, then crossed after a gap probe
shop2 = {i: ("Other", "x") for i in range(202, 260)}
shop2[201] = ("AUDI AG", "FC BAYERN MÜNCHEN - TEST")   # 185..200 deleted
rd.widget_lookup = lambda pid: fake_lookup2(pid)
async def fake_lookup2(pid): return shop2.get(pid)
m2 = rd.ReleaseDetectorManager(); m2._act = fake_act
cfg2 = SimpleNamespace(frontier_id=184, launched_ids="{}", keyword="fc-bayern")
for _ in range(rd.GAP_PROBE_EVERY + 1):
    asyncio.run(m2._scan_frontier(cfg2, None))
assert cfg2.frontier_id >= 201 and "201" in json.loads(cfg2.launched_ids), cfg2.frontier_id
print("frontier ok")


# first activation: frontier seeded once from the newest listed product, then walked
async def fake_listing(): return {"https://x/a": 100, "https://x/b": None}
rd.get_listing_products = fake_listing
rd.widget_lookup = fake_lookup
async def noop(*a, **k): pass
m4 = rd.ReleaseDetectorManager(); m4._act = fake_act; m4._broadcast = noop
cfg4 = SimpleNamespace(active=True, poll_interval=10, frontier_id=None, launched_ids="{}",
                       keyword="fc-bayern", scan_count=0, events_log="[]",
                       last_scan_at=None, last_new_found_at=None, error_message=None)
m4._get_cfg = lambda db: cfg4
asyncio.run(m4._scan_once(SimpleNamespace(commit=lambda: None)))
assert cfg4.frontier_id == 104 and "102" in json.loads(cfg4.events_log)[0]["url"], cfg4.frontier_id
print("seed ok")
