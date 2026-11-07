# --- stock alert carries 1×–4× cart links per category (open = cart in your own browser) ---
from app.bot.discord import _category_field, cart_link

url = cart_link("346054", "2026-11-20", "20:30:00", "824388", "2321611", 2)
assert url == ("https://audidefuehrungen2.regiondo.de/checkout/ajaxcart/ajaxadd/product/346054"
               "?ticket_date=2026-11-20&ticket_time=20:30&ticket_variation=824388"
               "&ticket_option_qty%5B2321611%5D=2"), url
assert "ticket_time=10:00-16:00&" in cart_link("1", "d", "10:00:00-16:00:00", "v", "o", 1)

cats = [{"title": "Block 237 - Kategorie 3", "available": 16, "capacity": 180, "variation_id": "824388", "option_id": "2321611", "max_qty": 4},
        {"title": "Block 328 - Kategorie 1", "available": 3, "capacity": 20, "variation_id": "824390", "option_id": "2321615", "max_qty": 4},
        {"title": "Block 136 - Kategorie 1", "available": 0, "capacity": 80, "variation_id": "824389", "option_id": "2321613", "max_qty": 4}]
f = _category_field(cats, ("346054", "2026-11-20", "20:30:00"))
assert [x["name"] for x in f] == [c["title"] for c in cats]
assert f[0]["value"].count("](") == 4 and "[4×](" in f[0]["value"]
assert f[1]["value"].count("](") == 3, "never more links than tickets left"
assert "🛒" not in f[2]["value"], "no links for a sold-out category"
assert all(len(x["value"]) <= 1024 for x in f), "Discord field limit"
assert "🛒" not in _category_field(cats)[0]["value"], "no slot, no links"
print("cart links ok")
