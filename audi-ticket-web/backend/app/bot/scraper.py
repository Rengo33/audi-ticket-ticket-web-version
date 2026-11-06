"""
FC Bayern games (from Regiondo's product API) plus the shop listing and
booking-widget lookups the release detector uses.
"""
import asyncio
import html
import re
import json
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Iterable, Tuple
from dataclasses import dataclass, asdict
from zoneinfo import ZoneInfo

from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

from .core import PRODUCT_API, PRODUCT_API_HEADERS, shop_curl_options

logger = logging.getLogger(__name__)


@dataclass
class BayernGame:
    """FC Bayern game information."""
    id: str  # Generated from URL
    title: str
    opponent: str
    location: str  # Ingolstadt or Neckarsulm
    url: str
    image_url: Optional[str]  # Team matchup image
    match_date: Optional[date]
    match_time: Optional[str]
    sale_date: Optional[date]
    sale_time: str = "07:00"  # Default 7 AM
    is_available: bool = False
    status: str = "upcoming"  # upcoming, on_sale, sold_out
    price_categories: Optional[List[Dict[str, Any]]] = None  # [{name, price}, ...]
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Convert dates to strings for JSON serialization
        if d['match_date']:
            d['match_date'] = d['match_date'].isoformat()
        if d['sale_date']:
            d['sale_date'] = d['sale_date'].isoformat()
        return d


# Games come from Regiondo's product API (no Cloudflare) instead of scraping
# /kategorien + every product page through the shop host, which Cloudflare
# 403s from the server IP for hours ("Page 1 returned 403" -> 0 games).
PRODUCT_LIST = PRODUCT_API.rsplit("/", 1)[0]
DATES_URL = ("https://regiondo.net/product/catalog_ajax/dates/id/{}/"
             "?___store=wl_de&ticket_id={}&availabilityType=starttime")
# Case-insensitive: the shop switched the product titles to all caps
# ("FC BAYERN MÜNCHEN - RB LEIPZIG (Ingolstadt)").
_TITLE_RE = re.compile(r"FC Bayern München\s*[-–]\s*(.+?)\s*\((\w+)\)", re.I)
# Description line: "Freitag, 20.11.2026 | Anstoß: 20:30 Uhr"
_KICKOFF_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s*\|\s*Ansto\S*\s*(\d{1,2}:\d{2})")
# First "1. Oktober 2026" after VERKAUFSSTART; the words in between vary
# ("VERKAUFSSTART GEPLANT FÜR: DONNERSTAG, 01. OKTOBER 2026").
_SALE_RE = re.compile(r"VERKAUFSSTART[^<]{0,60}?(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\s+(\d{4})", re.I)
_PRICE_RE = re.compile(r"(Kategorie\s+\d+\s*-\s*Block\s+\d+):\s*([\d,.]+)\s*(?:Euro|€)")
# "Zeitraum der Abholung: Freitag, 04.12.2026 bis Dienstag, 08.12.2026 jeweils von 08:00 Uhr bis 16:00 Uhr"
_PICKUP_RE = re.compile(r"Zeitraum der Abholung:\s*(.+?)\s+jeweils von\s+(.+?Uhr\s+bis\s+.+?Uhr)")
_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
}


async def _api_products(s: AsyncSession, include_inactive: bool) -> list:
    url = f"{PRODUCT_LIST}?limit=250" + ("&includeInactive=true" if include_inactive else "")
    r = await s.get(url, headers=PRODUCT_API_HEADERS)
    if r.status_code != 200:
        raise RuntimeError(f"product API list returned {r.status_code}")
    return r.json().get("items", [])


async def _stock(s: AsyncSession, pid: str) -> Optional[int]:
    """Tickets left right now: ticket id from the API's SKU, stock from
    catalog_ajax/dates on regiondo.net (same data as the shop, no Cloudflare).
    None when either step fails."""
    r = await s.get(PRODUCT_API.format(pid), headers=PRODUCT_API_HEADERS)
    if r.status_code != 200:
        return None
    ticket_id = (r.json().get("manufacturerSku") or "").rsplit("-", 1)[-1]
    if not ticket_id:
        return None
    r = await s.get(DATES_URL.format(pid, ticket_id))
    m = re.search(r"ticket\.setAvailableDateTimes\((\{.*?\})\);", r.text, re.S)
    if r.status_code != 200 or not m:
        return None
    return sum(max(0, t.get("qty_available", 0)) for ts in json.loads(m.group(1)).values() for t in ts)


def _parse_game(item: dict) -> BayernGame:
    """Build a game from one product-list item (title + description only)."""
    pid, title = str(item["id"]), item.get("title") or ""
    desc = item.get("description") or ""
    text = html.unescape(re.sub(r"<[^>]+>", " ", desc))

    m = _TITLE_RE.search(title)
    opponent = m.group(1).strip() if m else re.sub(r"(?i)fc bayern münchen", "", title).strip(" -–")
    location = m.group(2).strip() if m else ""

    match_date = match_time = None
    k = _KICKOFF_RE.search(text)
    if k:
        try:
            match_date = date(int(k.group(3)), int(k.group(2)), int(k.group(1)))
            match_time = k.group(4).zfill(5)
        except ValueError:
            pass

    sale_date = None
    sm = _SALE_RE.search(text)
    if sm and sm.group(2).lower() in _MONTHS:
        try:
            sale_date = date(int(sm.group(3)), _MONTHS[sm.group(2).lower()], int(sm.group(1)))
        except ValueError:
            pass

    prices, seen = [], set()
    for name, price in _PRICE_RE.findall(text):
        if name not in seen:
            seen.add(name)
            prices.append({"name": name.strip(), "price": float(price.replace(",", "."))})

    images = item.get("images") or []
    return BayernGame(
        id=pid, title=title, opponent=opponent, location=location,
        url=product_view_url(int(pid)),
        image_url=images[0].get("url") if images else None,
        match_date=match_date, match_time=match_time, sale_date=sale_date,
        price_categories=prices or None,
    )


def _widget_item(rec: dict) -> dict:
    """A widget product record in the product-list item shape _parse_game reads."""
    return {
        "id": rec["entity_id"], "title": rec.get("name") or "",
        "description": rec.get("description") or "",
        "images": [{"url": CDN_MEDIA + rec["image"]}] if rec.get("image") else [],
    }


def product_facts(rec: dict) -> Dict[str, str]:
    """Kickoff, pickup window and category prices of a widget product record,
    for alerts about products that are not public yet. Missing parts are left out."""
    g = _parse_game(_widget_item(rec))
    text = html.unescape(re.sub(r"<[^>]+>", " ", rec.get("description") or ""))
    facts = {}
    if g.match_date:
        facts["kickoff"] = g.match_date.strftime("%d.%m.%Y") + (f" {g.match_time}" if g.match_time else "")
    p = _PICKUP_RE.search(re.sub(r"\s+", " ", text))
    if p:
        facts["pickup"] = f"{p.group(1)}, {p.group(2)}"
    if g.price_categories:
        facts["prices"] = ", ".join(f"{c['name']}: {c['price']:.0f} €" for c in g.price_categories)
    return facts


async def get_bayern_games(location_filter: Optional[str] = "Ingolstadt",
                           hidden_ids: Iterable = ()) -> List[Dict[str, Any]]:
    """Upcoming FC Bayern games as dicts. Raises when the product API fails,
    so the caller keeps its last good list instead of caching 0 games.

    Status: "sold_out" when the API labels the sale ended, or the sale is
    running with no stock left; "on_sale" with stock; otherwise "upcoming".
    `hidden_ids` (products the release detector found before publication) are
    read from the widget route and listed as "upcoming" while still hidden.
    `location_filter=None` returns every location."""
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    async with AsyncSession(impersonate="safari17_2_ios", timeout=30) as s:
        listed, active = await asyncio.gather(_api_products(s, True), _api_products(s, False))
        active_ids = {str(i["id"]) for i in active}

        listed_ids = {str(i["id"]) for i in listed}
        recs = await asyncio.gather(
            *(widget_product(pid) for pid in hidden_ids if str(pid) not in listed_ids),
            return_exceptions=True,
        )
        hidden = [r for r in recs if isinstance(r, dict) and r.get("status") != "1"]
        hidden_set = {r["entity_id"] for r in hidden}
        listed = listed + [_widget_item(r) for r in hidden]

        games, ended = [], set()
        for item in listed:
            if "fc bayern" not in (item.get("title") or "").lower():
                continue
            g = _parse_game(item)
            if location_filter and g.location.lower() != location_filter.lower():
                continue
            is_ended = (item.get("label") or {}).get("type") == "sale-ended"
            # Past fixtures stay in the API for months; an ended sale without
            # a readable date is one of them.
            if (g.match_date and g.match_date < today) or (is_ended and not g.match_date):
                continue
            if is_ended:
                ended.add(g.id)
            games.append(g)

        # Stock only for games whose sale is not over: 2 small requests each.
        live = [g for g in games if g.id not in ended and g.id not in hidden_set]
        stocks = await asyncio.gather(*(_stock(s, g.id) for g in live), return_exceptions=True)

    stock_by_id = {g.id: q for g, q in zip(live, stocks) if isinstance(q, int)}
    for g in games:
        qty = stock_by_id.get(g.id, 0)
        if g.id in ended:
            g.status = "sold_out"
        elif qty > 0:
            g.status, g.is_available = "on_sale", True
        elif g.sale_date and g.sale_date > today:
            g.status = "upcoming"
        elif g.id in active_ids:
            g.status = "sold_out"
        else:
            g.status = "upcoming"

    logger.info(f"Found {len(games)} FC Bayern games (location: {location_filter or 'all'})")
    return [g.to_dict() for g in games]


BASE_URL = "https://audidefuehrungen2.regiondo.de"


async def get_listing_products() -> Dict[str, Optional[int]]:
    """Light discovery for the release detector: every product on the shop
    listing as {url: entity_id}, with NO per-product detail fetch. Just the
    3 `/kategorien` pages. entity_id comes from the GTM dataLayer and is None
    for a product only found via its anchor.

    Parses the GTM `productClick` dataLayer (`window.location='<product url>'`),
    which is emitted once per product tile and is precise (no nav links). Falls
    back to fc-bayern <a href> links if the dataLayer shape ever changes.
    """
    page_url = lambda p: f"{BASE_URL}/kategorien?___store=wl_de&p={p}"
    htmls: List[str] = []
    async with AsyncSession(impersonate="safari17_2_ios", curl_options=shop_curl_options()) as s:
        first = await s.get(page_url(1))
        if first.status_code != 200:
            raise RuntimeError(f"listing page 1 returned {first.status_code}")
        htmls.append(first.text)
        last_page = max(
            (int(n) for n in re.findall(r'[?&;]p=(\d{1,2})"', first.text)),
            default=1,
        )
        if last_page > 1:
            rest = await asyncio.gather(
                *(s.get(page_url(p)) for p in range(2, min(last_page, 9) + 1)),
                return_exceptions=True,
            )
            # All-or-nothing: a partial listing makes products on the missing
            # page look "new" next scan (or never seeded), which auto-carts old
            # events. Fail the whole scrape so the detector skips this round.
            for p, r in enumerate(rest, start=2):
                if isinstance(r, Exception):
                    raise RuntimeError(f"listing page {p} failed: {r}")
                if r.status_code != 200:
                    raise RuntimeError(f"listing page {p} returned {r.status_code}")
                htmls.append(r.text)

    # Non-product paths that live at the site root alongside product slugs.
    NAV = (
        "checkout", "kategorien", "catalogsearch", "customer", "wishlist",
        "sales", "review", "contacts", "accessibility", "sitemap",
        "locationsitemap", "city", "media", "skin", "js", "catalog",
    )

    def is_product(u: str) -> bool:
        if not u.startswith(BASE_URL):
            return False
        tail = u[len(BASE_URL):].split("?", 1)[0].split("#", 1)[0].strip("/")
        # Product slugs are a single root-level segment with no extension
        # (categories/cities use .html; nav uses the prefixes above).
        if not tail or "/" in tail or "." in tail:
            return False
        return not tail.startswith(NAV)

    # GTM productClick block: {... 'id': '346010', ...} ... window.location='<url>'
    pair_re = re.compile(
        r"'id':\s*'(\d+)'.{0,400}?window\.location\s*=\s*'(" + re.escape(BASE_URL) + r"/[^']+)'",
        re.S,
    )
    products: Dict[str, Optional[int]] = {}
    for html in htmls:
        for pid, m in pair_re.findall(html):
            if is_product(m):
                products[_normalize(m)] = int(pid)
        # Union with every product anchor — catches tiles whose dataLayer shape
        # differs (they get id None, so the detector never auto-carts them).
        for link in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            if is_product(link["href"]):
                products.setdefault(_normalize(link["href"]), None)
    return products

WIDGET_PATH = "/bookingwidget/vendor/30797/id/{}"
# The widget route is served by the booking service, which is reachable on
# regiondo.net (AWS, no Cloudflare) as well as on the shop host (Cloudflare).
# regiondo.net is primary: from the server IP the shop host gets 403 for hours
# at a time, regiondo.net never did. The shop host stays as fallback.
WIDGET_URLS = ("https://regiondo.net" + WIDGET_PATH, BASE_URL + WIDGET_PATH)
_WIDGET_TITLE = re.compile(r"<title>\s*(.*?)\s*bei Regiondo", re.S)
_WIDGET_BRAND = re.compile(r"'brand':\s*'([^']*)'")
# safari17_2_ios is the only impersonation target that reliably gets through
# Cloudflare (chrome* ~0-25%), and a long-lived session keeps __cf_bm + the
# connection. Extra headers (Accept-Language, Referer) break the fingerprint.
_widget_session: Optional[AsyncSession] = None


async def widget_lookup(pid: int) -> Optional[Tuple[str, str]]:
    """Resolve a global Regiondo product ID to (vendor, name) through the
    booking-widget route. Answers for every created product, published or not,
    so a new Audi game is identifiable as soon as Audi creates it.
    None = ID not created yet (404). Raises on any other failure so the caller
    never mistakes an error for the end of the ID range."""
    global _widget_session
    if _widget_session is None:
        _widget_session = AsyncSession(impersonate="safari17_2_ios", timeout=15)
    r = None
    for url in WIDGET_URLS:
        r = await _widget_session.get(url.format(pid))
        if r.status_code in (200, 404):
            break
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        if r.status_code == 403:  # challenged: start clean next time
            await _widget_session.close()
            _widget_session = None
        raise RuntimeError(f"widget id {pid} returned {r.status_code}")
    t, b = _WIDGET_TITLE.search(r.text), _WIDGET_BRAND.search(r.text)
    return (b.group(1) if b else "", t.group(1) if t else "")


WIDGET_PRODUCT = "https://regiondo.net/widgets/booking/product?locale=de_DE&provider=AU43&product={}"
CDN_MEDIA = "https://cdn.regiondo.net/media/catalog/product"


async def widget_product(pid) -> Optional[dict]:
    """Full shop record of a product by ID, hidden ones included (regiondo.net,
    no Cloudflare): `status` "2" hidden / "1" live, `updated_at` = Audi's last
    save, `ticket_id`, `name`, `description`. None = no such product. Raises
    on any other failure so an outage never reads as "not found"."""
    global _widget_session
    if _widget_session is None:
        _widget_session = AsyncSession(impersonate="safari17_2_ios", timeout=15)
    r = await _widget_session.get(WIDGET_PRODUCT.format(pid))
    if r.status_code != 200:
        raise RuntimeError(f"widget product {pid} returned {r.status_code}")
    data = r.json()
    return data if data.get("entity_id") else None


CATEGORIES_URL = ("https://regiondo.net/widgets/booking/product/ticketVariations"
                  "?locale=de_DE&provider=AU43&includeSoldOut=1&product={}")
TIMESLOTS_URL = PRODUCT_API.rsplit("/", 2)[0] + "/timeslots/times?productId={}&numberOfMonths=3&variationId={}"
# x-partner-domain must be exactly this, other values answer 500.
TIMESLOTS_HEADERS = {**PRODUCT_API_HEADERS, "x-partner-domain": "https://audidefuehrungen2.regiondo.de"}


async def option_ids(pid) -> Dict[str, str]:
    """{variation id: option id} for every category, hidden products included.
    Takes each category's first option, the same row the shop's options call
    lists first (core.get_option_number), i.e. the full-price ticket."""
    global _widget_session
    if _widget_session is None:
        _widget_session = AsyncSession(impersonate="safari17_2_ios", timeout=15)
    r = await _widget_session.get(CATEGORIES_URL.format(pid))
    if r.status_code != 200:
        raise RuntimeError(f"categories {pid} returned {r.status_code}")
    return {str(c["variation_id"]): str(c["options"][0]["option_id"])
            for c in r.json().get("variations") or [] if c.get("options")}


async def category_stock(pid) -> List[Dict[str, Any]]:
    """Tickets left per category, e.g. [{"title": "Block 237 - Kategorie 3",
    "available": 24, "capacity": 180}, ...], in the shop's category order.
    Category list from the widget route, stock per category from the product
    API's timeslots (both no Cloudflare). Raises on failure."""
    global _widget_session
    if _widget_session is None:
        _widget_session = AsyncSession(impersonate="safari17_2_ios", timeout=15)
    r = await _widget_session.get(CATEGORIES_URL.format(pid))
    if r.status_code != 200:
        raise RuntimeError(f"categories {pid} returned {r.status_code}")
    cats = r.json().get("variations") or []
    slots = await asyncio.gather(*(
        _widget_session.get(TIMESLOTS_URL.format(pid, c["variation_id"]), headers=TIMESLOTS_HEADERS)
        for c in cats))
    out = []
    for c, t in zip(cats, slots):
        if t.status_code != 200:
            raise RuntimeError(f"timeslots {pid}/{c['variation_id']} returned {t.status_code}")
        times = [x for day in (t.json().get("days") or {}).values() for x in day["times"].values()]
        out.append({"title": c.get("title") or c["variation_id"],
                    "available": sum(x.get("availableQuantity", 0) for x in times),
                    "capacity": sum(x.get("capacity", 0) for x in times)})
    return out


async def api_visible(pid) -> bool:
    """True once the product API serves the product, which it only does for
    public products (404 while hidden, including Audi's brief placeholder
    enables). Raises on anything but 200/404."""
    global _widget_session
    if _widget_session is None:
        _widget_session = AsyncSession(impersonate="safari17_2_ios", timeout=15)
    r = await _widget_session.get(PRODUCT_API.format(pid), headers=PRODUCT_API_HEADERS)
    if r.status_code not in (200, 404):
        raise RuntimeError(f"product API {pid} returned {r.status_code}")
    return r.status_code == 200


def product_view_url(pid: int) -> str:
    """Public product page by ID: 301 to /kategorien while hidden, 200 once live."""
    return f"{BASE_URL}/catalog/product/view/id/{pid}"


def _normalize(u: str) -> str:
    """Canonical product URL: drop query/fragment and trailing slash, so the
    same product never shows up twice under different suffixes."""
    return u.split("#", 1)[0].split("?", 1)[0].rstrip("/")


# For testing
if __name__ == "__main__":
    async def main():
        # Offline parser check on a real description shape.
        g = _parse_game({
            "id": "346054", "title": "FC BAYERN MÜNCHEN - 1. FC KÖLN (Ingolstadt)",
            "images": [{"url": "https://cdn.regiondo.net/x.jpg"}],
            "description": "<p>Freitag, 20.11.2026 | Anstoß: 20:30 Uhr</p>"
                           "<p>VERKAUFSSTART: MONTAG, 5. OKTOBER 2026</p>"
                           "<p>Kategorie 1 - Block 136: 80,00 Euro</p>",
        })
        assert (g.opponent, g.location) == ("1. FC KÖLN", "Ingolstadt"), g
        assert (g.match_date, g.match_time) == (date(2026, 11, 20), "20:30"), g
        assert g.sale_date == date(2026, 10, 5), g
        assert g.price_categories == [{"name": "Kategorie 1 - Block 136", "price": 80.0}], g
        assert g.url.endswith("/catalog/product/view/id/346054"), g
        # Widget record of a hidden product: "€" prices and the pickup window.
        facts = product_facts({
            "entity_id": "346058", "name": "FC BAYERN MÜNCHEN - SK SLAVIA PRAG (Ingolstadt)",
            "description": "<p>Dienstag, 08.12.2026 | Anstoß: 21:00 Uhr</p><p>Zeitraum der Abholung:<br />"
                           "<strong>Freitag, 04.12.2026 bis Dienstag, 08.12.2026</strong><br />jeweils von "
                           "<strong>08:00 Uhr bis 16:00 Uhr</strong></p><p>• Kategorie 3 - Block 237: 50,00&nbsp;€</p>",
        })
        assert facts == {"kickoff": "08.12.2026 21:00",
                         "pickup": "Freitag, 04.12.2026 bis Dienstag, 08.12.2026, 08:00 Uhr bis 16:00 Uhr",
                         "prices": "Kategorie 3 - Block 237: 50 €"}, facts

        games = await get_bayern_games()
        # Smoke check against the live shop: title parsing must yield a location,
        # otherwise the location filter silently drops every game (0 games in the UI).
        assert games, "no FC Bayern games found — check title/href parsing"
        assert all(g["location"] for g in games), "game without location — title regex broke"
        for g in games:
            print(f"{g['title']}")
            print(f"  Match: {g['match_date']} {g['match_time']}")
            print(f"  Sale: {g['sale_date']} {g['sale_time']}")
            print(f"  Status: {g['status']}")
            print()
    
    asyncio.run(main())
