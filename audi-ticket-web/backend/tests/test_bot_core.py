"""
Tests for the AudiTicketBot core module.
Mocks the Audi ticket API responses to test parsing and logic.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.bot.core import AudiTicketBot, CookieData, TicketInfo


# Sample HTML responses from Audi ticket pages
PRODUCT_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta itemprop="sku" content="tour-factory-12345">
</head>
<body>
    <form action="/checkout/cart/add/product/67890">
        <button type="submit">Buy</button>
    </form>
</body>
</html>
"""

PRODUCT_PAGE_HTML_NO_FORM = """
<!DOCTYPE html>
<html>
<head>
    <meta itemprop="sku" content="tour-factory-12345">
</head>
<body>
    <p>No form available</p>
</body>
</html>
"""

AVAILABILITY_RESPONSE = """
<script>
ticket.setAvailableDateTimes({"2024-03-15": [{"time": "10:00:00", "qty_available": 4, "traffic_light": 1, "variations": ["var-123"]}], "2024-03-16": [{"time": "14:00:00", "qty_available": 2, "traffic_light": 2, "variations": ["var-456"]}]});
</script>
"""

AVAILABILITY_RESPONSE_EMPTY = """
<script>
ticket.setAvailableDateTimes({});
</script>
"""

AVAILABILITY_RESPONSE_NO_TICKETS = """
<script>
ticket.setAvailableDateTimes({"2024-03-15": [{"time": "10:00:00", "qty_available": 0, "traffic_light": 3, "variations": ["var-123"]}]});
</script>
"""

OPTIONS_PAGE_HTML = """
<html>
<body>
    <table>
        <tr class="table-row" id="option-row-99887">
            <td>Option 1</td>
        </tr>
    </table>
</body>
</html>
"""

CART_SUCCESS_RESPONSE = {
    "success": True,
    "qtm_quote_item_ids": "12345",
    "qtm_quote_item_qtys": "2",
    "checkout_url": "https://audidefuehrungen2.regiondo.de/checkout/cart"
}

CART_FAILURE_RESPONSE = {
    "success": False,
    "messages": [{"text": "Tickets are no longer available"}]
}

CHECKOUT_PAGE_VALID = """
<html>
<body>
    <h1>Zusammenfassung</h1>
    <p>Zwischensumme: 50€</p>
    <p>Gesamtsumme: 50€</p>
    <button>Weiter zur Kasse</button>
</body>
</html>
"""

CHECKOUT_PAGE_EMPTY = """
<html>
<body>
    <p>Ihr Warenkorb ist leer</p>
</body>
</html>
"""

CHECKOUT_PAGE_UNAVAILABLE = """
<html>
<body>
    <p>Diese Tickets sind leider nicht mehr verfügbar</p>
</body>
</html>
"""


class TestExtractEventDetails:
    """Tests for extract_event_details method."""

    @pytest.mark.asyncio
    async def test_extract_event_details_success(self):
        """Test successful extraction of event and ticket IDs."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = PRODUCT_PAGE_HTML

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                event_id, ticket_id = await bot.extract_event_details(
                    "https://audidefuehrungen2.regiondo.de/test-product"
                )

                assert event_id == "67890"
                assert ticket_id == "12345"

    @pytest.mark.asyncio
    async def test_extract_event_details_no_form(self):
        """Test extraction when form is missing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = PRODUCT_PAGE_HTML_NO_FORM

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                event_id, ticket_id = await bot.extract_event_details(
                    "https://audidefuehrungen2.regiondo.de/test-product"
                )

                assert event_id is None
                assert ticket_id == "12345"

    @pytest.mark.asyncio
    async def test_extract_event_details_http_error(self):
        """Test extraction returns None on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                event_id, ticket_id = await bot.extract_event_details(
                    "https://audidefuehrungen2.regiondo.de/test-product"
                )

                assert event_id is None
                assert ticket_id is None

    @pytest.mark.asyncio
    async def test_extract_event_details_exception(self):
        """Test extraction handles exceptions gracefully."""
        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(side_effect=Exception("Network error"))

                event_id, ticket_id = await bot.extract_event_details(
                    "https://audidefuehrungen2.regiondo.de/test-product"
                )

                assert event_id is None
                assert ticket_id is None


class TestGetAvailableTickets:
    """Tests for get_available_tickets method."""

    @pytest.mark.asyncio
    async def test_get_available_tickets_success(self):
        """Test successful ticket availability fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = AVAILABILITY_RESPONSE

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                data = await bot.get_available_tickets("67890", "12345")

                assert data is not None
                assert "2024-03-15" in data
                assert "2024-03-16" in data
                assert data["2024-03-15"][0]["qty_available"] == 4
                assert data["2024-03-16"][0]["qty_available"] == 2

    @pytest.mark.asyncio
    async def test_get_available_tickets_empty(self):
        """Test when no tickets are available."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = AVAILABILITY_RESPONSE_EMPTY

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                data = await bot.get_available_tickets("67890", "12345")

                assert data is not None
                assert data == {}

    @pytest.mark.asyncio
    async def test_get_available_tickets_zero_quantity(self):
        """Test when tickets show qty_available of 0."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = AVAILABILITY_RESPONSE_NO_TICKETS

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                data = await bot.get_available_tickets("67890", "12345")

                assert data is not None
                assert data["2024-03-15"][0]["qty_available"] == 0

    @pytest.mark.asyncio
    async def test_get_available_tickets_http_error(self):
        """Test returns None on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                data = await bot.get_available_tickets("67890", "12345")

                assert data is None


class TestGetOptionNumber:
    """Tests for get_option_number method."""

    @pytest.mark.asyncio
    async def test_get_option_number_success(self):
        """Test successful option number extraction."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = OPTIONS_PAGE_HTML

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                option = await bot.get_option_number(
                    "67890", "var-123", "2024-03-15", "10%3A00%3A00"
                )

                assert option == "99887"

    @pytest.mark.asyncio
    async def test_get_option_number_not_found(self):
        """Test returns None when option not found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>No options</body></html>"

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                option = await bot.get_option_number(
                    "67890", "var-123", "2024-03-15", "10%3A00%3A00"
                )

                assert option is None


class TestAddToCart:
    """Tests for add_to_cart method."""

    @pytest.mark.asyncio
    async def test_add_to_cart_success(self):
        """Test successful add to cart."""
        mock_atc_response = MagicMock()
        mock_atc_response.status_code = 200
        mock_atc_response.json.return_value = CART_SUCCESS_RESPONSE
        mock_atc_response.text = '{"success": true}'

        mock_checkout_response = MagicMock()
        mock_checkout_response.status_code = 200
        mock_checkout_response.text = CHECKOUT_PAGE_VALID

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.post = AsyncMock(return_value=mock_atc_response)
                bot.session.get = AsyncMock(return_value=mock_checkout_response)
                bot.session.cookies = {"frontend": "session-cookie-value"}

                success, cookie, error = await bot.add_to_cart(
                    event_id="67890",
                    date="2024-03-15",
                    time_short="10:00",
                    ticket_variation="var-123",
                    option_number="99887",
                    quantity=2,
                    product_url="https://audidefuehrungen2.regiondo.de/test"
                )

                assert success is True
                assert cookie is not None
                assert cookie.name == "frontend"
                assert cookie.value == "session-cookie-value"
                assert error is None

    @pytest.mark.asyncio
    async def test_add_to_cart_api_failure(self):
        """Test add to cart when API returns failure."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = CART_FAILURE_RESPONSE
        mock_response.text = '{"success": false}'

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.post = AsyncMock(return_value=mock_response)

                success, cookie, error = await bot.add_to_cart(
                    event_id="67890",
                    date="2024-03-15",
                    time_short="10:00",
                    ticket_variation="var-123",
                    option_number="99887",
                    quantity=2,
                    product_url="https://audidefuehrungen2.regiondo.de/test"
                )

                assert success is False
                assert cookie is None
                assert error == "Tickets are no longer available"

    @pytest.mark.asyncio
    async def test_add_to_cart_phantom_cart(self):
        """Test detection of phantom cart (ATC success but checkout invalid)."""
        mock_atc_response = MagicMock()
        mock_atc_response.status_code = 200
        mock_atc_response.json.return_value = CART_SUCCESS_RESPONSE
        mock_atc_response.text = '{"success": true}'

        mock_checkout_response = MagicMock()
        mock_checkout_response.status_code = 200
        mock_checkout_response.text = CHECKOUT_PAGE_UNAVAILABLE

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.post = AsyncMock(return_value=mock_atc_response)
                bot.session.get = AsyncMock(return_value=mock_checkout_response)

                success, cookie, error = await bot.add_to_cart(
                    event_id="67890",
                    date="2024-03-15",
                    time_short="10:00",
                    ticket_variation="var-123",
                    option_number="99887",
                    quantity=2,
                    product_url="https://audidefuehrungen2.regiondo.de/test"
                )

                assert success is False
                assert cookie is None
                assert "phantom cart" in error.lower() or "not valid" in error.lower()

    @pytest.mark.asyncio
    async def test_add_to_cart_http_error(self):
        """Test add to cart with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.post = AsyncMock(return_value=mock_response)

                success, cookie, error = await bot.add_to_cart(
                    event_id="67890",
                    date="2024-03-15",
                    time_short="10:00",
                    ticket_variation="var-123",
                    option_number="99887",
                    quantity=2,
                    product_url="https://audidefuehrungen2.regiondo.de/test"
                )

                assert success is False
                assert cookie is None
                assert "500" in error


class TestVerifyCartAtCheckout:
    """Tests for _verify_cart_at_checkout method."""

    @pytest.mark.asyncio
    async def test_verify_cart_valid(self):
        """Test verification of valid cart."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = CHECKOUT_PAGE_VALID

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                is_valid = await bot._verify_cart_at_checkout(
                    "https://audidefuehrungen2.regiondo.de/checkout/cart"
                )

                assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_cart_empty(self):
        """Test verification detects empty cart."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = CHECKOUT_PAGE_EMPTY

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                is_valid = await bot._verify_cart_at_checkout(
                    "https://audidefuehrungen2.regiondo.de/checkout/cart"
                )

                assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_cart_unavailable(self):
        """Test verification detects unavailable tickets."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = CHECKOUT_PAGE_UNAVAILABLE

        with patch.object(AudiTicketBot, 'start_session', new_callable=AsyncMock):
            with patch.object(AudiTicketBot, 'close_session', new_callable=AsyncMock):
                bot = AudiTicketBot()
                bot.session = MagicMock()
                bot.session.get = AsyncMock(return_value=mock_response)

                is_valid = await bot._verify_cart_at_checkout(
                    "https://audidefuehrungen2.regiondo.de/checkout/cart"
                )

                assert is_valid is False


class TestParseAvailabilityData:
    """Tests for parse_availability_data method."""

    def test_parse_availability_data_success(self):
        """Test parsing availability data into TicketInfo objects."""
        bot = AudiTicketBot()
        data = {
            "2024-03-15": [
                {"time": "10:00:00", "qty_available": 4, "traffic_light": 1, "variations": ["var-123"]}
            ],
            "2024-03-16": [
                {"time": "14:00:00", "qty_available": 2, "traffic_light": 2, "variations": ["var-456"]}
            ]
        }

        tickets = bot.parse_availability_data(data)

        assert len(tickets) == 2
        assert all(isinstance(t, TicketInfo) for t in tickets)

        # Find ticket for 2024-03-15
        ticket_15 = next(t for t in tickets if t.date == "2024-03-15")
        assert ticket_15.time == "10:00:00"
        assert ticket_15.qty_available == 4
        assert ticket_15.traffic_light == 1
        assert ticket_15.variations == ["var-123"]

    def test_parse_availability_data_empty(self):
        """Test parsing empty availability data."""
        bot = AudiTicketBot()
        data = {}

        tickets = bot.parse_availability_data(data)

        assert tickets == []

    def test_parse_availability_data_multiple_times(self):
        """Test parsing data with multiple times per date."""
        bot = AudiTicketBot()
        data = {
            "2024-03-15": [
                {"time": "10:00:00", "qty_available": 4, "traffic_light": 1, "variations": ["var-1"]},
                {"time": "14:00:00", "qty_available": 2, "traffic_light": 2, "variations": ["var-2"]},
                {"time": "18:00:00", "qty_available": 0, "traffic_light": 3, "variations": ["var-3"]}
            ]
        }

        tickets = bot.parse_availability_data(data)

        assert len(tickets) == 3
        times = [t.time for t in tickets]
        assert "10:00:00" in times
        assert "14:00:00" in times
        assert "18:00:00" in times


class TestExtractSessionCookie:
    """Tests for _extract_session_cookie method."""

    def test_extract_frontend_cookie(self):
        """Test extraction of frontend cookie."""
        bot = AudiTicketBot()
        bot.session = MagicMock()
        bot.session.cookies = {"frontend": "abc123", "other": "xyz"}

        cookie = bot._extract_session_cookie()

        assert cookie is not None
        assert cookie.name == "frontend"
        assert cookie.value == "abc123"
        assert cookie.domain == "audidefuehrungen2.regiondo.de"

    def test_extract_fallback_cookie(self):
        """Test extraction falls back to first cookie if no frontend."""
        bot = AudiTicketBot()
        bot.session = MagicMock()
        bot.session.cookies = {"session_id": "xyz789"}

        cookie = bot._extract_session_cookie()

        assert cookie is not None
        assert cookie.name == "session_id"
        assert cookie.value == "xyz789"

    def test_extract_no_cookies(self):
        """Test returns None when no cookies."""
        bot = AudiTicketBot()
        bot.session = MagicMock()
        bot.session.cookies = {}

        cookie = bot._extract_session_cookie()

        assert cookie is None

    def test_extract_no_session(self):
        """Test returns None when no session."""
        bot = AudiTicketBot()
        bot.session = None

        cookie = bot._extract_session_cookie()

        assert cookie is None


class TestCookieData:
    """Tests for CookieData dataclass."""

    def test_cookie_data_creation(self):
        """Test CookieData creation."""
        cookie = CookieData(
            name="frontend",
            value="test-value",
            domain="example.com"
        )

        assert cookie.name == "frontend"
        assert cookie.value == "test-value"
        assert cookie.domain == "example.com"


class TestTicketInfo:
    """Tests for TicketInfo dataclass."""

    def test_ticket_info_creation(self):
        """Test TicketInfo creation."""
        ticket = TicketInfo(
            date="2024-03-15",
            time="10:00:00",
            qty_available=4,
            traffic_light=1,
            variations=["var-123", "var-456"]
        )

        assert ticket.date == "2024-03-15"
        assert ticket.time == "10:00:00"
        assert ticket.qty_available == 4
        assert ticket.traffic_light == 1
        assert ticket.variations == ["var-123", "var-456"]
