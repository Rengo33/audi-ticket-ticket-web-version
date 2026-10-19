from app.bot.release_detector import _classify

known = {"a": 100, "b": 200}
# old product reappearing with its old ID is not new
assert _classify(known, {"a": 100, "b": 200, "old": 150}) == ([], ["old"])
# ID above max is new; unknown ID is ignored
assert _classify(known, {"new": 201, "x": None}) == (["new"], ["x"])
# no known IDs yet (first scan / legacy list) -> seed only
assert _classify({"a": None}, {"z": 999}) == ([], [])
print("ok")

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
print("frontier ok")
