"""
Cart session and checkout proxy endpoints.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from curl_cffi.requests import Session as CurlSession

from ..database import get_db
from ..auth import get_current_user
from ..models import CartSession
from ..schemas import CartSessionResponse
from ..config import get_settings

settings = get_settings()

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


@router.get("/api/checkout/{token}/cookie")
async def get_checkout_cookie(
    token: str,
    db: Session = Depends(get_db)
):
    """Return cookie data for a cart session. No auth — token IS the auth."""
    cart = db.query(CartSession).filter(CartSession.token == token).first()
    if not cart:
        raise HTTPException(404, "Session not found")
    if datetime.utcnow() > cart.expires_at:
        raise HTTPException(410, "Session expired")

    return JSONResponse(
        content={
            "name": cart.cookie_name,
            "value": cart.cookie_value,
            "domain": cart.cookie_domain,
            "checkout_url": "https://audidefuehrungen2.regiondo.de/checkout/cart",
            "expires_at": cart.expires_at.isoformat() + "Z"
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
        }
    )


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
        _proxy_sessions.pop(cart.token, None)
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

    cookie_api_url = f"{settings.base_url}/api/checkout/{token}/cookie"
    js_snippet = f"fetch('{cookie_api_url}').then(r=>r.json()).then(d=>{{document.cookie=d.name+'='+d.value+';path=/;domain=.audidefuehrungen2.regiondo.de';location.href=d.checkout_url}})"

    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Checkout - Audi Tickets</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 20px;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: white; min-height: 100vh;
            }}
            .container {{ max-width: 500px; margin: 0 auto; }}
            .card {{
                background: rgba(255,255,255,0.1); border-radius: 16px;
                padding: 24px; margin-bottom: 20px; backdrop-filter: blur(10px);
            }}
            .success-badge {{
                background: #00c853; color: white; padding: 8px 16px;
                border-radius: 20px; font-weight: 600; display: inline-block; margin-bottom: 16px;
            }}
            h1 {{ margin: 0 0 8px 0; font-size: 1.5em; }}
            h3 {{ margin: 0 0 12px 0; font-size: 1.1em; }}
            .timer {{
                font-size: 2.5em; font-weight: bold; color: #ffd700; text-align: center; margin: 20px 0;
            }}
            .timer-label {{ text-align: center; color: #aaa; font-size: 0.9em; }}
            .info-row {{
                display: flex; justify-content: space-between; padding: 12px 0;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }}
            .info-label {{ color: #aaa; }}
            .info-value {{ font-weight: 600; }}
            .btn {{
                display: block; width: 100%; padding: 16px; border: none; cursor: pointer;
                text-align: center; font-size: 1.1em; font-weight: bold; border-radius: 12px;
                margin-top: 12px; color: white; text-decoration: none;
            }}
            .btn:active {{ transform: scale(0.98); }}
            .btn-green {{ background: linear-gradient(135deg, #00c853, #00e676); box-shadow: 0 4px 15px rgba(0,200,83,0.4); }}
            .btn-blue {{ background: linear-gradient(135deg, #007AFF, #5856d6); box-shadow: 0 4px 15px rgba(0,122,255,0.3); }}
            .btn-gray {{ background: rgba(255,255,255,0.15); font-size: 0.95em; }}
            .steps {{ color: #ccc; font-size: 0.9em; line-height: 1.8; margin: 12px 0 0 0; padding-left: 0; list-style: none; }}
            .steps li::before {{ content: attr(data-step) ". "; font-weight: 700; color: #ffd700; }}
            .cookie-value {{
                background: rgba(0,0,0,0.3); border-radius: 8px; padding: 12px; margin-top: 12px;
                font-family: monospace; font-size: 0.85em; word-break: break-all; color: #7dd3fc;
                cursor: pointer; position: relative;
            }}
            .copied {{ position: absolute; top: -24px; right: 8px; background: #00c853; padding: 4px 10px; border-radius: 6px; font-size: 0.8em; font-family: sans-serif; }}
            .divider {{ border-top: 1px solid rgba(255,255,255,0.1); margin: 16px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <span class="success-badge">Im Warenkorb</span>
                <h1>Audi Tickets</h1>
                <p style="color: #aaa; margin: 0;">Menge: {cart.quantity} | Speed: {cart.total_time:.2f}s</p>
            </div>

            <div class="card">
                <div class="timer-label">Verbleibende Zeit</div>
                <div class="timer" id="timer">{remaining_min:02d}:{remaining_sec:02d}</div>
            </div>

            <div class="card">
                <h3>Checkout (Chrome Extension)</h3>
                <p style="color:#ccc;font-size:0.9em;margin-bottom:12px">Empfohlen: Nutze die Chrome Extension fur One-Click Checkout.</p>

                <div class="divider"></div>

                <h3>Manuell (Inkognito)</h3>
                <ol class="steps">
                    <li data-step="1">Offne ein <strong>Inkognito-Fenster</strong> (Strg+Shift+N)</li>
                    <li data-step="2">Gehe zu <a href="https://audidefuehrungen2.regiondo.de" target="_blank" style="color:#7dd3fc">audidefuehrungen2.regiondo.de</a></li>
                    <li data-step="3">Offne DevTools (F12) &rarr; Console</li>
                    <li data-step="4">Paste das Script und drucke Enter</li>
                </ol>
                <button class="btn btn-green" onclick="copyScript()">Script kopieren</button>

                <div class="divider"></div>

                <h3>Cookie Value</h3>
                <div class="cookie-value" id="cookieVal" onclick="copyCookie()">{cart.cookie_value}</div>
                <button class="btn btn-gray" onclick="copyCookie()">Cookie kopieren</button>
            </div>

            <div class="card">
                <h3>Proxy Checkout (ohne Zahlung)</h3>
                <a href="/checkout/{token}/cart" class="btn btn-blue">Warenkorb anzeigen (Proxy)</a>
            </div>
        </div>

        <script>
            const script = `{js_snippet}`;

            function copyScript() {{
                navigator.clipboard.writeText(script).then(() => flash('Script kopiert!'));
            }}

            function copyCookie() {{
                navigator.clipboard.writeText('{cart.cookie_value}').then(() => flash('Cookie kopiert!'));
            }}

            function flash(msg) {{
                const el = document.createElement('div');
                el.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#00c853;color:white;padding:10px 24px;border-radius:10px;font-weight:600;z-index:999;';
                el.textContent = msg;
                document.body.appendChild(el);
                setTimeout(() => el.remove(), 2000);
            }}

            let remaining = {int(remaining)};
            const timerEl = document.getElementById('timer');
            setInterval(() => {{
                remaining--;
                if (remaining <= 0) {{ timerEl.textContent = '00:00'; timerEl.style.color = '#ff6b6b'; return; }}
                const min = Math.floor(remaining / 60);
                const sec = remaining % 60;
                timerEl.textContent = String(min).padStart(2, '0') + ':' + String(sec).padStart(2, '0');
                if (remaining < 120) timerEl.style.color = '#ff6b6b';
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


def rewrite_html_for_proxy(html: str, token: str, base_url: str, cookie_name: str = '', cookie_value: str = '') -> str:
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

    # Inject Stripe fix on checkout pages (runs on main page, watches for payment step via DOM)
    if 'cryozonic_stripe' in html or 'checkoutsimple' in html:
        stripe_fix = f"""
        <script src="https://js.stripe.com/v3/"></script>
        <script>
        (function() {{
            var stripeFixed = false;

            // Watch for payment step appearing in DOM
            var observer = new MutationObserver(function() {{
                if (stripeFixed) return;
                var cardEl = document.getElementById('cryozonic_stripe_cc_num');
                if (!cardEl) return;
                stripeFixed = true;

                // Get Stripe key and client secret from cryozonic object or page
                var pk = (window.cryozonic && cryozonic.apiKey) || null;
                var secret = null;

                // Find client secret in any script or data attribute on the page
                var allScripts = document.querySelectorAll('script');
                for (var i = 0; i < allScripts.length; i++) {{
                    var txt = allScripts[i].textContent;
                    var m = txt.match(/pi_[A-Za-z0-9_]+_secret_[A-Za-z0-9_]+/);
                    if (m) {{ secret = m[0]; break; }}
                }}

                // Also check inline event handlers and hidden inputs
                if (!secret) {{
                    var bodyText = document.body.innerHTML;
                    var m = bodyText.match(/pi_[A-Za-z0-9_]+_secret_[A-Za-z0-9_]+/);
                    if (m) secret = m[0];
                }}

                if (!pk || !secret) {{
                    console.log('Stripe fix: missing pk=' + pk + ' secret=' + !!secret);
                    return;
                }}

                console.log('Stripe fix: injecting Payment Element with pk=' + pk.substring(0,20) + '...');

                // Replace the card input area with Stripe Payment Element
                var container = cardEl.closest('.input-box') || cardEl.parentElement;
                container.innerHTML = '<div id="stripe-payment-element" style="padding:12px 0;background:#fff;border-radius:4px"></div>' +
                    '<div id="stripe-errors" style="color:#ff3b30;margin-top:8px;font-size:14px"></div>';

                var stripe = Stripe(pk);
                var elements = stripe.elements({{ clientSecret: secret }});
                var paymentElement = elements.create('payment');
                paymentElement.mount('#stripe-payment-element');

                // Override place order buttons
                setTimeout(function() {{
                    var btns = document.querySelectorAll('.sc-place-order-btn, .btn-checkout, [onclick*="review.save"], .button.btn-inline');
                    // Also try the "Jetzt kaufen" button
                    if (btns.length === 0) {{
                        document.querySelectorAll('button, .button').forEach(function(b) {{
                            if (b.textContent.match(/kaufen|bestellen|order/i)) {{
                                btns = [b];
                            }}
                        }});
                    }}

                    btns.forEach(function(btn) {{
                        var newBtn = btn.cloneNode(true);
                        newBtn.removeAttribute('onclick');
                        btn.parentNode.replaceChild(newBtn, btn);
                        newBtn.addEventListener('click', function(e) {{
                            e.preventDefault();
                            e.stopPropagation();
                            newBtn.disabled = true;
                            newBtn.textContent = 'Zahlung wird verarbeitet...';
                            var errEl = document.getElementById('stripe-errors');
                            if (errEl) errEl.textContent = '';

                            stripe.confirmPayment({{
                                elements: elements,
                                confirmParams: {{ return_url: window.location.href }},
                                redirect: 'if_required'
                            }}).then(function(result) {{
                                if (result.error) {{
                                    if (errEl) errEl.textContent = result.error.message;
                                    newBtn.disabled = false;
                                    newBtn.textContent = 'Jetzt kaufen';
                                }} else {{
                                    var formData = 'payment[method]=cryozonic_stripeintent&payment[cc_stripejs_token]=' +
                                        encodeURIComponent(result.paymentIntent.id + ':' + result.paymentIntent.payment_method);
                                    fetch('/checkout/{token}/proxy/checkoutsimple/onepage/saveOrder/', {{
                                        method: 'POST',
                                        headers: {{ 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' }},
                                        body: formData
                                    }}).then(function(r) {{ return r.text(); }}).then(function(text) {{
                                        try {{
                                            var data = JSON.parse(text);
                                            if (data.success || data.redirect) {{
                                                window.location.href = data.redirect || '/checkout/{token}/proxy/checkout/onepage/success/';
                                            }} else {{
                                                if (errEl) errEl.textContent = data.error || 'Bestellung fehlgeschlagen';
                                                newBtn.disabled = false;
                                                newBtn.textContent = 'Jetzt kaufen';
                                            }}
                                        }} catch(e) {{
                                            // If response is HTML (success page), just show it
                                            document.open();
                                            document.write(text);
                                            document.close();
                                        }}
                                    }}).catch(function(err) {{
                                        if (errEl) errEl.textContent = 'Netzwerkfehler: ' + err.message;
                                        newBtn.disabled = false;
                                        newBtn.textContent = 'Jetzt kaufen';
                                    }});
                                }}
                            }});
                        }});
                    }});
                }}, 500);
            }});

            observer.observe(document.body, {{ childList: true, subtree: true }});
        }})();
        </script>
        """
        if '</body>' in html:
            html = html.replace('</body>', stripe_fix + '</body>')

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
        _proxy_sessions.pop(cart.token, None)
        raise HTTPException(410, "Session expired")

    # Mark as used
    if not cart.used_at:
        cart.used_at = datetime.utcnow()
        db.commit()
    
    try:
        session = get_proxy_session(cart)
        response = session.get("https://audidefuehrungen2.regiondo.de/checkout/cart")
        
        if response.status_code == 200:
            html = rewrite_html_for_proxy(response.text, token, "https://audidefuehrungen2.regiondo.de", cart.cookie_name, cart.cookie_value)
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
        _proxy_sessions.pop(cart.token, None)
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
            html = rewrite_html_for_proxy(response.text, token, "https://audidefuehrungen2.regiondo.de", cart.cookie_name, cart.cookie_value)
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
        _proxy_sessions.pop(cart.token, None)
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
        
        # If HTML (but not JSON disguised as HTML), rewrite URLs
        resp_text = response.text
        is_json = resp_text.strip()[:1] in ('{', '[')
        if 'text/html' in response_content_type and not is_json:
            html = rewrite_html_for_proxy(resp_text, token, "https://audidefuehrungen2.regiondo.de", cart.cookie_name, cart.cookie_value)
            return HTMLResponse(content=html, status_code=response.status_code)

        # JSON response — rewrite URLs in HTML fragments, inject Stripe fix if needed
        if is_json:
            import json as _json
            try:
                data = _json.loads(resp_text)
                # Rewrite URLs in the HTML fragment
                if isinstance(data, dict) and 'html' in data and isinstance(data['html'], str):
                    data['html'] = data['html'].replace(
                        'https://audidefuehrungen2.regiondo.de/',
                        f'/checkout/{token}/proxy/'
                    )
                    # Inject Stripe fix into the HTML fragment if it contains payment init
                    data['html'] = rewrite_html_for_proxy(
                        data['html'], token, "https://audidefuehrungen2.regiondo.de",
                        cart.cookie_name, cart.cookie_value
                    )
                resp_text = _json.dumps(data)
            except Exception:
                # Fallback: simple string replace
                resp_text = resp_text.replace(
                    'https:\\/\\/audidefuehrungen2.regiondo.de\\/',
                    f'/checkout/{token}/proxy/'
                )
            return Response(content=resp_text, status_code=response.status_code, media_type='application/json')

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response_content_type
        )

    except Exception as e:
        raise HTTPException(502, f"Proxy error: {str(e)}")
