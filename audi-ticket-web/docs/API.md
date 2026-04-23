# Audi Ticket Bot — API & System Documentation

## Platform Overview

The Audi ticket shop (`audidefuehrungen2.regiondo.de`) runs on **Magento 1.x** with **Regiondo's** white-label booking overlay. No REST/GraphQL API is exposed — all communication uses Magento's controller-action URL pattern.

Payment is processed via **Stripe** (Cryozonic Stripe integration). The checkout uses a 3-step "CheckoutSimple" flow.

---

## Audi Website API Endpoints

### Product Availability

#### `GET /product/catalog_ajax/dates/id/{product_id}/`
**The core polling endpoint used by the bot.**

| Param | Description |
|-------|-------------|
| `___store` | Always `wl_de` |
| `ticket_id` | Product's ticket ID (from page JS) |
| `availabilityType` | Always `starttime` |

**Response:** JavaScript with multiple function calls:
```javascript
ticket.setAvailableDateTimes({
  "2026-04-19": [{
    "time": "17:30:00",
    "variations": [786750, 786751, 786752],  // Price category IDs
    "traffic_light": 1,                       // 1=green, 2=yellow, 3=red
    "qty_available": 20
  }]
});
ticket.setAvailabilityRange({"from": "2026-04-19", "to": "2026-04-19"});
ticket.setHasSigleDate(1);  // Single-event flag
```

**Traffic lights:** 1 = available, 2 = limited, 3 = sold out (qty_available = 0)

#### `GET /product/catalog_ajax/options/id/{product_id}/`
Returns ticket types (adult, child, reduced) for a specific variation.

| Param | Description |
|-------|-------------|
| `variation_id` | Variation ID from availability response |
| `date` | Date (YYYY-MM-DD) |
| `time` | Time (URL-encoded, e.g. `15%3A30%3A00`) |

**Response:** HTML table with option rows. Each row has `id="option-{option_number}"`.

#### `GET /product/catalog_ajax/variations/id/{product_id}/`
Returns variation data. Empty for single-variation products.

#### `GET /product/catalog_ajax/times/id/{product_id}/`
Returns time slots for a specific date. Mostly unused (times come from dates endpoint).

### Add to Cart

#### `POST /checkout/ajaxcart/ajaxadd/product/{product_id}`

| Header | Value |
|--------|-------|
| `Content-Type` | `application/x-www-form-urlencoded` |
| `X-Requested-With` | `XMLHttpRequest` |
| `Origin` | `https://audidefuehrungen2.regiondo.de` |

| Field | Description |
|-------|-------------|
| `product` | Product ID |
| `related_product` | Empty string |
| `ticket_date` | Date (YYYY-MM-DD) |
| `ticket_time` | Time (HH:MM) |
| `ticket_variation` | Variation ID |
| `ticket_option_qty[{option_number}]` | Quantity |

**Response:**
```json
{
  "success": true,
  "qtm_quote_item_ids": "66477344",
  "qtm_quote_item_qtys": 2,
  "checkout_url": "https://audidefuehrungen2.regiondo.de/checkoutsimple/onepage/index/step/address"
}
```

### Checkout

#### `POST /checkoutsimple/threestep/posteditaddress`
Submits billing + invoice details.

| Field | Description |
|-------|-------------|
| `type` | Always `first` |
| `skip_shipping_method` | Always `1` (digital tickets) |
| `firstname` | First name |
| `lastname` | Last name |
| `email` | Email |
| `email_confirm` | Email (must match) |
| `telephone` | Phone |
| `custom_field[buyer][buyer_field_5]` | Stammnummer (employee number) |
| `custom_field[buyer][buyer_field_19900]` | Department (optional) |
| `is_tax_invoice_required` | `on` for invoice |
| `tax_invoice_recipient_name` | Invoice recipient |
| `company` | Company (optional) |
| `company_tax_id` | Tax ID (optional) |
| `street[]` | Street address |
| `postcode` | Postal code |
| `city` | City |
| `country_id` | Country code (e.g. `DE`) |

**Response:**
```json
{
  "success": true,
  "step": "payment",
  "html": "<payment form HTML with Stripe client_secret>"
}
```

The `html` field contains `initStripe('pk_live_...', 2)` and the PaymentIntent client secret.

#### `POST /checkoutsimple/threestep/saveorder`
Places the final order after payment confirmation.

| Field | Description |
|-------|-------------|
| `payment[method]` | `cryozonic_stripeintent` |
| `payment[cc_owner]` | Cardholder name |
| `payment[cc_stripejs_token]` | `{pi_id}:{pm_id}` |
| `agreement_with_terms` | `on` |

### Product Pages

#### `GET /kategorien?___store=wl_de&p={page}`
Product catalog listing (24 per page, 2 pages).

#### `GET /catalogsearch/result/?q={query}`
Full-text product search.

---

## Variation → Price Category Mapping

For Bayern games, the availability API returns 3 variation IDs. The mapping (confirmed by testing):

| Index | Variation | Category | Bundesliga | Champions League |
|-------|-----------|----------|------------|-----------------|
| 0 | First ID | Kat 3 - Block 237 | 50€ | 120€ |
| 1 | Second ID | Kat 1 - Block 136 | 80€ | 200€ |
| 2 | Third ID | Kat 1 - Block 328 | 80€ | 200€ |

**Note:** The page text lists categories in a different order (Kat 1 first). The API variation order does NOT match the page display order.

---

## Bot Architecture

### Components

```
┌─────────────────────────────────────────────────┐
│                  Dashboard (Vue 3)              │
│  Tasks | Games | Carts | Billing | Logs         │
│  WebSocket ←──── Real-time updates              │
└──────────────────────┬──────────────────────────┘
                       │ HTTPS (audi-tickets.duckdns.org)
┌──────────────────────┴──────────────────────────┐
│                  Nginx (SSL termination)         │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────┐
│              FastAPI Backend                     │
│                                                  │
│  ┌─────────────────┐  ┌──────────────────┐      │
│  │ AvailabilityWatcher │ TaskManager      │      │
│  │ (shared polling)    │ (lifecycle)      │      │
│  └────────┬────────┘  └──────────────────┘      │
│           │                                      │
│  ┌────────┴────────┐  ┌──────────────────┐      │
│  │ AudiTicketBot   │  │ AutoCheckout     │      │
│  │ (ATC via curl)  │  │ (billing+payment)│      │
│  └─────────────────┘  └──────────────────┘      │
│                                                  │
│  ┌─────────────────┐  ┌──────────────────┐      │
│  │ TaskScheduler   │  │ Discord Webhook  │      │
│  │ (7 AM triggers) │  │ (notifications)  │      │
│  └─────────────────┘  └──────────────────┘      │
└──────────────────────────────────────────────────┘
```

### Monitoring Flow

```
1. User creates task (product URL, quantity, price category, billing profile)
   └── TaskManager.start_task() → _setup_task()

2. _setup_task extracts event_id + ticket_id from product page
   └── Finds or creates AvailabilityWatcher for this product

3. AvailabilityWatcher polls /catalog_ajax/dates/ every 1 second
   └── Multiple tasks on same URL share ONE watcher (no duplicate polling)

4. When qty_available > 0 detected:
   └── For each subscriber task:
       a. Get option_number (cached after first lookup)
       b. Fire N concurrent ATC threads
       c. Each thread: POST /ajaxcart/ajaxadd → verify cart → extract cookie

5. On ATC success:
   └── Store CartSession (cookie, token, expiry)
   └── If ACO enabled: trigger auto-checkout
   └── If not: notify via Discord + WebSocket
```

### Auto Checkout (ACO) Flow

```
1. submit_billing() — server-side via curl_cffi
   └── POST /posteditaddress with profile data
   └── Extract client_secret from response HTML

2. confirm_payment() — headless browser (Playwright)
   └── Open audidefuehrungen2.regiondo.de (HTTPS origin)
   └── Inject Stripe.js
   └── Call Stripe confirm API from browser context (valid hCaptcha)
   └── If 3DS: confirmCardPayment() handles the challenge
   └── User approves 3DS on phone (Revolut push notification)

3. place_order() — server-side via curl_cffi
   └── POST /saveorder with PI:PM token
   └── Order confirmed
```

### Key Technical Decisions

- **curl_cffi with Chrome 120 impersonation** — TLS fingerprint spoofing to bypass bot detection
- **Headless Playwright for Stripe** — Stripe blocks server-side card tokenization; browser context provides valid hCaptcha + fingerprints
- **Sequential checkout queue** — only one Chromium instance at a time (server memory constraint: 1GB)
- **15-second delay between checkouts** — prevents Stripe from flagging rapid same-card payments
- **Shared AvailabilityWatcher** — deduplicates polling when multiple tasks monitor the same product
- **Option number caching** — avoids redundant HTTP requests during ATC
- **Phantom cart detection** — verifies cart at checkout page (Audi site returns fake success under load)

### Infrastructure

- **Server:** AWS EC2 (t3.micro, 1GB RAM, 2 vCPU)
- **Domain:** audi-tickets.duckdns.org (Let's Encrypt SSL)
- **Docker:** backend (FastAPI + Playwright), frontend (Vue 3), nginx, certbot
- **Database:** SQLite
- **Notifications:** Discord webhook (rate-limited queue, 0.5s spacing)
