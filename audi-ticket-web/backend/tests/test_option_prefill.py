# --- option IDs are prefetched per category before the sale; a failed prefetch must not stop the watcher ---
import asyncio
from app.bot import monitor as mon

saved = mon.option_ids


async def fake_option_ids(pid): return {"824388": "2321611", "824389": "2321613"}
async def broken_option_ids(pid): raise RuntimeError("down")

try:
    w = mon.AvailabilityWatcher("346054", "373632", "https://x", manager=None)
    mon.option_ids = fake_option_ids
    asyncio.run(w._prefill_options())
    # keyed by variation alone: the add-to-cart reads _option_cache[str(variation)]
    assert w._option_cache == {"824388": "2321611", "824389": "2321613"}, w._option_cache
    assert w._option_cache.get(str(824388)) == "2321611"

    w2 = mon.AvailabilityWatcher("346054", "373632", "https://x", manager=None)
    mon.option_ids = broken_option_ids
    asyncio.run(w2._prefill_options())          # logs and falls back to the lookup at release
    assert w2._option_cache == {}
finally:
    mon.option_ids = saved
print("option prefill ok")
