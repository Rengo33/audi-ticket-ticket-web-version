"""
FC Bayern Munich game scraper for Audi ticket website.
Scrapes upcoming games and their sale dates.
"""
import asyncio
import re
import json
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
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
        seen_urls = set()
        
        try:
            # Scrape multiple pages
            for page in range(1, 10):
                url = f"{self.BASE_URL}/kategorien?___store=wl_de&p={page}"
                response = await self.session.get(url)
                
                if response.status_code != 200:
                    logger.warning(f"Page {page} returned {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all product links containing fc-bayern in URL
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'fc-bayern' in href.lower() and href not in seen_urls:
                        seen_urls.add(href)
                        
                        # Try to get title from link text, or fetch from page
                        title = link.get_text(strip=True)
                        if not title or len(title) < 5 or 'fc bayern' not in title.lower():
                            # Fetch the page to get proper title
                            game = await self._get_game_details(href, None)
                        else:
                            game = await self._get_game_details(href, title)
                        
                        if game:
                            # Filter by location if specified
                            if location_filter and game.location.lower() != location_filter.lower():
                                continue
                            games.append(game)
                
                # Check if there's a next page
                if 'p=' + str(page + 1) not in response.text:
                    break
                    
                await asyncio.sleep(0.5)  # Rate limiting
                
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
            
            match = re.search(r'FC Bayern München\s*-\s*(.+?)\s*\((\w+)\)', title)
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
            sale_match = re.search(r'VERKAUFSSTART[:\s]*(\w+),?\s*(\d{1,2})\.?\s*(\w+)\s*(\d{4})', html, re.IGNORECASE)
            if sale_match:
                day = int(sale_match.group(2))
                month_name = sale_match.group(3).lower()
                year = int(sale_match.group(4))
                
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
            
            if sale_date and sale_date <= today:
                # Check if tickets are available
                if 'ausverkauft' in html.lower() or 'sold out' in html.lower():
                    status = "sold_out"
                else:
                    # Check availability endpoint
                    is_available = await self._check_availability(url)
                    status = "on_sale"
            
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
                status=status
            )
            
        except Exception as e:
            logger.error(f"Error getting game details for {url}: {e}")
            return None
    
    async def _check_availability(self, product_url: str) -> bool:
        """Check if tickets are currently available for a game."""
        try:
            # Extract event ID from page
            response = await self.session.get(product_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
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


# For testing
if __name__ == "__main__":
    async def main():
        games = await get_bayern_games()
        for g in games:
            print(f"{g['title']}")
            print(f"  Match: {g['match_date']} {g['match_time']}")
            print(f"  Sale: {g['sale_date']} {g['sale_time']}")
            print(f"  Status: {g['status']}")
            print()
    
    asyncio.run(main())
