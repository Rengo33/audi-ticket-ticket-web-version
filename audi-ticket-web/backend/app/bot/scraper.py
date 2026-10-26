"""
FC Bayern Munich game scraper for Audi ticket website.
Scrapes upcoming games and their sale dates.
"""
import asyncio
import re
import json
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

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


class BayernScraper:
    """Scraper for FC Bayern games on Audi ticket website."""
    
    BASE_URL = "https://audidefuehrungen2.regiondo.de"
    
    def __init__(self):
        self.session: Optional[AsyncSession] = None
    
    async def __aenter__(self):
        self.session = AsyncSession(impersonate="chrome120")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_all_games(self, location_filter: Optional[str] = "Ingolstadt") -> List[BayernGame]:
        """Scrape all FC Bayern games from the website.
        
        Args:
            location_filter: Only return games at this location (e.g., "Ingolstadt"). 
                           Set to None to return all locations.
        """
        games = []
        found: Dict[str, Optional[str]] = {}  # url -> title from the listing, if usable

        try:
            def collect(html: str):
                """Pull fc-bayern product links plus their listing title out of one page."""
                for link in BeautifulSoup(html, 'html.parser').find_all('a', href=True):
                    href = link['href']
                    if 'fc-bayern' in href.lower() and href not in found:
                        title = link.get_text(strip=True)
                        if not title or len(title) < 5 or 'fc bayern' not in title.lower():
                            title = None  # fall back to the title on the detail page
                        found[href] = title

            # Page 1 tells us how many pages there are, so the rest can be fetched
            # together instead of one-by-one with a sleep in between.
            page_url = lambda p: f"{self.BASE_URL}/kategorien?___store=wl_de&p={p}"
            first = await self.session.get(page_url(1))
            if first.status_code != 200:
                logger.warning(f"Page 1 returned {first.status_code}")
                return games
            collect(first.text)

            last_page = max(
                (int(n) for n in re.findall(r'[?&;]p=(\d{1,2})"', first.text)),
                default=1,
            )
            if last_page > 1:
                rest = await asyncio.gather(
                    *(self.session.get(page_url(p)) for p in range(2, min(last_page, 9) + 1)),
                    return_exceptions=True,
                )
                for p, response in enumerate(rest, start=2):
                    if isinstance(response, Exception):
                        logger.warning(f"Page {p} failed: {response}")
                        continue
                    if response.status_code != 200:
                        logger.warning(f"Page {p} returned {response.status_code}")
                        continue
                    collect(response.text)

            # One detail fetch per game, all in flight at once — 4 games turn
            # ~12s of sequential requests into roughly one round trip.
            results = await asyncio.gather(
                *(self._get_game_details(u, t) for u, t in found.items()),
                return_exceptions=True,
            )
            for game in results:
                if isinstance(game, Exception):
                    logger.error(f"Error getting game details: {game}")
                    continue
                if not game:
                    continue
                if location_filter and game.location.lower() != location_filter.lower():
                    continue
                games.append(game)

        except Exception as e:
            logger.error(f"Error scraping games: {e}")

        logger.info(f"Found {len(games)} FC Bayern games (location: {location_filter or 'all'})")
        return games
    
    async def _get_game_details(self, url: str, title: Optional[str] = None) -> Optional[BayernGame]:
        """Get detailed information about a specific game."""
        try:
            response = await self.session.get(url)
            
            if response.status_code != 200:
                return None
            
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # Generate ID from URL
            game_id = url.split('/')[-1]
            
            # Get title from page if not provided
            if not title:
                # Try h1 first
                h1 = soup.find('h1')
                if h1:
                    title = h1.get_text(strip=True)
                else:
                    # Try meta title
                    meta_title = soup.find('meta', property='og:title')
                    if meta_title:
                        title = meta_title.get('content', '')
                
                if not title:
                    title = game_id.replace('-', ' ').title()
            
            # Parse opponent and location from title
            # Format: "FC Bayern München - Opponent (Location)"
            opponent = ""
            location = ""
            
            # Case-insensitive: the shop switched the product titles to all caps
            # ("FC BAYERN MÜNCHEN - RB LEIPZIG (Ingolstadt)").
            match = re.search(r'FC Bayern München\s*-\s*(.+?)\s*\((\w+)\)', title, re.IGNORECASE)
            if match:
                opponent = match.group(1).strip()
                location = match.group(2).strip()
            else:
                opponent = title.replace("FC Bayern München", "").strip(" -")
            
            # Parse match date from schema.org JSON-LD
            match_date = None
            match_time = None
            
            schema_match = re.search(r'"startDate"\s*:\s*"([^"]+)"', html)
            if schema_match:
                try:
                    dt = datetime.fromisoformat(schema_match.group(1).replace('+00:00', ''))
                    match_date = dt.date()
                    match_time = dt.strftime("%H:%M")
                except:
                    pass
            
            # Parse sale date from VERKAUFSSTART
            sale_date = None
            # Take the first "1. Oktober 2026" after VERKAUFSSTART; the words in
            # between vary ("VERKAUFSSTART GEPLANT FÜR: DONNERSTAG, 01. OKTOBER 2026",
            # "VERKAUFSSTART: MONTAG, 5. MAI 2026").
            sale_match = re.search(r'VERKAUFSSTART[^<]{0,60}?(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\s+(\d{4})', html, re.IGNORECASE)
            if sale_match:
                day = int(sale_match.group(1))
                month_name = sale_match.group(2).lower()
                year = int(sale_match.group(3))
                
                # German month names
                months = {
                    'januar': 1, 'februar': 2, 'märz': 3, 'maerz': 3,
                    'april': 4, 'mai': 5, 'juni': 6, 'juli': 7,
                    'august': 8, 'september': 9, 'oktober': 10,
                    'november': 11, 'dezember': 12
                }
                
                month = months.get(month_name, 1)
                sale_date = date(year, month, day)
            
            # Extract main product image (team matchup image)
            image_url = None
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if 'catalog/product' in src and '600x400' in src:
                    image_url = src
                    break
            
            # Determine status
            status = "upcoming"
            is_available = False
            today = date.today()
            page_says_sold_out = 'ausverkauft' in html.lower() or 'sold out' in html.lower()

            # Check if sale has actually started (7:00 AM German time)
            from datetime import datetime as dt
            from zoneinfo import ZoneInfo
            now_german = dt.now(ZoneInfo("Europe/Berlin"))
            sale_started = False
            if sale_date:
                sale_datetime = dt(sale_date.year, sale_date.month, sale_date.day, 7, 0, tzinfo=ZoneInfo("Europe/Berlin"))
                sale_started = now_german >= sale_datetime

            if sale_date and sale_started and page_says_sold_out:
                status = "sold_out"
            elif not sale_date and page_says_sold_out:
                status = "sold_out"
            elif sale_date and sale_started:
                is_available = await self._check_availability(soup)
                status = "on_sale"

            # Extract price categories (e.g. "Kategorie 1 - Block 136: 80,00 Euro")
            price_categories = []
            seen = set()
            for cat_match in re.finditer(r'(Kategorie\s+\d+\s*-\s*Block\s+\d+):\s*([\d,.]+)\s*Euro', html):
                name = cat_match.group(1).strip()
                if name not in seen:
                    seen.add(name)
                    price_categories.append({
                        "name": name,
                        "price": float(cat_match.group(2).replace(',', '.'))
                    })

            return BayernGame(
                id=game_id,
                title=title,
                opponent=opponent,
                location=location,
                url=url,
                image_url=image_url,
                match_date=match_date,
                match_time=match_time,
                sale_date=sale_date,
                is_available=is_available,
                status=status,
                price_categories=price_categories or None
            )
            
        except Exception as e:
            logger.error(f"Error getting game details for {url}: {e}")
            return None
    
    async def _check_availability(self, soup: BeautifulSoup) -> bool:
        """Check if tickets are currently available for a game.

        Takes the already-parsed product page — refetching it here cost a second
        100 KB download per on-sale game.
        """
        try:
            form = soup.find('form')
            if form and form.get('action'):
                event_id = form['action'].split('/')[-1]
                
                sku_tag = soup.find('meta', {'itemprop': 'sku'})
                if sku_tag and sku_tag.get('content'):
                    ticket_id = sku_tag['content'].split('-')[-1]
                    
                    # Check availability
                    avail_url = (
                        f"{self.BASE_URL}/product/catalog_ajax/dates/id/{event_id}/"
                        f"?___store=wl_de&ticket_id={ticket_id}&availabilityType=starttime"
                    )
                    
                    avail_response = await self.session.get(avail_url)
                    if avail_response.status_code == 200:
                        pattern = r"ticket\.setAvailableDateTimes\((\{.*?\})\);"
                        match = re.search(pattern, avail_response.text, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            # Check if any tickets available
                            for tickets in data.values():
                                for t in tickets:
                                    if t.get('qty_available', 0) > 0:
                                        return True
        except Exception as e:
            logger.debug(f"Availability check error: {e}")
        
        return False


async def get_bayern_games() -> List[Dict[str, Any]]:
    """Get all FC Bayern games as a list of dicts."""
    async with BayernScraper() as scraper:
        games = await scraper.get_all_games()
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
    async with AsyncSession(impersonate="chrome120") as s:
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

WIDGET_URL = BASE_URL + "/bookingwidget/vendor/30797/id/{}"
_WIDGET_TITLE = re.compile(r"<title>\s*(.*?)\s*bei Regiondo", re.S)
_WIDGET_BRAND = re.compile(r"'brand':\s*'([^']*)'")
# Cloudflare challenges this route from the server IP. safari17_2_ios is the
# only impersonation target that reliably gets through (chrome* ~0-25%), and a
# long-lived session keeps __cf_bm + the connection, cutting 403s further.
# Extra headers (Accept-Language, Referer) break the fingerprint — don't add any.
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
    r = await _widget_session.get(WIDGET_URL.format(pid))
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        if r.status_code == 403:  # challenged: start clean next time
            await _widget_session.close()
            _widget_session = None
        raise RuntimeError(f"widget id {pid} returned {r.status_code}")
    t, b = _WIDGET_TITLE.search(r.text), _WIDGET_BRAND.search(r.text)
    return (b.group(1) if b else "", t.group(1) if t else "")


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
