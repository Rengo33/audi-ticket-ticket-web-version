"""
Cart session and checkout proxy endpoints.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from curl_cffi.requests import Session as CurlSession

from ..database import get_db
from ..auth import get_current_user
from ..models import CartSession
from ..schemas import CartSessionResponse

router = APIRouter(tags=["checkout"])


@router.get("/api/carts", response_model=list[CartSessionResponse])
async def list_cart_sessions(
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """List all cart sessions."""
    sessions = db.query(CartSession)\
        .order_by(CartSession.created_at.desc())\
        .limit(50)\
        .all()
    return sessions


@router.get("/checkout/{token}", response_class=HTMLResponse)
async def checkout_proxy_page(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Mobile checkout page.
    No auth required - the token IS the auth.
    """
    cart = db.query(CartSession).filter(CartSession.token == token).first()
    
    if not cart:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Session Not Found</title>
                <style>
                    body { font-family: -apple-system, sans-serif; padding: 20px; text-align: center; background: #1a1a2e; color: white; }
                    .error { color: #ff6b6b; font-size: 1.5em; margin-top: 50px; }
                </style>
            </head>
            <body>
                <div class="error">❌ Session nicht gefunden</div>
                <p>Der Link ist ungültig oder abgelaufen.</p>
            </body>
            </html>
            """,
            status_code=404
        )
    
    # Check if expired
    if datetime.utcnow() > cart.expires_at:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Session Expired</title>
                <style>
                    body { font-family: -apple-system, sans-serif; padding: 20px; text-align: center; background: #1a1a2e; color: white; }
                    .error { color: #ff6b6b; font-size: 1.5em; margin-top: 50px; }
                </style>
            </head>
            <body>
                <div class="error">⏰ Session abgelaufen</div>
                <p>Die Warenkorb-Session ist nicht mehr gültig.</p>
            </body>
            </html>
            """,
            status_code=410
        )
    
    # Calculate remaining time
    remaining = (cart.expires_at - datetime.utcnow()).total_seconds()
    remaining_min = int(remaining // 60)
    remaining_sec = int(remaining % 60)
    
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>🎫 Checkout - Audi Tickets</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: white;
                min-height: 100vh;
            }}
            .container {{
                max-width: 500px;
                margin: 0 auto;
            }}
            .card {{
                background: rgba(255,255,255,0.1);
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 20px;
                backdrop-filter: blur(10px);
            }}
            .success-badge {{
                background: #00c853;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: 600;
                display: inline-block;
                margin-bottom: 16px;
            }}
            h1 {{
                margin: 0 0 8px 0;
                font-size: 1.5em;
            }}
            .timer {{
                font-size: 2.5em;
                font-weight: bold;
                color: #ffd700;
                text-align: center;
                margin: 20px 0;
            }}
            .timer-label {{
                text-align: center;
                color: #aaa;
                font-size: 0.9em;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                padding: 12px 0;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }}
            .info-label {{ color: #aaa; }}
            .info-value {{ font-weight: 600; }}
            .checkout-btn {{
                display: block;
                width: 100%;
                padding: 18px;
                background: linear-gradient(135deg, #00c853 0%, #00e676 100%);
                color: white;
                text-decoration: none;
                text-align: center;
                font-size: 1.2em;
                font-weight: bold;
                border-radius: 12px;
                margin-top: 20px;
                box-shadow: 0 4px 15px rgba(0,200,83,0.4);
            }}
            .checkout-btn:active {{
                transform: scale(0.98);
            }}
            .warning {{
                background: rgba(255,193,7,0.2);
                border: 1px solid #ffc107;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
                font-size: 0.9em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <span class="success-badge">✅ Im Warenkorb</span>
                <h1>Audi Tickets</h1>
                <p style="color: #aaa; margin: 0;">Menge: {cart.quantity}</p>
            </div>
            
            <div class="card">
                <div class="timer-label">Verbleibende Zeit</div>
                <div class="timer" id="timer">{remaining_min:02d}:{remaining_sec:02d}</div>
                <div class="timer-label">Minuten : Sekunden</div>
            </div>
            
            <div class="card">
                <div class="info-row">
                    <span class="info-label">Cart Speed</span>
                    <span class="info-value">{cart.total_time:.2f}s</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Session</span>
                    <span class="info-value">{token[:8]}...</span>
                </div>
            </div>
            
            <a href="/checkout/{token}/cart" class="checkout-btn">
                🛒 Jetzt zur Kasse
            </a>
            
            <div class="warning">
                ⚠️ <strong>Hinweis:</strong> Du wirst zur Checkout-Seite weitergeleitet. 
                Gib dort deine Daten ein und schließe den Kauf ab, bevor die Zeit abläuft!
            </div>
        </div>
        
        <script>
            let remaining = {int(remaining)};
            const timerEl = document.getElementById('timer');
            
            setInterval(() => {{
                remaining--;
                if (remaining <= 0) {{
                    timerEl.textContent = '00:00';
                    timerEl.style.color = '#ff6b6b';
                    return;
                }}
                const min = Math.floor(remaining / 60);
                const sec = remaining % 60;
                timerEl.textContent = String(min).padStart(2, '0') + ':' + String(sec).padStart(2, '0');
                
                if (remaining < 120) {{
                    timerEl.style.color = '#ff6b6b';
                }}
            }}, 1000);
        </script>
    </body>
    </html>
    """)


@router.get("/checkout/{token}/redirect")
async def checkout_redirect(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Redirect to the proxy checkout page.
    """
    return RedirectResponse(url=f"/checkout/{token}/cart", status_code=302)


# Store sessions for reuse
_proxy_sessions: dict = {}


def get_proxy_session(cart) -> CurlSession:
    """Get or create a session with the cart cookie."""
    if cart.token not in _proxy_sessions:
        session = CurlSession(impersonate="chrome120")
        session.cookies.set(cart.cookie_name, cart.cookie_value, domain=cart.cookie_domain)
        _proxy_sessions[cart.token] = session
    return _proxy_sessions[cart.token]


def rewrite_html_for_proxy(html: str, token: str, base_url: str) -> str:
    """Rewrite HTML to route all requests through our proxy."""
    
    # Replace absolute URLs to Audi site with our proxy
    html = html.replace(
        'https://audidefuehrungen2.regiondo.de/',
        f'/checkout/{token}/proxy/'
    )
    html = html.replace(
        'http://audidefuehrungen2.regiondo.de/',
        f'/checkout/{token}/proxy/'
    )
    
    # Replace relative URLs
    html = html.replace('href="/', f'href="/checkout/{token}/proxy/')
    html = html.replace("href='/", f"href='/checkout/{token}/proxy/")
    html = html.replace('action="/', f'action="/checkout/{token}/proxy/')
    html = html.replace("action='/", f"action='/checkout/{token}/proxy/")
    
    # Fix form actions that are relative (no leading slash)
    html = html.replace('action="checkout/', f'action="/checkout/{token}/proxy/checkout/')
    
    # Keep external resources (CSS/JS from CDNs) as-is
    # But proxy the Audi-specific ones
    
    # Add base tag for any missed relative URLs
    if '<head>' in html:
        html = html.replace(
            '<head>',
            f'<head><base href="/checkout/{token}/proxy/">'
        )
    
    return html


@router.get("/checkout/{token}/cart")
async def checkout_cart_page(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Proxy the Audi cart page - main entry point for mobile checkout.
    """
    cart = db.query(CartSession).filter(CartSession.token == token).first()
    
    if not cart:
        raise HTTPException(404, "Session not found")
    
    if datetime.utcnow() > cart.expires_at:
        raise HTTPException(410, "Session expired")
    
    # Mark as used
    if not cart.used_at:
        cart.used_at = datetime.utcnow()
        db.commit()
    
    try:
        session = get_proxy_session(cart)
        response = session.get("https://audidefuehrungen2.regiondo.de/checkout/cart")
        
        if response.status_code == 200:
            html = rewrite_html_for_proxy(response.text, token, "https://audidefuehrungen2.regiondo.de")
            return HTMLResponse(content=html)
        else:
            raise HTTPException(502, f"Audi server returned {response.status_code}")
            
    except Exception as e:
        raise HTTPException(502, f"Proxy error: {str(e)}")


@router.get("/checkout/{token}/proxy/{path:path}")
async def checkout_proxy_get(
    token: str,
    path: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Proxy GET requests to Audi checkout.
    """
    cart = db.query(CartSession).filter(CartSession.token == token).first()
    
    if not cart:
        raise HTTPException(404, "Session not found")
    
    if datetime.utcnow() > cart.expires_at:
        raise HTTPException(410, "Session expired")
    
    target_url = f"https://audidefuehrungen2.regiondo.de/{path}"
    if request.query_params:
        target_url += f"?{request.query_params}"
    
    try:
        session = get_proxy_session(cart)
        response = session.get(target_url)
        
        content_type = response.headers.get('content-type', '')
        
        # If HTML, rewrite URLs
        if 'text/html' in content_type:
            html = rewrite_html_for_proxy(response.text, token, "https://audidefuehrungen2.regiondo.de")
            return HTMLResponse(content=html, status_code=response.status_code)
        
        # For other content types, return as-is
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=content_type
        )
            
    except Exception as e:
        raise HTTPException(502, f"Proxy error: {str(e)}")


@router.post("/checkout/{token}/proxy/{path:path}")
async def checkout_proxy_post(
    token: str,
    path: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Proxy POST requests to Audi checkout (form submissions).
    """
    cart = db.query(CartSession).filter(CartSession.token == token).first()
    
    if not cart:
        raise HTTPException(404, "Session not found")
    
    if datetime.utcnow() > cart.expires_at:
        raise HTTPException(410, "Session expired")
    
    target_url = f"https://audidefuehrungen2.regiondo.de/{path}"
    
    try:
        session = get_proxy_session(cart)
        
        # Get form data
        content_type = request.headers.get('content-type', '')
        
        if 'application/x-www-form-urlencoded' in content_type:
            body = await request.body()
            response = session.post(
                target_url,
                data=body.decode('utf-8'),
                headers={'Content-Type': content_type}
            )
        elif 'multipart/form-data' in content_type:
            body = await request.body()
            response = session.post(
                target_url,
                data=body,
                headers={'Content-Type': content_type}
            )
        else:
            body = await request.body()
            response = session.post(
                target_url,
                data=body,
                headers={'Content-Type': content_type} if content_type else {}
            )
        
        response_content_type = response.headers.get('content-type', '')
        
        # Handle redirects
        if response.status_code in [301, 302, 303, 307, 308]:
            location = response.headers.get('location', '')
            if location:
                # Rewrite redirect URL to go through proxy
                if location.startswith('https://audidefuehrungen2.regiondo.de/'):
                    location = location.replace(
                        'https://audidefuehrungen2.regiondo.de/',
                        f'/checkout/{token}/proxy/'
                    )
                elif location.startswith('/'):
                    location = f'/checkout/{token}/proxy{location}'
                return RedirectResponse(url=location, status_code=response.status_code)
        
        # If HTML, rewrite URLs
        if 'text/html' in response_content_type:
            html = rewrite_html_for_proxy(response.text, token, "https://audidefuehrungen2.regiondo.de")
            return HTMLResponse(content=html, status_code=response.status_code)
        
        # For other content types, return as-is
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response_content_type
        )
            
    except Exception as e:
        raise HTTPException(502, f"Proxy error: {str(e)}")
