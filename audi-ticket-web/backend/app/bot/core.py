"""
Core bot functionality - async version of the original bot.
Uses curl_cffi for TLS fingerprinting with async support.
"""
import asyncio
import json
import re
import logging
from typing import Optional, Tuple, Dict, Any, Callable
from datetime import datetime
from urllib.parse import quote
from dataclasses import dataclass

from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class CookieData:
    """Cookie data structure."""
    name: str
    value: str
    domain: str


@dataclass
class TicketInfo:
    """Available ticket information."""
    date: str
    time: str
    qty_available: int
    traffic_light: int
    variations: list


class AudiTicketBot:
    """
    Async Audi Ticket Bot.
    Handles ticket monitoring and carting with TLS fingerprint spoofing.
    """
    
    BASE_URL = "https://audidefuehrungen2.regiondo.de"
    
    def __init__(self):
        self.session: Optional[AsyncSession] = None
    
    async def __aenter__(self):
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()
    
    async def start_session(self):
        """Initialize async session with Chrome TLS fingerprint."""
        self.session = AsyncSession(impersonate="chrome120")
    
    async def close_session(self):
        """Close the session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def extract_event_details(self, product_url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract Event ID and Ticket ID from product page.
        
        Returns:
            Tuple of (event_id, ticket_id) or (None, None) on error
        """
        try:
            logger.info(f"Extracting event details from: {product_url}")
            logger.info(f"Session object: {self.session}")
            
            response = await self.session.get(product_url)
            
            logger.info(f"Response status: {response.status_code}, length: {len(response.text)}")
            
            if response.status_code != 200:
                logger.error(f"Status {response.status_code} fetching product page")
                return None, None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract event ID from form action
            form = soup.find('form')
            event_id = None
            if form and form.get('action'):
                event_id = form['action'].split('/')[-1]
            
            # Extract ticket ID from meta tag
            ticket_id = None
            sku_tag = soup.find('meta', {'itemprop': 'sku'})
            if sku_tag and sku_tag.get('content'):
                ticket_id = sku_tag['content'].split('-')[-1]
            
            logger.info(f"Extracted: event_id={event_id}, ticket_id={ticket_id}")
            
            return event_id, ticket_id
            
        except Exception as e:
            logger.error(f"Error extracting event details: {e}")
            return None, None
    
    async def get_available_tickets(
        self, 
        event_id: str, 
        ticket_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check AJAX endpoint for ticket availability.
        
        Returns:
            Dict with availability data or None on error
        """
        url = (
            f"{self.BASE_URL}/product/catalog_ajax/dates/id/{event_id}/"
            f"?___store=wl_de&ticket_id={ticket_id}&availabilityType=starttime"
        )
        
        try:
            response = await self.session.get(url)
            
            logger.debug(f"[Availability] URL: {url}")
            logger.debug(f"[Availability] Status: {response.status_code}")
            
            if response.status_code == 200:
                # Log raw response (truncated for readability)
                raw_text = response.text[:500] if len(response.text) > 500 else response.text
                logger.debug(f"[Availability] Response: {raw_text}")
                
                # Parse JavaScript response
                pattern = r"ticket\.setAvailableDateTimes\((\{.*?\})\);"
                match = re.search(pattern, response.text, re.DOTALL)
                
                if match:
                    data = json.loads(match.group(1))
                    logger.debug(f"[Availability] Parsed data: {json.dumps(data, indent=2)[:300]}")
                    return data
                else:
                    logger.warning(f"[Availability] Could not parse response - pattern not found")
            else:
                logger.warning(f"[Availability] Non-200 status: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"[Availability] Error: {e}")
        
        return None
    
    async def get_option_number(
        self,
        event_id: str,
        ticket_variation: str,
        date: str,
        time_encoded: str
    ) -> Optional[str]:
        """Get the option ID for a specific ticket."""
        url = (
            f"{self.BASE_URL}/product/catalog_ajax/options/id/{event_id}/"
            f"?___store=wl_de&variation_id={ticket_variation}&date={date}&time={time_encoded}"
        )
        
        try:
            response = await self.session.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            row = soup.find('tr', class_='table-row')
            if row and row.has_attr('id'):
                return row['id'].split('-')[-1]
                
        except Exception as e:
            logger.debug(f"Error getting option number: {e}")
        
        return None
    
    async def add_to_cart(
        self,
        event_id: str,
        date: str,
        time_short: str,
        ticket_variation: str,
        option_number: str,
        quantity: int,
        product_url: str
    ) -> Tuple[bool, Optional[CookieData], Optional[str]]:
        """
        Add ticket to cart.
        
        Returns:
            Tuple of (success, cookie_data, error_message)
        """
        checkout_url = f"{self.BASE_URL}/checkout/ajaxcart/ajaxadd/product/{event_id}"
        
        payload = {
            'product': event_id,
            'related_product': '',
            'ticket_date': date,
            'ticket_time': time_short,
            'ticket_variation': ticket_variation,
            f'ticket_option_qty[{option_number}]': str(quantity),
        }
        
        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": self.BASE_URL,
            "referer": product_url,
            "x-requested-with": "XMLHttpRequest",
        }
        
        try:
            response = await self.session.post(
                checkout_url,
                headers=headers,
                data=payload
            )
            
            # Log the full response for debugging
            logger.info(f"[ATC] URL: {checkout_url}")
            logger.info(f"[ATC] Payload: {payload}")
            logger.info(f"[ATC] Status: {response.status_code}")
            logger.info(f"[ATC] Raw Response: {response.text[:1000]}")
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    logger.info(f"[ATC] JSON Response: {response_data}")
                except Exception as json_err:
                    logger.warning(f"[ATC] Failed to parse JSON: {json_err}")
                    response_data = {}
                
                if response_data.get('success') is True:
                    # Check if we got a quote item ID (indicates item was actually added)
                    quote_item_ids = response_data.get('qtm_quote_item_ids', '')
                    quote_item_qtys = response_data.get('qtm_quote_item_qtys', 0)
                    checkout_url = response_data.get('checkout_url', '')
                    
                    logger.info(f"[ATC] Quote Item IDs: {quote_item_ids}, Qty: {quote_item_qtys}")
                    
                    # If we have a quote item ID and quantity, verify by visiting checkout
                    if quote_item_ids and quote_item_qtys and int(quote_item_qtys) > 0:
                        # Verify cart is valid by checking the checkout page (same session!)
                        cart_valid = await self._verify_cart_at_checkout(checkout_url)
                        
                        if cart_valid:
                            logger.info(f"[ATC] SUCCESS! Cart verified at checkout with {quote_item_qtys} items")
                            cookie = self._extract_session_cookie()
                            return True, cookie, None
                        else:
                            logger.warning(f"[ATC] Cart verification failed - phantom cart detected!")
                            return False, None, "Cart not valid at checkout (phantom cart)"
                    else:
                        # No quote item ID means nothing was added
                        logger.warning(f"[ATC] No quote item ID/qty returned - cart may be invalid!")
                        return False, None, "No items added to cart (out of stock?)"
                else:
                    # Extract error message
                    error_msg = "Unknown error"
                    if 'messages' in response_data and response_data['messages']:
                        error_msg = response_data['messages'][0].get('text', 'Unknown')
                    elif 'error' in response_data:
                        error_msg = response_data['error']
                    
                    logger.warning(f"[ATC] Failed with error: {error_msg}")
                    
                    return False, None, error_msg
            else:
                return False, None, f"HTTP {response.status_code}"
                
        except Exception as e:
            logger.error(f"ATC exception: {e}")
            return False, None, str(e)
    
    def _extract_session_cookie(self) -> Optional[CookieData]:
        """Extract the session cookie from the session."""
        if not self.session:
            return None
        
        cookies = self.session.cookies
        
        # Look for 'frontend' cookie first
        for name, value in cookies.items():
            if 'frontend' in name:
                return CookieData(
                    name=name,
                    value=value,
                    domain="audidefuehrungen2.regiondo.de"
                )
        
        # Fallback to first cookie
        if cookies:
            name = next(iter(cookies.keys()))
            return CookieData(
                name=name,
                value=cookies[name],
                domain="audidefuehrungen2.regiondo.de"
            )
        
        return None
    
    async def _verify_cart_at_checkout(self, checkout_url: str) -> bool:
        """
        Verify cart is valid by visiting the checkout URL (uses same session!).
        This detects phantom carts where ATC returned success but tickets are unavailable.
        
        Returns:
            True if cart is valid, False if invalid/phantom
        """
        if not checkout_url:
            checkout_url = f"{self.BASE_URL}/checkout/cart"
        
        try:
            logger.info(f"[Cart Verify] Checking checkout URL: {checkout_url}")
            response = await self.session.get(checkout_url)
            
            if response.status_code == 200:
                html = response.text
                
                # Check for error messages that indicate invalid cart
                error_indicators = [
                    "nicht mehr verfügbar",  # "no longer available"
                    "Warenkorb ist leer",    # "cart is empty"
                    "leider nicht mehr",      # "unfortunately no longer"
                    "ausverkauft",            # "sold out"
                    "Bedauerlicherweise",     # "Unfortunately"
                ]
                
                for indicator in error_indicators:
                    if indicator in html:
                        logger.warning(f"[Cart Verify] Found error indicator: '{indicator}'")
                        return False
                
                # Check for positive indicators (items in cart)
                success_indicators = [
                    "Zusammenfassung",        # "Summary"
                    "Zwischensumme",          # "Subtotal"  
                    "Gesamtsumme",            # "Total"
                    "Weiter zur Kasse",       # "Continue to checkout"
                ]
                
                for indicator in success_indicators:
                    if indicator in html:
                        logger.info(f"[Cart Verify] Found success indicator: '{indicator}'")
                        return True
                
                # If no clear indicator, log HTML sample for debugging
                logger.warning(f"[Cart Verify] Unclear result, HTML sample: {html[:500]}")
                return False
                
            else:
                logger.warning(f"[Cart Verify] Non-200 status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"[Cart Verify] Exception: {e}")
            return False
    
    async def _verify_cart_contents(self) -> Tuple[bool, int]:
        """
        Verify that the cart actually contains items.
        
        Returns:
            Tuple of (is_valid, item_count)
        """
        cart_url = f"{self.BASE_URL}/checkout/cart/"
        
        try:
            response = await self.session.get(cart_url)
            
            if response.status_code == 200:
                html = response.text
                # Log first 2000 chars of cart HTML for debugging
                logger.info(f"[Cart Verify] Cart HTML (first 2000 chars): {html[:2000]}")
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for cart items - check for empty cart message
                empty_cart = soup.find('p', class_='empty')
                if empty_cart and 'leer' in empty_cart.get_text().lower():
                    logger.info("[Cart Verify] Cart is empty (found empty message)")
                    return False, 0
                
                # Also check for "Ihr Warenkorb ist leer" text
                if 'Ihr Warenkorb ist leer' in html:
                    logger.info("[Cart Verify] Cart is empty (found 'Warenkorb ist leer')")
                    return False, 0
                
                # Count cart items - try multiple selectors
                cart_items = soup.find_all('tr', class_='cart-item')
                logger.info(f"[Cart Verify] Selector 'tr.cart-item' found: {len(cart_items)}")
                
                if not cart_items:
                    cart_items = soup.find_all('tr', {'data-item-id': True})
                    logger.info(f"[Cart Verify] Selector 'tr[data-item-id]' found: {len(cart_items)}")
                
                if not cart_items:
                    # Try finding any table rows in the cart body
                    cart_table = soup.find('table', class_='cart-table')
                    if cart_table:
                        cart_items = cart_table.find_all('tr')
                        logger.info(f"[Cart Verify] Selector 'table.cart-table tr' found: {len(cart_items)}")
                
                # Try finding by item class
                if not cart_items:
                    cart_items = soup.find_all(class_='item')
                    logger.info(f"[Cart Verify] Selector '.item' found: {len(cart_items)}")
                
                item_count = len(cart_items)
                logger.info(f"[Cart Verify] Final item count: {item_count}")
                
                # Also check for quantity in the cart
                qty_inputs = soup.find_all('input', {'class': 'qty'})
                total_qty = 0
                for qty_input in qty_inputs:
                    try:
                        total_qty += int(qty_input.get('value', 0))
                    except:
                        pass
                
                # Also try type="number" inputs
                if total_qty == 0:
                    qty_inputs = soup.find_all('input', {'type': 'number'})
                    for qty_input in qty_inputs:
                        try:
                            total_qty += int(qty_input.get('value', 0))
                        except:
                            pass
                
                logger.info(f"[Cart Verify] Total quantity: {total_qty}")
                
                return item_count > 0 or total_qty > 0, total_qty
            else:
                logger.warning(f"[Cart Verify] Got status {response.status_code}")
                
        except Exception as e:
            logger.error(f"[Cart Verify] Error: {e}")
        
        return False, 0
    
    def parse_availability_data(self, data: Dict[str, Any]) -> list[TicketInfo]:
        """Parse availability data into TicketInfo objects."""
        tickets = []
        
        for date, entries in data.items():
            for entry in entries:
                tickets.append(TicketInfo(
                    date=date,
                    time=entry.get('time', ''),
                    qty_available=entry.get('qty_available', 0),
                    traffic_light=entry.get('traffic_light', 3),
                    variations=entry.get('variations', [])
                ))
        
        return tickets
