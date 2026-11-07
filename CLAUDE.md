# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Audi Ticket Bot - monitors the Audi employee ticket shop (`audidefuehrungen2.regiondo.de`, a Regiondo/Magento 1 white-label shop) for FC Bayern match tickets, adds them to cart the moment they go on sale, and optionally checks out automatically.

**Components:**
- `audi-ticket-web/` - Web application (FastAPI backend + Vue 3 frontend, Docker + nginx)
- `audi-ticket-web/docs/atc-routes.md` - Measured findings on cart routes, latency and the regiondo.net channel

## Development Commands

### Backend (FastAPI)
```bash
cd audi-ticket-web/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest                                  # tests/ (pytest.ini, asyncio_mode=auto)
python -m app.bot.scraper               # parser self-check + live games smoke check
```
`get_settings()` refuses to start while `APP_PASSWORD` / `SECRET_KEY` are at their defaults, so set both (any value) for local runs and tests.

### Frontend (Vue 3 + Vite)
```bash
cd audi-ticket-web/frontend
npm install
npm run dev      # Development server on port 3000
npm run build    # Production build
```

### Docker (Production)
```bash
cd audi-ticket-web
docker-compose up -d --build
docker-compose logs -f
```
Services: `backend`, `frontend`, `nginx`, `certbot`. Production deploy = rsync the source to the server, then `docker compose up -d --build <service>`.

## Architecture

### Backend (`audi-ticket-web/backend/app/`)
- `main.py` - FastAPI app; lifespan runs DB migrations, seeds runtime switches from `AppSettings`, resumes running tasks and the release detector, starts the scheduler
- `config.py` - Pydantic settings from env; `database.py` - SQLite (rollback journal, not WAL — see comment) + `_add_column_if_missing` migrations; `models.py` / `schemas.py`
- `scheduler.py` - starts `ScheduledTask`s at their sale date (05:55 Berlin)
- **API routers** in `api/` (all under `/api` except checkout + websocket):
  - `auth.py` - password login, JWT
  - `tasks.py` - task CRUD, start/stop
  - `games.py` - FC Bayern games list, schedule-on-sale-date; `GET /api/games/upcoming` is **public** (Login screen scoreboard)
  - `billing.py` - billing profiles (card data encrypted via `crypto.py`)
  - `checkout.py` - cart list, mobile checkout proxy (`/checkout/{token}/...`), cookie copy, manual ACO trigger
  - `detector.py` - release detector config/status
  - `settings.py` - runtime switches `shop_via_origin` (Bypass) and `cart_via_regiondo`
  - `push.py` - Web Push subscriptions; `websocket.py` - live updates
- **Bot logic** in `bot/`:
  - `core.py` - `AudiTicketBot` (curl_cffi, `safari17_2_ios` impersonation — the only target that reliably passes Cloudflare): availability, option lookup, add-to-cart, phantom-cart check; origin-IP pinning (Bypass); `add_to_cart_regiondo` (opt-in regiondo.net route)
  - `monitor.py` - `TaskManager` singleton; one shared `AvailabilityWatcher` per product; waits for hidden products to go live; concurrent ATC threads; re-cart after the 17-min hold
  - `release_detector.py` - walks Regiondo's global product-ID counter via the booking widget to find new Audi products at creation (before publication) and auto-starts tasks
  - `scraper.py` - games list from the product API; shop listing + booking-widget lookups for the detector
  - `checkout.py` (`AutoCheckout`) + `aco_dispatcher.py` - server-side auto-checkout (billing → Stripe confirm → place order), one at a time, distinct profiles per event
  - `discord.py` - webhook notifications; `web_push.py` - push notifications

### Upstream hosts
- **Shop host** `audidefuehrungen2.regiondo.de` - behind Cloudflare, which 403s/blocks the server IP for hours. Bypass (`shop_via_origin`) pins it to the origin IPs (resolved from regiondo.net DNS).
- **regiondo.net** - same Magento backend, no Cloudflare. Serves `catalog_ajax/dates|options`, `ajaxadd` (cart lands in the marketplace store, not the Audi store) and the booking widget.
- **Product API** `shopping-experience-api.prod.regiondo.net` (headers `x-tenant: REGIONDO`, `x-partner-code: AU43`) - no Cloudflare; published products only; `manufacturerSku` = `T-AU43-{ticket_id}`. Used for the games list and release detection.

### Frontend (`audi-ticket-web/frontend/src/`)
- Vue 3 Composition API, plain CSS with design tokens in `style.css`
- **Stores** (`stores/`): `api.js` (client), `auth.js`, `tasks.js`, `cart.js`, `logs.js`, `push.js`, `websocket.js`
- **Views** (`views/`): `Login` (public, with the upcoming-fixtures scoreboard), `Tasks` (home, incl. Bypass/regiondo.net toggles), `Carts`, `Billing`, `Detector`, `Logs`

### Key Data Flow
1. A task is created with a product URL (or by the release detector / scheduler)
2. `TaskManager` gets event/ticket IDs from the product page, or from the product API for `/catalog/product/view/id/N` URLs (waits until the product is live)
3. The shared watcher polls `catalog_ajax/dates` every ~10 s (`default_scan_interval`, ±30% jitter): the total (`ticket_id=`) plus, in parallel, each subscribed category (`variation_id=`); a task decides on its own category's stock
4. On stock it resolves the option ID and fires concurrent `ajaxadd` requests, each in its own session
5. On success it stores the `frontend` cookie as a `CartSession` with a unique token (Discord + push notify)
6. Checkout via the mobile proxy page (token = auth) or server-side ACO
7. After 17 minutes (cart hold time) the task re-carts unless ACO placed an order

### WebSocket Protocol
Messages are JSON with `type` and `data`: `task_update`, `scan_update`, `log`, `cart_success`, `cart_update`, `detector_update`, `ping`.

## Environment Variables

Set in `.env` (see `.env.example`):
- `APP_PASSWORD`, `SECRET_KEY` - required, must not be the defaults (`SECRET_KEY` also keys card encryption)
- `DATABASE_URL` - SQLite path (default `sqlite:///./data/tickets.db`)
- `BASE_URL` - public URL used in checkout / Discord links
- `DISCORD_WEBHOOK_URL` - optional notifications
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CONTACT_EMAIL` - Web Push (`scripts/generate_vapid_keys.py`)
- `SHOP_VIA_ORIGIN`, `SHOP_ORIGIN_IPS` - Bypass default + DNS fallback IPs (runtime switch lives in the DB)

## Testing

`pytest` in `audi-ticket-web/backend` (`requirements-dev.txt`). Known failures at the time of writing: `test_detector_classify.py` (collection error) and 4 `TestExtractEventDetails` cases in `test_bot_core.py`. Anything touching the shop needs a check against the live site; keep live probes read-only or use refused adds (`ajaxadd` with too high a quantity reserves nothing).
