# Backend Development Guide

## Current Focus Areas
- Improve bot resilience and retry logic
- Add comprehensive logging
- Implement rate limiting
- Add health check endpoints

## Key Dependencies
- `curl_cffi` - TLS fingerprinting (Chrome impersonation)
- `FastAPI` - Web framework
- `SQLAlchemy` - ORM

## Testing Strategy
- Add pytest framework
- Mock the Audi ticket API for unit tests
- Integration tests for websocket connections