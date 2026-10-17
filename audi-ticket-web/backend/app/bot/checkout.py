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
import secrets
import time
import traceback
import uuid
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
# Captured from a fresh manual checkout HAR. Update if Stripe Elements ships a
# new build hash and starts rejecting our payload (look for /elements/sessions
# requests in DevTools, the User-Agent string is in the response).
STRIPE_JS_VERSION = "stripe.js/12427d159a; stripe-js-v3/12427d159a; card-element"


def _stripe_session_id() -> str:
    """Mimic Stripe.js Elements' guid/muid/sid: UUID4 + 6 random hex chars."""
    return f"{uuid.uuid4()}{secrets.token_hex(3)}"

# Any one of these substrings on /checkout/onepage/success means the order was
# placed. Verified against a real manual checkout HAR. The template is shared
# across payment methods (CC, invoice, etc.).
SUCCESS_PAGE_MARKERS = (
    "checkout-onepage-success",
    "checkout-success-page",
    "Vielen Dank für Ihre Bestellung",
)
# Regiondo emits the public 12-digit order number as data-qa on .success-title.
SUCCESS_ORDER_REF_RE = re.compile(r'class="success-title[^"]*"\s+data-qa="(\d+)"')
# The success page's JS embeds the internal order ID in the checkOrderStatus
# poller URL — different from the public order_ref above.
INTERNAL_ORDER_ID_RE = re.compile(r'/checkOrderStatus/order_id/(\d+)')
# Signed invoice-PDF link on the success page. The `k` param is Regiondo's MD5
# signature, so this URL is self-authenticating — no session cookie needed
# to download the PDF once the URL is captured.
INVOICE_URL_RE = re.compile(
    r'https?://[^"\'\s<>]+/getTaxInvoicePdf\.php\?[^"\'\s<>]+',
    re.IGNORECASE,
)

# Stripe PI status groups — single source of truth for confirm / recovery /
# 3DS branching. `requires_capture` is "auth held, awaiting merchant capture"
# and counts as success: the funds are reserved, the merchant will capture.
STRIPE_STATUS_TERMINAL_OK = ("succeeded", "requires_capture")
STRIPE_STATUS_3DS = ("requires_action", "requires_source_action")


def _extract_pm_id(payload: dict) -> str:
    """Stripe returns `payment_method` as either a string ID or an expanded dict."""
    pm_raw = (payload or {}).get("payment_method")
    if isinstance(pm_raw, str):
        return pm_raw
    return ((pm_raw or {}).get("id") or "")


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
    order_ref: str = ""
    invoice_url: str = ""


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
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Origin": AUDI_BASE,
                    "Referer": f"{AUDI_BASE}/checkoutsimple/onepage/index/step/address",
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
        true, falling back to Playwright on any exception. Before the fallback,
        we GET the PI's current state — the HTTP request may have completed
        server-side even if our Python path raised, in which case re-confirming
        via Playwright would fail with payment_intent_unexpected_state and
        leave the user's card with a stranded authorization hold.
        """
        if get_settings().use_pure_http_confirm:
            try:
                logger.info("[ACO] confirm: pure-HTTP path")
                return await self._confirm_http(profile, pi_id, client_secret)
            except Exception as e:
                logger.warning(f"[ACO] pure-HTTP confirm raised: {type(e).__name__}: {e}")
                logger.warning(traceback.format_exc())
                recovered = await self._recover_pi_state(pi_id, client_secret)
                if recovered is not None:
                    return recovered
        else:
            logger.info("[ACO] confirm: Playwright path (flag off)")
        return await self._confirm_playwright(profile, pi_id, client_secret)

    async def _recover_pi_state(self, pi_id: str, client_secret: str) -> Optional[CheckoutResult]:
        """Fetch Stripe PI state and return a terminal CheckoutResult if the
        confirm already succeeded server-side. Returns None if the caller
        should still attempt the Playwright fallback (e.g. 3DS pending)."""
        try:
            pi = await _stripe_get_pi(pi_id, client_secret)
        except Exception as inner:
            logger.warning(f"[ACO] PI state recovery check failed: {type(inner).__name__}: {inner}")
            return None
        status = (pi or {}).get("status")
        logger.info(f"[ACO] PI state after http failure: status={status} pi={pi_id}")
        if status in STRIPE_STATUS_TERMINAL_OK:
            logger.info(f"[ACO] HTTP confirm reached terminal state ({status}); skipping Playwright re-confirm")
            return CheckoutResult(
                success=True,
                status="payment_confirmed",
                message=f"Recovered from transient confirm error (Stripe status={status})",
                payment_intent_id=pi_id,
                payment_method_id=_extract_pm_id(pi),
                client_secret=client_secret,
            )
        if status == "canceled":
            return CheckoutResult(
                success=False,
                status="failed",
                message="Stripe PaymentIntent was canceled",
                payment_intent_id=pi_id,
                client_secret=client_secret,
            )
        return None

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
        if not isinstance(resp, dict):
            raise RuntimeError(f"Stripe /confirm returned non-dict response: {type(resp).__name__}={resp!r}")
        logger.info(
            f"[ACO] stripe /confirm → status={resp.get('status')} "
            f"next_action={(resp.get('next_action') or {}).get('type')} "
            f"error={(resp.get('error') or {}).get('code')} pi={pi_id}"
        )

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
        pm_id = _extract_pm_id(resp)

        # 3DS branch: the pure-HTTP 3DS2 handshake requires Device Data Collection
        # against the issuer's ACS, which only works from a browser context. Raise
        # so confirm_payment falls back to Playwright — it handles all 3DS variants
        # (fingerprint + challenge, frictionless) via Stripe.js.
        if status in STRIPE_STATUS_3DS:
            na_type = (resp.get("next_action") or {}).get("type")
            usk_type = ((resp.get("next_action") or {}).get("use_stripe_sdk") or {}).get("type")
            raise RuntimeError(f"3DS required (next_action={na_type}/{usk_type}) — pure-HTTP does not yet support the ACS handshake; falling back to Playwright")

        if status in STRIPE_STATUS_TERMINAL_OK:
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

            body = _build_stripe_confirm_body(client_secret, cardholder, {
                "number": card_number, "exp_month": card_exp_month,
                "exp_year": card_exp_year, "cvc": card_cvc,
            })

            async with _browser_lock:
                logger.info("[ACO] Launching browser for Stripe payment...")
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        channel="chromium-headless-shell",
                        args=['--no-sandbox', '--disable-dev-shm-usage'],
                    )
                    context = await browser.new_context()
                    # Seed the Audi cart cookie so the page renders against the
                    # actual user session (otherwise /checkout/cart serves a
                    # logged-out shell — Stripe.js still loads, but the request
                    # context isn't representative of a real checkout).
                    await context.add_cookies([{
                        "name": self.cookie_name,
                        "value": self.cookie_value,
                        "domain": "audidefuehrungen2.regiondo.de",
                        "path": "/",
                    }])
                    page = await context.new_page()

                    await page.goto(f"{AUDI_BASE}/checkout/cart", wait_until="domcontentloaded", timeout=20000)

                    result_data = await page.evaluate("""
                        async ({pi_id, body, pk}) => new Promise((resolve) => {
                            const script = document.createElement('script');
                            script.src = 'https://js.stripe.com/v3/';
                            script.onload = async () => {
                                try {
                                    const stripe = Stripe(pk);
                                    const formData = new URLSearchParams();
                                    for (const [k, v] of Object.entries(body)) formData.set(k, v);
                                    const resp = await fetch(
                                        `https://api.stripe.com/v1/payment_intents/${pi_id}/confirm`,
                                        { method: 'POST',
                                          headers: { 'Content-Type': 'application/x-www-form-urlencoded',
                                                     'Accept': 'application/json' },
                                          body: formData.toString() }
                                    );
                                    const data = await resp.json();
                                    if (data.error) {
                                        resolve({ success: false, error: data.error.message,
                                                  code: data.error.code, decline: data.error.decline_code });
                                        return;
                                    }
                                    let pmId = '';
                                    if (data.payment_method && typeof data.payment_method === 'object') pmId = data.payment_method.id;
                                    else if (typeof data.payment_method === 'string') pmId = data.payment_method;
                                    if (data.status === 'requires_action' || data.status === 'requires_source_action') {
                                        const actionResult = await stripe.confirmCardPayment(data.client_secret);
                                        if (actionResult.error) {
                                            resolve({ success: false, error: actionResult.error.message, code: '3ds_failed' });
                                        } else {
                                            resolve({ success: true,
                                                      status: actionResult.paymentIntent.status,
                                                      pi_id: actionResult.paymentIntent.id,
                                                      pm_id: actionResult.paymentIntent.payment_method || pmId });
                                        }
                                    } else {
                                        resolve({ success: true, status: data.status, pi_id: data.id, pm_id: pmId });
                                    }
                                } catch (e) {
                                    resolve({ success: false, error: e.message });
                                }
                            };
                            script.onerror = () => resolve({ success: false, error: 'Failed to load Stripe.js' });
                            document.head.appendChild(script);
                        })
                    """, {"pi_id": pi_id, "body": body, "pk": STRIPE_PK})

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
        """Submit the order to the Audi backend."""
        try:
            # Refresh first so verifyPayment sees the current Stripe PI status —
            # without it, Audi's stale PI cache rejects with "card security check failed".
            await self.session.get(
                f"{AUDI_BASE}/cryozonic_stripeintent/api/payment_intent_refresh",
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "text/javascript, text/html, application/xml, text/xml, */*",
                    "Referer": f"{AUDI_BASE}/checkoutsimple/onepage/index/step/payment",
                },
            )

            form_data = {
                "payment[method]": "cryozonic_stripeintent",
                "payment[cc_owner]": cardholder,
                "agreement_with_terms": "on",
                "newsletter_legal_notice": "",
            }

            r = await self.session.post(
                f"{AUDI_BASE}/checkoutsimple/payone_onepage/verifyPayment",
                data=urlencode(form_data),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Origin": AUDI_BASE,
                    "Referer": f"{AUDI_BASE}/checkoutsimple/onepage/index/step/payment",
                },
            )
            logger.info(f"[ACO] verifyPayment status={r.status_code} body={r.text[:300]}")

            sr = await self.session.get(f"{AUDI_BASE}/checkout/onepage/success")
            html = sr.text
            if any(m in html for m in SUCCESS_PAGE_MARKERS):
                ref_match = SUCCESS_ORDER_REF_RE.search(html)
                order_ref = ref_match.group(1) if ref_match else None

                internal_match = INTERNAL_ORDER_ID_RE.search(html)
                if internal_match:
                    status = await self._check_order_status(internal_match.group(1))
                    if status.get("isCanceled") == 1:
                        return CheckoutResult(
                            False, "failed",
                            f"Audi canceled the order immediately after placement (#{order_ref or 'unknown'})",
                            payment_intent_id=pi_id,
                            payment_method_id=pm_id,
                            order_ref=order_ref or "",
                        )

                logger.info(f"[ACO] order placed, ref={order_ref}")
                # invoice_url is filled in by a background task in
                # aco_dispatcher — Regiondo generates the PDF async and we
                # don't want to hold the dispatcher lock for 30+ s.
                return CheckoutResult(
                    True, "completed",
                    f"Order placed (#{order_ref or 'unknown'})",
                    payment_intent_id=pi_id,
                    payment_method_id=pm_id,
                    order_url=f"{AUDI_BASE}/checkout/onepage/success",
                    order_ref=order_ref or "",
                )

            return CheckoutResult(
                False, "failed",
                f"No success page after verifyPayment (status={r.status_code}): {r.text[:200]}",
                payment_intent_id=pi_id,
                payment_method_id=pm_id,
            )

        except Exception as e:
            logger.error(f"[ACO] verifyPayment error: {e}")
            logger.error(traceback.format_exc())
            return CheckoutResult(False, "failed", str(e))

    async def _poll_invoice_url(self, timeout_s: int = 30, interval_s: float = 1.5) -> str:
        """Poll /checkout/onepage/taxinvoices until the signed PDF URL appears.

        Regiondo generates the invoice PDF asynchronously: `items_count` flips
        from 0 to 1 once the PDF is ready, and `html` then carries the link.
        Returns "" on timeout — the order completes either way and the invoice
        remains reachable from Regiondo's account page."""
        deadline = time.monotonic() + timeout_s
        attempts = 0
        while time.monotonic() < deadline:
            attempts += 1
            url = await self._fetch_invoice_url_once(attempts)
            if url:
                logger.info(f"[ACO] invoice URL captured after {attempts} poll(s): {url[:80]}...")
                return url
            await asyncio.sleep(interval_s)
        logger.warning(f"[ACO] invoice URL not available within {timeout_s}s ({attempts} polls)")
        return ""

    async def _check_order_status(self, internal_order_id: str) -> dict:
        """One-shot sanity check: returns {isPending, isCanceled} (both 0/1).
        Audi sometimes async-cancels orders right after the success page
        renders (fraud review, payment capture failure)."""
        try:
            r = await self.session.get(
                f"{AUDI_BASE}/checkout/onepage/checkOrderStatus/order_id/{internal_order_id}",
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": f"{AUDI_BASE}/checkout/onepage/success",
                },
                timeout=10,
            )
            if r.status_code != 200:
                logger.warning(f"[ACO] checkOrderStatus order_id={internal_order_id} returned {r.status_code}")
                return {}
            data = r.json() or {}
            logger.info(f"[ACO] checkOrderStatus order_id={internal_order_id}: isPending={data.get('isPending')} isCanceled={data.get('isCanceled')}")
            return data
        except Exception as e:
            logger.warning(f"[ACO] checkOrderStatus failed for order_id={internal_order_id}: {e}")
            return {}

    async def _fetch_invoice_url_once(self, attempt: int) -> str:
        try:
            ir = await self.session.get(
                f"{AUDI_BASE}/checkout/onepage/taxinvoices",
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": f"{AUDI_BASE}/checkout/onepage/success",
                },
            )
        except Exception as e:
            logger.warning(f"[ACO] taxinvoices poll error (attempt {attempt}): {e}")
            return ""
        if ir.status_code != 200:
            return ""
        html_frag = (ir.json() or {}).get("html") or ""
        m = INVOICE_URL_RE.search(html_frag)
        return m.group(0) if m else ""


# ------------------------------------------------------------------
# Module-level Stripe HTTP helpers.
# Each raises on infrastructure errors so the dispatcher falls back to
# Playwright. Card-decision responses (4xx with error body) are returned
# as normal JSON for the caller to interpret.
# ------------------------------------------------------------------
def _build_stripe_confirm_body(client_secret: str, cardholder: str, card: dict) -> dict:
    """Mirrors the manual-checkout HAR. Stripe escalates to 3DS more aggressively
    when these attribution markers are missing, so we send everything except
    radar_options[hcaptcha_token] (server-issued from a real hCaptcha challenge,
    can't fake). client_attribution_metadata appears at both nested and top level."""
    client_session_id = str(uuid.uuid4())
    wallet_config_id = str(uuid.uuid4())
    cam = {
        "client_session_id": client_session_id,
        "merchant_integration_source": "elements",
        "merchant_integration_subtype": "card-element",
        "merchant_integration_version": "2017",
        "wallet_config_id": wallet_config_id,
    }
    body = {
        "payment_method_data[type]": "card",
        "payment_method_data[billing_details][name]": cardholder,
        "payment_method_data[card][number]": card["number"],
        "payment_method_data[card][cvc]": card["cvc"],
        "payment_method_data[card][exp_month]": card["exp_month"],
        "payment_method_data[card][exp_year]": card["exp_year"],
        "payment_method_data[guid]": _stripe_session_id(),
        "payment_method_data[muid]": _stripe_session_id(),
        "payment_method_data[sid]": _stripe_session_id(),
        "payment_method_data[pasted_fields]": "number",
        "payment_method_data[payment_user_agent]": STRIPE_JS_VERSION,
        "payment_method_data[referrer]": AUDI_BASE,
        "payment_method_data[time_on_page]": "30000",
        "expected_payment_method_type": "card",
        "use_stripe_sdk": "true",
        "key": STRIPE_PK,
        "client_secret": client_secret,
    }
    for k, v in cam.items():
        body[f"payment_method_data[client_attribution_metadata][{k}]"] = v
        body[f"client_attribution_metadata[{k}]"] = v
    return body


async def _stripe_confirm(pi_id: str, client_secret: str, cardholder: str, card: dict) -> dict:
    body = _build_stripe_confirm_body(client_secret, cardholder, card)
    async with AsyncSession(impersonate="chrome120") as s:
        r = await s.post(
            f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm",
            data=urlencode(body),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            },
            timeout=20,
        )
    return r.json()


async def _stripe_get_pi(pi_id: str, client_secret: str) -> dict:
    """Single GET of a PaymentIntent. Used to recover after a transient
    confirm failure: if Stripe's server-side state is already terminal,
    don't issue a second confirm (which would fail with
    payment_intent_unexpected_state and orphan the user's auth hold)."""
    async with AsyncSession(impersonate="chrome120") as s:
        r = await s.get(
            f"https://api.stripe.com/v1/payment_intents/{pi_id}",
            params={"key": STRIPE_PK, "client_secret": client_secret},
            headers={
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            },
            timeout=10,
        )
    return r.json() or {}


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
    terminal = {*STRIPE_STATUS_TERMINAL_OK, "canceled", "requires_payment_method"}
    start = time.monotonic()
    async with AsyncSession(impersonate="chrome120") as s:
        last_status = None
        while time.monotonic() - start < timeout_s:
            r = await s.get(
                f"https://api.stripe.com/v1/payment_intents/{pi_id}",
                params={"key": STRIPE_PK, "client_secret": client_secret},
                timeout=10,
            )
            data = r.json()
            status = data.get("status")
            if status != last_status:
                logger.info(f"[ACO] poll t={int(time.monotonic()-start)}s status={status}")
                last_status = status
            if status in terminal:
                return data
            await asyncio.sleep(3)
    raise TimeoutError(f"Poll timed out after {timeout_s}s, last status={last_status}")
