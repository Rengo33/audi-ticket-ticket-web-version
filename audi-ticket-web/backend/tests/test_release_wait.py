# --- release wait: a placeholder enable (status 1, product API 404) must not count as live ---
import asyncio
from app.bot import monitor as mon

states = iter([
    {"entity_id": "9", "status": "2", "updated_at": "a"},   # hidden
    {"entity_id": "9", "status": "1", "updated_at": "a"},   # placeholder: enabled, API still 404
    {"entity_id": "9", "status": "2", "updated_at": "a"},   # hidden again
    {"entity_id": "9", "status": "1", "updated_at": "a"},   # enabled + API 200 = live
])
api_calls = []


class FakeBot:
    last_ok = 0
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def api_ticket_id(self, pid):
        api_calls.append(pid)
        return "T1" if len(api_calls) == 2 else None   # 404 on the first enable, 200 on the second
    async def extract_event_details(self, url):
        raise AssertionError("shop page must not be used while the widget route answers")
    def raise_if_blocked(self): pass


async def fake_widget_product(pid): return next(states)

saved = {k: getattr(mon, k) for k in ("widget_product", "AudiTicketBot", "SessionLocal", "RELEASE_RECHECK_S", "RELEASE_FAST_S")}
mon.widget_product = fake_widget_product
mon.AudiTicketBot = FakeBot
mon.RELEASE_RECHECK_S = mon.RELEASE_FAST_S = 0
mon.SessionLocal = lambda: type("DB", (), {"query": lambda *a: type("Q", (), {"filter": lambda *a: type("U", (), {"update": lambda *a, **k: None})()})(),
                                       "commit": lambda s: None, "close": lambda s: None, "add": lambda *a: None, "rollback": lambda s: None})()

tm = mon.TaskManager()
url = "https://x/catalog/product/view/id/9"
tm._release_waiters[url] = {1}
try:
    result = asyncio.run(tm._poll_release(url))
finally:
    for k, v in saved.items():
        setattr(mon, k, v)
assert result == ("9", "T1", []), result
assert len(api_calls) == 2, api_calls          # API asked only while the shop record said enabled
print("release wait ok")
