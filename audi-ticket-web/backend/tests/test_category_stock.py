# --- the add-to-cart decides on the chosen category's own stock, not the slot total ---
import asyncio
from app.bot import monitor as mon

SLOT = lambda qty, vids: {"2026-11-20": [{"time": "20:30:00", "variations": vids, "qty_available": qty}]}
TOTAL = SLOT(2, [824386, 824387])          # Köln Neckarsulm: 2 = 2 + 0
CATS = {"824386": SLOT(2, [824386]), "824387": SLOT(0, [824387])}


class FakeBot:
    def __init__(self): self.calls = []
    async def get_available_tickets(self, event_id, ticket_id, variation_id=None):
        self.calls.append(variation_id)
        return CATS[variation_id] if variation_id else TOTAL


class FakeManager:
    def __init__(self): self.atc = []
    async def _log(self, *a): pass
    async def _attempt_atc(self, task_id, bot, event_id, date, time_, variation, *rest):
        self.atc.append(variation)
        return False


saved = mon.SessionLocal
mon.SessionLocal = lambda: type("DB", (), {"close": lambda s: None})()
try:
    assert mon._category_qty(CATS, 824387, "2026-11-20", "20:30:00", 2) == 0
    assert mon._category_qty({}, 824387, "2026-11-20", "20:30:00", 2) == 2   # no category number: total

    m = FakeManager()
    w = mon.AvailabilityWatcher("346053", "373631", "https://x", manager=m)
    w._bot = FakeBot()
    w._option_cache = {"824386": "1", "824387": "2"}
    w.add_subscriber(mon.TaskSubscriber(1, "https://x", 1, 1, price_category=1))

    data, cats = asyncio.run(w._scan())           # first scan learns the category IDs
    assert cats == {} and w._variations == ["824386", "824387"]
    data, cats = asyncio.run(w._scan())           # then reads the subscribed category
    assert w._bot.calls[-1] == "824387" and cats == {"824387": CATS["824387"]}

    sub = w.subscribers[1]
    asyncio.run(w._handle_availability(sub, data, 0, cats))
    assert m.atc == [], "sold-out category must not fire an add"

    sub.price_category = 0
    asyncio.run(w._handle_availability(sub, data, 0, {"824386": CATS["824386"]}))
    assert m.atc == [824386]
finally:
    mon.SessionLocal = saved
print("category stock ok")
