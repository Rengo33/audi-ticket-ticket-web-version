"""Scan Regiondo product IDs through the booking-widget route and record Audi products.

/bookingwidget/vendor/30797/id/{ID} returns a page with "<title>{Name} bei Regiondo.de" and
a dataLayer "'brand': '{Vendor}'" for every existing product, published or not. IDs are one global counter across all
Regiondo shops, so we walk a range and keep only vendor "AUDI AG".

Polite by design: max RATE requests/s across WORKERS threads, stops on 403/429 or
repeated errors, resumable (skips IDs already in the output file).

Usage:  python3 tools/scan_audi_ids.py 346203 295000 [out.csv]
"""
import csv, os, re, sys, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "https://audidefuehrungen2.regiondo.de/bookingwidget/vendor/30797/id/{}"
RATE, WORKERS, MAX_ERRORS = 100, 10, 20
TITLE = re.compile(r"<title>\s*(.*?)\s*bei Regiondo", re.S)
BRAND = re.compile(r"'brand':\s*'([^']*)'")

lock, stop = threading.Lock(), threading.Event()
next_slot, errors = [time.monotonic()], [0]


def throttle():
    # ponytail: one global token slot, fine for a few req/s
    with lock:
        now = time.monotonic()
        wait = max(0.0, next_slot[0] - now)
        next_slot[0] = max(now, next_slot[0]) + 1.0 / RATE
    time.sleep(wait)


def fetch(pid):
    if stop.is_set():
        return None
    throttle()
    req = urllib.request.Request(URL.format(pid), headers={"User-Agent": "Mozilla/5.0"})
    try:
        body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return pid, 404, "", ""
        if e.code in (403, 429):
            print(f"\n{e.code} at id {pid}, stopping — shop is rate-limiting us", flush=True)
            stop.set()
            return None
        body = None
    except Exception:
        body = None
    if body is None:
        with lock:
            errors[0] += 1
            if errors[0] >= MAX_ERRORS:
                print(f"\n{MAX_ERRORS} errors, stopping", flush=True)
                stop.set()
        return None
    t, b = TITLE.search(body), BRAND.search(body)
    return pid, 200, (b.group(1) if b else ""), (t.group(1) if t else "")


def main():
    hi, lo = int(sys.argv[1]), int(sys.argv[2])
    out = sys.argv[3] if len(sys.argv) > 3 else "audi_ids.csv"
    done = set()
    if os.path.exists(out):
        with open(out) as f:
            done = {int(r["id"]) for r in csv.DictReader(f)}
    todo = [i for i in range(hi, lo - 1, -1) if i not in done]
    new_file = not os.path.exists(out)
    print(f"{len(todo)} IDs to scan, ~{len(todo) / RATE / 3600:.1f} h at {RATE}/s", flush=True)
    with open(out, "a", newline="") as f, ThreadPoolExecutor(WORKERS) as pool:
        w = csv.writer(f)
        if new_file:
            w.writerow(["id", "status", "vendor", "name"])
        for n, res in enumerate(pool.map(fetch, todo), 1):
            if res is None:
                continue
            pid, st, vendor, name = res
            # every ID is recorded (keeps resume exact); Audi rows are printed
            w.writerow([pid, st, vendor, name])
            if "AUDI" in vendor.upper():
                print(f"AUDI {pid}: {name}", flush=True)
            if n % 500 == 0:
                f.flush()
                print(f"... {n}/{len(todo)} (at id {pid})", flush=True)


if __name__ == "__main__":
    main()
