"""
Auto Checkout (ACO) — server-side billing + Stripe payment.

Two confirm paths:
  * pure-HTTP via curl_cffi chrome120 impersonation (fast, no Chromium)
  * Playwright headless Chromium (legacy, ~1 GB RAM per run)

Dispatch is controlled by settings.use_pure_http_confirm. When the pure-HTTP
path raises an exception the dispatcher falls back to Playwright so a regression
still ends with a working checkout.
"""
import asyncio
import json
import logging
import re
import time
import traceback
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession

from ..config import get_settings
from ..crypto import decrypt
from ..models import BillingProfile

logger = logging.getLogger(__name__)

STRIPE_PK = "pk_live_0j2JVbs4TBKMV39UGD7KmTqU"
AUDI_BASE = "https://audidefuehrungen2.regiondo.de"
STRIPE_JS_VERSION = "stripe.js/cc947ffb8d; stripe-js-v3/cc947ffb8d; card-element"

# Only one headless browser checkout at a time (server memory constraint)
_browser_lock = asyncio.Lock()

# Berechtigte Gesellschaft — hardcoded to AUDI AG. Option value is stable
# across events. Change or make per-profile if other employers ever need it.
BERECHTIGTE_GESELLSCHAFT_AUDI_AG = "49289"

# The checkout form uses different buyer_field_N IDs per event (museum uses
# buyer_field_5 for Stammnummer, Bayern uses buyer_field_20709, etc.) and
# some events omit the department field entirely. We scrape the form.
_FIELD_RE = re.compile(
    r'name="custom_field\[buyer\]\[(buyer_field_\d+)\]"(?:[^>]*placeholder="([^"]*)")?',
    re.IGNORECASE,
)
_LABEL_RE = re.compile(r'<label[^>]*>([^<]{1,120})</label>')


def _discover_buyer_fields(html: str) -> dict[str, str]:
    """Return {purpose: buyer_field_N} for the buyer fields on the form.

    purpose is one of: "stammnummer", "department", "gesellschaft". Only keys
    for fields actually present on the page are included.
    """
    found: dict[str, str] = {}
    for m in _FIELD_RE.finditer(html):
        field_id = m.group(1)
        placeholder = (m.group(2) or "").lower()

        # Closest preceding <label> is usually the label for the input.
        labels = _LABEL_RE.findall(html[max(0, m.start() - 600):m.start()])
        label = labels[-1].lower() if labels else ""
        hint = f"{label} {placeholder}"

        if "stammnummer" in hint and "stammnummer" not in found:
            found["stammnummer"] = field_id
        elif ("abteilung" in hint or "department" in hint) and "department" not in found:
            found["department"] = field_id
        elif "berechtigt" in hint and "gesellschaft" not in found:
            found["gesellschaft"] = field_id
    return found


def _decrypt_card(profile: BillingProfile) -> dict[str, str]:
    return {
        "number": decrypt(profile.card_number_enc),
        "exp_month": decrypt(profile.card_exp_month_enc),
        "exp_year": decrypt(profile.card_exp_year_enc),
        "cvc": decrypt(profile.card_cvc_enc),
    }


@dataclass
class CheckoutResult:
    success: bool
    status: str  # billing_done, payment_confirmed, completed, failed
    message: str = ""
    payment_intent_id: str = ""
    payment_method_id: str = ""
    client_secret: str = ""
    order_url: str = ""


class AutoCheckout:
    """Handles billing (server-side) and payment (Stripe)."""

    def __init__(self, cookie_name: str, cookie_value: str):
        self.session: Optional[AsyncSession] = None
        self.cookie_name = cookie_name
        self.cookie_value = cookie_value

    async def __aenter__(self):
        self.session = AsyncSession(impersonate="chrome120")
        self.session.cookies.set(self.cookie_name, self.cookie_value, domain="audidefuehrungen2.regiondo.de")
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def submit_billing(self, profile: BillingProfile) -> CheckoutResult:
        """Step 1: Submit billing details server-side via curl."""
        try:
            r = await self.session.get(f"{AUDI_BASE}/checkoutsimple/onepage/index")
            if r.status_code != 200:
                return CheckoutResult(False, "failed", f"Checkout page returned {r.status_code}")

            buyer_fields = _discover_buyer_fields(r.text)
            logger.info(f"[ACO] Discovered buyer fields: {buyer_fields}")

            form_data = {
                "type": "first",
                "skip_shipping_method": "1",
                "firstname": profile.firstname,
                "lastname": profile.lastname,
                "email": profile.email,
                "email_confirm": profile.email,
                "telephone": profile.telephone,
                "is_tax_invoice_required": "on",
                "tax_invoice_recipient_name": profile.invoice_recipient or f"{profile.firstname} {profile.lastname}",
                "company": profile.invoice_company or "",
                "company_tax_id": profile.invoice_tax_id or "",
                "street[]": profile.invoice_street or "",
                "postcode": profile.invoice_postcode or "",
                "city": profile.invoice_city or "",
                "country_id": profile.invoice_country or "DE",
            }
            if fid := buyer_fields.get("stammnummer"):
                form_data[f"custom_field[buyer][{fid}]"] = profile.stammnummer
            if fid := buyer_fields.get("department"):
                form_data[f"custom_field[buyer][{fid}]"] = profile.department or ""
            if fid := buyer_fields.get("gesellschaft"):
                form_data[f"custom_field[buyer][{fid}]"] = BERECHTIGTE_GESELLSCHAFT_AUDI_AG

            r = await self.session.post(
                f"{AUDI_BASE}/checkoutsimple/threestep/posteditaddress",
                data=urlencode(form_data),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                }
            )

            if r.status_code != 200:
                return CheckoutResult(False, "failed", f"Billing POST returned {r.status_code}")

            data = r.json()
            if not data.get("success"):
                return CheckoutResult(False, "failed", f"Billing rejected: {data.get('message', str(data))}")

            html = data.get("html", "")
            secret_match = re.search(r'(pi_[A-Za-z0-9_]+_secret_[A-Za-z0-9_]+)', html)
            if not secret_match:
                return CheckoutResult(False, "failed", "Could not find payment intent client secret")

            client_secret = secret_match.group(1)
            pi_id = client_secret.split("_secret_")[0]

            logger.info(f"[ACO] Billing submitted. PI: {pi_id}")
            return CheckoutResult(True, "billing_done", payment_intent_id=pi_id, client_secret=client_secret)

        except Exception as e:
            logger.error(f"[ACO] Billing error: {e}")
            return CheckoutResult(False, "failed", str(e))

    async def confirm_payment(self, profile: BillingProfile, pi_id: str, client_secret: str) -> CheckoutResult:
        """Step 2: Confirm payment on Stripe.

        Dispatches to the pure-HTTP path when settings.use_pure_http_confirm is
        true, falling back to Playwright on any exception. Card-decision errors
        (card_declined, incorrect_cvc, etc.) are NOT fallback conditions — they
        are real results and are returned unchanged.
        """
        if get_settings().use_pure_http_confirm:
            try:
                logger.info("[ACO] confirm: pure-HTTP path")
                return await self._confirm_http(profile, pi_id, client_secret)
            except Exception as e:
                logger.warning(f"[ACO] pure-HTTP confirm failed, falling back to Playwright: {type(e).__name__}: {e}")
                logger.warning(traceback.format_exc())
        else:
            logger.info("[ACO] confirm: Playwright path (flag off)")
        return await self._confirm_playwright(profile, pi_id, client_secret)

    # ------------------------------------------------------------------
    # Pure-HTTP confirm path
    # ------------------------------------------------------------------
    async def _confirm_http(self, profile: BillingProfile, pi_id: str, client_secret: str) -> CheckoutResult:
        card = _decrypt_card(profile)
        if not card["number"]:
            raise RuntimeError("No card details in profile")
        cardholder = f"{profile.firstname} {profile.lastname}"

        # /v1/payment_intents/{pi}/confirm
        resp = await _stripe_confirm(pi_id, client_secret, cardholder, card)
        logger.info(f"[ACO] stripe /confirm → status={resp.get('status')} next_action={resp.get('next_action', {}).get('type')} error={(resp.get('error') or {}).get('code')}")

        if resp.get("error"):
            err = resp["error"]
            return CheckoutResult(
                success=False,
                status="failed",
                message=err.get("message", "Card error"),
                payment_intent_id=pi_id,
                client_secret=client_secret,
            )

        status = resp.get("status")
        pm_raw = resp.get("payment_method")
        pm_id = pm_raw if isinstance(pm_raw, str) else ((pm_raw or {}).get("id") or "")

        # 3DS branch: the pure-HTTP 3DS2 handshake requires Device Data Collection
        # against the issuer's ACS, which only works from a browser context. Raise
        # so confirm_payment falls back to Playwright — it handles all 3DS variants
        # (fingerprint + challenge, frictionless) via Stripe.js.
        if status in ("requires_action", "requires_source_action"):
            na_type = (resp.get("next_action") or {}).get("type")
            usk_type = ((resp.get("next_action") or {}).get("use_stripe_sdk") or {}).get("type")
            raise RuntimeError(f"3DS required (next_action={na_type}/{usk_type}) — pure-HTTP does not yet support the ACS handshake; falling back to Playwright")

        if status in ("succeeded", "requires_capture"):
            logger.info(f"[ACO] HTTP confirm success: status={status} pm={pm_id}")
            return CheckoutResult(
                success=True,
                status="payment_confirmed",
                payment_intent_id=pi_id,
                payment_method_id=pm_id,
                client_secret=client_secret,
            )

        err = resp.get("last_payment_error") or {}
        msg = err.get("message") or f"Unexpected status: {status}"
        return CheckoutResult(
            success=False,
            status="failed",
            message=msg,
            payment_intent_id=pi_id,
            payment_method_id=pm_id,
            client_secret=client_secret,
        )

    # ------------------------------------------------------------------
    # Playwright confirm path (fallback / legacy)
    # ------------------------------------------------------------------
    async def _confirm_playwright(self, profile: BillingProfile, pi_id: str, client_secret: str) -> CheckoutResult:
        try:
            card_number = decrypt(profile.card_number_enc)
            card_cvc = decrypt(profile.card_cvc_enc)
            card_exp_month = decrypt(profile.card_exp_month_enc)
            card_exp_year = decrypt(profile.card_exp_year_enc)

            if not card_number:
                return CheckoutResult(False, "failed", "No card details in profile")

            cardholder = f"{profile.firstname} {profile.lastname}"

            from playwright.async_api import async_playwright

            async with _browser_lock:
                logger.info("[ACO] Launching browser for Stripe payment...")
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
                    page = await browser.new_page()

                    await page.goto(f"{AUDI_BASE}/checkout/cart", wait_until="domcontentloaded", timeout=20000)

                    # Call Stripe confirm API from browser context (valid origin + hCaptcha)
                    # If 3DS required, handleCardAction resolves after user approves on phone
                    result_data = await page.evaluate(f"""
                        new Promise(async (resolve) => {{
                            var script = document.createElement('script');
                            script.src = 'https://js.stripe.com/v3/';
                            script.onload = async function() {{
                                try {{
                                    var stripe = Stripe('{STRIPE_PK}');

                                    var formData = new URLSearchParams();
                                    formData.set('payment_method_data[type]', 'card');
                                    formData.set('payment_method_data[card][number]', '{card_number}');
                                    formData.set('payment_method_data[card][exp_month]', '{card_exp_month}');
                                    formData.set('payment_method_data[card][exp_year]', '{card_exp_year}');
                                    formData.set('payment_method_data[card][cvc]', '{card_cvc}');
                                    formData.set('payment_method_data[billing_details][name]', '{cardholder}');
                                    formData.set('payment_method_data[referrer]', '{AUDI_BASE}');
                                    formData.set('payment_method_data[payment_user_agent]', 'stripe.js/cc947ffb8d; stripe-js-v3/cc947ffb8d; card-element');
                                    formData.set('payment_method_data[time_on_page]', '30000');
                                    formData.set('expected_payment_method_type', 'card');
                                    formData.set('use_stripe_sdk', 'true');
                                    formData.set('key', '{STRIPE_PK}');
                                    formData.set('client_secret', '{client_secret}');

                                    var resp = await fetch('https://api.stripe.com/v1/payment_intents/{pi_id}/confirm', {{
                                        method: 'POST',
                                        headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                                        body: formData.toString()
                                    }});
                                    var data = await resp.json();

                                    if (data.error) {{
                                        resolve({{ success: false, error: data.error.message, code: data.error.code, decline: data.error.decline_code }});
                                    }} else {{
                                        var status = data.status;
                                        var pmId = '';
                                        if (data.payment_method && typeof data.payment_method === 'object') pmId = data.payment_method.id;
                                        else if (typeof data.payment_method === 'string') pmId = data.payment_method;

                                        if (status === 'requires_action' || status === 'requires_source_action') {{
                                            // 3DS required — confirmCardPayment handles 3DS challenge
                                            var actionResult = await stripe.confirmCardPayment(data.client_secret);
                                            if (actionResult.error) {{
                                                resolve({{ success: false, error: actionResult.error.message, code: '3ds_failed' }});
                                            }} else {{
                                                resolve({{
                                                    success: true,
                                                    status: actionResult.paymentIntent.status,
                                                    pi_id: actionResult.paymentIntent.id,
                                                    pm_id: actionResult.paymentIntent.payment_method || pmId
                                                }});
                                            }}
                                        }} else {{
                                            resolve({{ success: true, status: status, pi_id: data.id, pm_id: pmId }});
                                        }}
                                    }}
                                }} catch(e) {{
                                    resolve({{ success: false, error: e.message }});
                                }}
                            }};
                            script.onerror = function() {{ resolve({{ success: false, error: 'Failed to load Stripe.js' }}); }};
                            document.head.appendChild(script);
                        }})
                    """)

                    logger.info(f"[ACO] Stripe browser result: {json.dumps(result_data)[:300]}")
                    await browser.close()

            if not result_data.get('success'):
                error_msg = result_data.get('error', 'Unknown error')
                decline = result_data.get('decline', '')
                logger.error(f"[ACO] Payment failed: {error_msg} (code: {result_data.get('code')}, decline: {decline})")
                return CheckoutResult(False, "failed", error_msg, pi_id, "", client_secret)

            status = result_data.get('status')
            pm_id = result_data.get('pm_id', '')
            logger.info(f"[ACO] Payment status: {status}, PM: {pm_id}")

            if status in ("succeeded", "requires_capture"):
                return CheckoutResult(True, "payment_confirmed", payment_intent_id=pi_id, payment_method_id=pm_id, client_secret=client_secret)

            return CheckoutResult(False, "failed", f"Unexpected status: {status}", pi_id, pm_id, client_secret)

        except Exception as e:
            logger.error(f"[ACO] Payment error: {e}")
            logger.error(traceback.format_exc())
            return CheckoutResult(False, "failed", str(e))

    async def place_order(self, pi_id: str, pm_id: str, cardholder: str) -> CheckoutResult:
        """Step 3: Submit the order to the Audi backend."""
        try:
            form_data = {
                "payment[method]": "cryozonic_stripeintent",
                "payment[cc_owner]": cardholder,
                "payment[cc_stripejs_token]": f"{pi_id}:{pm_id}",
                "agreement_with_terms": "on",
            }

            r = await self.session.post(
                f"{AUDI_BASE}/checkoutsimple/threestep/saveorder",
                data=urlencode(form_data),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

            logger.info(f"[ACO] SaveOrder status: {r.status_code}, response: {r.text[:300]}")

            if r.status_code == 200:
                try:
                    data = r.json()
                    if data.get("success") or data.get("redirect"):
                        return CheckoutResult(True, "completed", "Order placed!", order_url=data.get("redirect", ""))
                    else:
                        return CheckoutResult(False, "failed", f"Order failed: {data.get('error', str(data))}")
                except Exception:
                    if "success" in r.text.lower() or "Bestellung" in r.text:
                        return CheckoutResult(True, "completed", "Order placed!")
                    return CheckoutResult(False, "failed", f"Unexpected response: {r.text[:200]}")

            return CheckoutResult(False, "failed", f"SaveOrder returned {r.status_code}")

        except Exception as e:
            logger.error(f"[ACO] SaveOrder error: {e}")
            return CheckoutResult(False, "failed", str(e))


# ------------------------------------------------------------------
# Module-level Stripe HTTP helpers.
# Each raises on infrastructure errors so the dispatcher falls back to
# Playwright. Card-decision responses (4xx with error body) are returned
# as normal JSON for the caller to interpret.
# ------------------------------------------------------------------
async def _stripe_confirm(pi_id: str, client_secret: str, cardholder: str, card: dict) -> dict:
    body = {
        "payment_method_data[type]": "card",
        "payment_method_data[card][number]": card["number"],
        "payment_method_data[card][exp_month]": card["exp_month"],
        "payment_method_data[card][exp_year]": card["exp_year"],
        "payment_method_data[card][cvc]": card["cvc"],
        "payment_method_data[billing_details][name]": cardholder,
        "payment_method_data[referrer]": AUDI_BASE,
        "payment_method_data[payment_user_agent]": STRIPE_JS_VERSION,
        "payment_method_data[time_on_page]": "30000",
        "expected_payment_method_type": "card",
        "use_stripe_sdk": "true",
        "key": STRIPE_PK,
        "client_secret": client_secret,
    }
    async with AsyncSession(impersonate="chrome120") as s:
        r = await s.post(
            f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm",
            data=urlencode(body),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            },
            timeout=20,
        )
    return r.json()


async def _stripe_3ds2_authenticate(source: str) -> dict:
    body = {"source": source, "key": STRIPE_PK, "is_stripe_sdk": "true"}
    async with AsyncSession(impersonate="chrome120") as s:
        r = await s.post(
            "https://api.stripe.com/v1/3ds2/authenticate",
            data=urlencode(body),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            },
            timeout=20,
        )
    return r.json()


async def _stripe_poll_pi(pi_id: str, client_secret: str, timeout_s: int = 180) -> dict:
    terminal = {"succeeded", "requires_capture", "canceled", "requires_payment_method"}
    start = time.time()
    async with AsyncSession(impersonate="chrome120") as s:
        last_status = None
        while time.time() - start < timeout_s:
            r = await s.get(
                f"https://api.stripe.com/v1/payment_intents/{pi_id}",
                params={"key": STRIPE_PK, "client_secret": client_secret},
                timeout=10,
            )
            data = r.json()
            status = data.get("status")
            if status != last_status:
                logger.info(f"[ACO] poll t={int(time.time()-start)}s status={status}")
                last_status = status
            if status in terminal:
                return data
            await asyncio.sleep(3)
    raise TimeoutError(f"Poll timed out after {timeout_s}s, last status={last_status}")
