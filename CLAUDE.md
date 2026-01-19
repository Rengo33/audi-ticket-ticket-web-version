# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Audi Ticket Bot - A ticket monitoring and auto-carting system for Audi factory tour tickets. The application monitors ticket availability and automatically adds tickets to cart when they become available.

**Components:**
- `audi-ticket-web/` - Web application (FastAPI backend + Vue 3 frontend)
- `Audi_Ticket_Bot_App/AudiTicketBot/` - Native iOS app (SwiftUI)

## Development Commands

### Backend (FastAPI)
```bash
cd audi-ticket-web/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend (Vue 3 + Vite)
```bash
cd audi-ticket-web/frontend
npm install
npm run dev      # Development server on port 3000
npm run build    # Production build
npm run preview  # Preview production build
```

### Docker (Production)
```bash
cd audi-ticket-web
docker-compose up -d --build
docker-compose logs -f
```

### iOS App (SwiftUI)
Open in Xcode:
```bash
open Audi_Ticket_Bot_App/AudiTicketBot/AudiTicketBot.xcodeproj
```
Build and run on simulator or device. Requires iOS 16+.

## Architecture

### Backend (`audi-ticket-web/backend/`)
- **FastAPI application** with SQLite database
- **Entry point**: `app/main.py` - FastAPI app with lifespan events, CORS, and router registration
- **API routers** in `app/api/`:
  - `auth.py` - Simple password-based authentication
  - `tasks.py` - Task CRUD operations
  - `games.py` - Game/event management
  - `checkout.py` - Checkout link handling for mobile
  - `websocket.py` - Real-time updates via WebSocket
- **Bot logic** in `app/bot/`:
  - `core.py` - `AudiTicketBot` class using `curl_cffi` for TLS fingerprint spoofing (Chrome impersonation)
  - `monitor.py` - `TaskManager` singleton managing async monitoring tasks with auto re-cart after 17 minutes
  - `discord.py` - Discord webhook notifications
  - `scraper.py` - Additional scraping utilities
- **Config**: `app/config.py` - Pydantic settings from environment variables
- **Database**: SQLAlchemy models in `app/models.py`, schemas in `app/schemas.py`

### Frontend (`audi-ticket-web/frontend/`)
- **Vue 3** with Composition API
- **State management**: Pinia stores in `src/stores/`
  - `auth.js` - Authentication state
  - `tasks.js` - Task management
  - `cart.js` - Cart session handling
  - `api.js` - API client
- **Views**: `src/views/` - Dashboard, Tasks, Carts, Games, Login
- **Styling**: TailwindCSS

### iOS App (`Audi_Ticket_Bot_App/AudiTicketBot/`)
- **SwiftUI app** targeting iOS 16+
- **Entry point**: `AudiTicketBotApp.swift` with `ContentView.swift` as root view
- **Views** (TabView-based navigation):
  - `GamesView` - Browse and schedule games
  - `TasksView` - View/manage monitoring tasks
  - `CartsView` - View successful carts with checkout links
  - `SettingsView` - App configuration and logout
  - `CreateTaskView`, `TaskDetailView`, `SafariView`, `LoginView`
- **Services** (singletons):
  - `APIService` - HTTP client for backend API, uses `X-Auth-Token` header
  - `AuthManager` - Authentication state with Keychain storage
  - `TaskMonitor` - Polls backend for task/cart updates
  - `KeychainHelper` - Secure token storage
- **Models**: `Task.swift`, `Cart.swift`, `Game.swift`

### Key Data Flow
1. User creates a monitoring task with a product URL and desired quantity
2. `TaskManager` extracts event/ticket IDs from the product page
3. Bot polls the AJAX availability endpoint every 0.1 seconds
4. When tickets are available, bot attempts add-to-cart with multiple concurrent threads
5. On success, stores session cookie and creates a `CartSession` with unique token
6. Mobile checkout page uses the token to inject the cookie and redirect to checkout
7. After 17 minutes (cart hold time), task automatically re-carts

### WebSocket Protocol
Messages are JSON with `type` and `data` fields:
- `task_update` - Task status changes
- `scan_update` - Scan count and availability updates
- `log` - Task log entries
- `cart_success` - Successful cart with checkout token

## Environment Variables

Required in `.env`:
- `APP_PASSWORD` - Dashboard login password
- `SECRET_KEY` - JWT signing key
- `DISCORD_WEBHOOK_URL` - Optional Discord notifications
- `DATABASE_URL` - SQLite path (default: `sqlite:///./data/tickets.db`)

## Testing

No test framework is currently configured. The backend uses `curl_cffi` for HTTP requests which requires testing against the live site.
