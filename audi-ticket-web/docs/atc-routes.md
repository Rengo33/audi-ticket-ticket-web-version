# Add-to-cart routes and speed (findings 2026-11-05)

Measured from the production server against 346054 (FC Bayern – 1. FC Köln,
Ingolstadt) while it was on sale. Every test cart held 1 ticket and was
released afterwards, or expired after the shop's 20-minute reservation.

## Release timeline of 346054 (5 Nov 2026, UTC)

| Time | Event |
|---|---|
| 15 Oct | Product created, image uploaded. Visible only to the booking widget. |
| 08:34:15–25 | Product API (`shopping-experience-api…/products/346054`) flips 404 → 200 with `manufacturerSku T-AU43-373632`. Stock still 0. |
| 08:36:09–19 | Sale opens: stock 0 → 280. Our 10 s watcher saw it on scan #12. |
| 08:36:20–22 | Tasks 5–7 each carted 3 tickets (≈3 s incl. the cart check). |

So the product turns visible about 2 minutes before stock opens. Stock drained
280 → 168 in 17 minutes.

## Latency per hop (median, from the server)

| Step | Bypass (shop host pinned to origin) | Cloudflare | regiondo.net |
|---|---|---|---|
| Availability (`catalog_ajax/dates`), fresh connection | 397 ms | 444 ms | — |
| Availability, reused connection | 402 ms | 417 ms, 1×403 in 10 | — |
| Option lookup (`catalog_ajax/options`) | 378 ms | 358 ms | — |
| `ajaxadd`, refused (qty 999) | 338 ms | 351 ms | 250 ms |
| `ajaxadd`, real add (1 ticket) | — | — | 519–759 ms |

- Shop processing (~350–400 ms) dominates; TLS setup adds almost nothing.
- Bypass handled 40 availability calls at 4/s without a single error. Cloudflare
  already 403s at a slow pace.
- Bypass needs the current origin IPs: they rotate with regiondo.net's AWS load
  balancer, so `shop_origin_ips()` resolves regiondo.net via DNS.

## Facts that matter for speed

- Option IDs are the same with and without `date`/`time` in the options call
  (824388 → 2321611/2321612, 824389 → 2321613/2321614, 824390 → 2321615/2321616).
  Without date/time it answers before the sale, so it can be looked up ahead of time.
- `ajaxadd` is a stock oracle: `Die gewünschte Menge ist nicht verfügbar.` means
  the payload is right and stock is missing; `Invalid option selected` means wrong
  data. A refused add reserves nothing (`qtm_quote_item_ids: null`).
- Hot path today: wait for the next 10 s scan (avg 5 s) → 3 DB log commits →
  option lookup (~0.4 s) → `ajaxadd` (~0.35 s, this holds the tickets) → cart
  check on the checkout page (~1–2 s, only delays the "secured" message).

## Other cart routes checked

### shopping-experience API — no cart

The public OpenAPI spec (`/api-json`, v1.0.12) has products, locations, regions,
reviews and `POST /api/order`. `POST /api/order` takes `{orderNumber}` and
returns order info. It is an order lookup, not an add-to-cart. Its response schema has contact data
(name, email, phone) and tickets with a `url` field. Live it answers 500 for
every input, including our real order 501801672745, the internal order id, the
invoice number and an empty body; partner code 30797 gets 403. Not usable.

### Regiondo booking widget (widgets.regiondo.net) — same endpoint

The new booking widget's bundle builds its cart URLs from the shop base URL:
`checkout/ajaxcart/ajaxadd`, `updatePost`, `delete`, `cleancart`, then
`checkoutsimple/onepage`. It uses the same Magento endpoints as we do; there is
no separate cart backend.

### regiondo.net — carts, but in a different shop

- `POST https://regiondo.net/checkout/ajaxcart/ajaxadd/product/346054` works:
  no Cloudflare, no IP pinning, ~250 ms refused / ~520–760 ms real add.
- It sets `frontend` for `domain=.regiondo.de`, which a client on regiondo.net
  drops, so the cookie has to be read from `Set-Cookie` and sent by hand.
- The cart lands in Regiondo's marketplace store (`store-default`). The Audi shop
  (`audidefuehrungen2…`, `store-wl-de`) does not see it with the same cookie.
  Adding `___store=wl_de`, `wl` or `audidefuehrungen2` did not change that
  (`wl_de` points the checkout at `shop.regiondo.de`, whose cart is also empty).
  Using the Audi shop's own session cookie on regiondo.net did not help either.
- It holds real stock: carting 3 via regiondo.net dropped the Audi shop's
  `qty_available` 138 → 135 (three reads each), releasing the cart put it back to
  138. One shared stock pool, so a regiondo.net cart takes tickets away from Audi
  shop buyers like any other cart. A 5-ticket add was refused (`success: false`,
  no message); 3 passed, so a per-order cap sits somewhere between 3 and 4.
- That cart can still be checked out on regiondo.net and www.regiondo.de: the
  address step renders with the same Audi fields (Stammnummer, Berechtigte
  Gesellschaft, FC Bayern App E-Mail Account) and the cryozonic Stripe payment.
  It is branded "Regiondo.de: Zur Kasse" with Regiondo's AGB, and the form posts
  to `www.regiondo.de/checkoutsimple/threestep/posteditaddress`, which is behind
  Cloudflare.

### regiondo.net — full checkout VERIFIED (2026-11-06)

Placed a complete order through the regiondo.net channel on the free product
337874 ("Faszination Geschichte und Produktion für Neuwagenabholende", 0,00 €),
random identity + a catchall email. It reached Audi:

- Confirmation email, **Buchungsnummer 101804078317** (same 101… family as a real
  Audi booking, not a throwaway marketplace id).
- "Benachrichtigung an den Anbieter … gesendet. Dieser prüft nun, ob der …
  Termin verfügbar ist" — the order routes to Audi (the Anbieter) for
  confirmation. Free tours are request-style (manual provider confirm); paid
  game tickets confirm on stock instead.

The working flow, entirely on the regiondo.net host (no Cloudflare anywhere):

1. `POST regiondo.net/checkout/ajaxcart/ajaxadd/product/{pid}` → cart. Read
   `frontend` from Set-Cookie (client drops the `.regiondo.de` cookie on the
   regiondo.net host; send it back by hand on every later request).
2. `GET regiondo.net/checkoutsimple/onepage/` → `form_key` + fields. A free
   product's payment method is `invoice` (no Stripe/payone, no card).
3. `POST regiondo.net/checkoutsimple/threestep/posteditaddress` with buyer
   (firstname/lastname/email/email_confirm) + attendee custom fields + the
   waiver checkbox + `payment[method]=invoice`. For a free/invoice order this
   **places the order** and returns `step:success` with the success redirect;
   `saveorder` is not needed (and errors "Payment Method not available" because
   the order is already done).
4. `GET .../checkout/onepage/success` → confirmation + order id.

`posteditaddress` and the guest flow work on both `regiondo.net` and
`www.regiondo.de` from the server (no CF 403 on either). Guest-order
cancellation is disabled (`sales/guest/form` → 503 on both hosts); cancel via
the storno link in the confirmation email.

Bayern game checkout via regiondo.net (346054) renders the full Audi buyer set:
`buyer_field_20709` Stammnummer (required), `buyer_field_27285` Berechtigte
Gesellschaft, `buyer_field_29605` **FC Bayern App E-Mail Account** — same IDs as
the Audi host / the HAR, so `checkout.py`'s `fcb_app_email` handling applies
unchanged.

Still unproven: a **paid** marketplace-channel order (payone/Stripe + 3DS, not
`invoice`) and which invoice Audi then issues — needs a real paid test.

### Built: regiondo.net as an explicit, opt-in cart mode

`AudiTicketBot.add_to_cart_regiondo(...)` (core.py) carts via regiondo.net and
returns the `frontend` cookie scoped to `.regiondo.de`. It is a **separate mode**,
never an automatic fallback: a live switch `cart_via_regiondo`
(AppSettings + `set/cart_via_regiondo_enabled` in core.py, PUT /api/settings,
UI toggle on the Tasks page next to Bypass). When on, `_attempt_atc` carts
through regiondo.net and stores the cart with
`checkout_url=https://www.regiondo.de/checkout/cart`; when off, nothing changes.

Deferred (needs work / a paid test first):
- Mobile proxy (`api/checkout.py`) + server-side ACO are still Audi-host only;
  they don't yet drive the www.regiondo.de checkout for a regiondo-channel cart.
  ACO refuses regiondo carts (`run_checkout` guard) and the cookie endpoint
  returns the cart's own `checkout_url`, so checkout is manual via cookie copy.
- No checkout-page phantom re-check on the regiondo path; only the
  `qtm_quote_item_*` check, and only when the response carries those fields.

Gain over Bypass on the add itself is only ~90 ms, so regiondo.net is an
on-demand alternate route, not the default.

## Where the speed actually is

1. Poll stock non-stop (back to back, ~0.4 s) through Bypass in the window after
   a product turns visible: detection delay 0–10 s → 0–0.4 s.
2. Look up option IDs before the sale opens: −0.4 s on the hot path.
3. Fire `ajaxadd` before the DB logs and notifications.
4. Or, during the window, send `ajaxadd` directly every ~0.3 s and treat
   "nicht verfügbar" as "not yet": sale-open → tickets held in one ~0.35 s request.
   Costs many more POSTs per second.
