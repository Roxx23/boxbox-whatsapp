"""One-off: fill shopify_orders.discount_codes for orders stored before the
column existed, from the Shopify Admin API (read-only on Shopify).

Writes only to the local SQLite DB: discount_codes (JSON list; [] when the
order used none), and Shopify's current financial_status and cancelled_at so
code revenue can leave out refunded/cancelled orders.

Idempotent: by default only orders whose discount_codes is still NULL are
fetched, so a re-run picks up where a failed run stopped. --all refetches
every order. Dry run unless --apply.

    cd /home/sayboxbox/boxbox-whatsapp
    venv/bin/python scripts/backfill_order_discount_codes.py            # dry run
    venv/bin/python scripts/backfill_order_discount_codes.py --apply

Run it after this change is deployed (app start adds the new columns).
Uses the app's Shopify auth helper (token renews itself). Never logs tokens.
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, '.env'))

from utils.database import Database  # noqa: E402
from utils.shopify_auth import shopify_request, is_configured  # noqa: E402

BATCH = 100  # ids per orders.json call (Shopify allows up to 250)


MAX_TRIES = 5


def fetch_batch(ids):
    """{order_id: {discount_codes, financial_status, cancelled_at}} for ids.
    Retries a 429 (rate limited) up to MAX_TRIES times with backoff."""
    for attempt in range(1, MAX_TRIES + 1):
        resp = shopify_request('GET', '/orders.json', params={
            'ids': ','.join(ids), 'status': 'any', 'limit': 250,
            'fields': 'id,discount_codes,financial_status,cancelled_at',
        }, timeout=30)
        if resp.status_code != 429:
            break
        if attempt == MAX_TRIES:
            raise RuntimeError(f"Shopify still rate-limiting after {MAX_TRIES} tries; re-run later (it resumes)")
        try:
            wait = float(resp.headers.get('Retry-After', 0))
        except ValueError:
            wait = 0
        time.sleep(max(wait, 2 ** attempt))
    if resp.status_code != 200:
        raise RuntimeError(f"Shopify orders.json HTTP {resp.status_code}: {resp.text[:200]}")
    return {str(o['id']): o for o in resp.json().get('orders', [])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true', help='write to the DB (default: dry run)')
    ap.add_argument('--all', action='store_true', help='refetch every order, not only missing ones')
    args = ap.parse_args()
    if not is_configured():
        sys.exit("Shopify is not configured (.env)")

    db = Database()
    ids = db.get_orders_missing_discount_codes(all_orders=args.all)
    print(f"{len(ids)} order(s) to fetch ({'apply' if args.apply else 'dry run'})")
    found = with_codes = missing = 0
    code_counts = {}
    for i in range(0, len(ids), BATCH):
        batch = ids[i:i + BATCH]
        got = fetch_batch(batch)
        for oid in batch:
            o = got.get(oid)
            if not o:
                missing += 1  # deleted in Shopify / not visible: left NULL
                continue
            found += 1
            codes = [d.get('code') for d in o.get('discount_codes') or [] if d.get('code')]
            if codes:
                with_codes += 1
                for c in codes:
                    code_counts[c.upper()] = code_counts.get(c.upper(), 0) + 1
            if args.apply:
                db.set_order_discount_info(oid, codes, o.get('financial_status'), o.get('cancelled_at'))
        print(f"  fetched {min(i + BATCH, len(ids))}/{len(ids)}")
        time.sleep(0.5)  # well under Shopify's REST rate limit
    print(f"found {found}, with codes {with_codes}, not returned by Shopify {missing}")
    top = sorted(code_counts.items(), key=lambda kv: -kv[1])[:15]
    print("most used codes:", json.dumps(top))
    if not args.apply:
        print("dry run: nothing written. Re-run with --apply to store.")


if __name__ == '__main__':
    main()
