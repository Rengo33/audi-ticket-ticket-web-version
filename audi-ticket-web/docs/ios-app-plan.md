# API Contract

All agents must respect this contract when making changes.

## Authentication
- Endpoint: POST `/api/auth/login`
- Response: `{access_token: string}`

## Task Management
- GET `/api/tasks` - List all tasks
- POST `/api/tasks` - Create task
- PUT `/api/tasks/{id}` - Update task
- DELETE `/api/tasks/{id}` - Delete task

## WebSocket Events
- `task_update` - Task status changes
- `cart_success` - Checkout token available

## Mobile Checkout
- GET `/mobile/checkout/{token}` - Cookie injection + redirect
