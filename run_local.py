"""
CLI runner – allows local testing without Apify infrastructure.

Usage examples:
    python run_local.py --query "restaurant" --location "Bali, Indonesia"
    python run_local.py --query "hotel" --location "Tokyo, Japan" --max 50
    python run_local.py --query "travel agent" --location "Singapore" --proxies proxies.txt
    python run_local.py --query "cafe" --location "London, UK" --visible
"""

from utils import setup_logging
from scraper import GoogleMapsScraper, load_proxies
import argparse
import asyncio
import csv
import json
import logging
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


COLUMNS = [
    "place_id",
    "name",
    "category",
    "phone",
    "website",
    "rating",
    "review_count",
    "address",
    "city",
    "state",
    "postal_code",
    "country",
    "latitude",
    "longitude",
    "opening_hours",
    "price_range",
    "permanently_closed",
    "plus_code",
    "google_maps_url",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Google Maps Leads Scraper – local runner"
    )
    parser.add_argument(
        "--query", "-q",
        required=True,
        help='Search keyword, e.g. "restaurant" or "travel agent"',
    )
    parser.add_argument(
        "--location", "-l",
        required=True,
        help='Location string, e.g. "Bali, Indonesia" or "New York, USA"',
    )
    parser.add_argument(
        "--max", "-m",
        type=int,
        default=50,
        help="Maximum number of results to scrape (default: 50)",
    )
    parser.add_argument(
        "--output", "-o",
        default="",
        help=(
            "Base output filename (without extension). "
            "Both .csv and .json are always saved. "
            "Default: auto-generated from query + location + timestamp, "
            "e.g. restaurant_bali-indonesia_20260306_072130"
        ),
    )
    parser.add_argument(
        "--proxies", "-p",
        default="proxies.txt",
        help="Path to proxies.txt file – one proxy URL per line (default: proxies.txt)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )
    parser.add_argument(
        "--visible",
        dest="headless",
        action="store_false",
        help="Run browser in visible (non-headless) mode for debugging",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    # ── Load proxies ─────────────────────────────────────────────────────────
    proxy_list = load_proxies(args.proxies)

    scraper = GoogleMapsScraper(
        max_results=args.max,
        headless=args.headless,
        proxy_list=proxy_list,
    )

    # ── Derive output paths ───────────────────────────────────────────────────
    if args.output:
        # User supplied a name – strip any extension and use as base
        base = re.sub(r"\.(csv|json)$", "", args.output, flags=re.IGNORECASE)
    else:
        # Auto-generate: <query>_<location>_<YYYYMMDD_HHMMSS>
        safe_query = re.sub(r"[^\w]+", "-", args.query.lower()).strip("-")
        safe_location = re.sub(
            r"[^\w]+", "-", args.location.lower()).strip("-")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{safe_query}_{safe_location}_{timestamp}"

    csv_path = base + ".csv"
    json_path = base + ".json"

    print(f"\n{'='*60}")
    print(f"  Query    : {args.query}")
    print(f"  Location : {args.location}")
    print(f"  Max      : {args.max}")
    print(
        f"  Proxies  : {len(proxy_list)} loaded" if proxy_list else "  Proxies  : none")
    print(f"  CSV out  : {csv_path}")
    print(f"  JSON out : {json_path}")
    print(f"{'='*60}\n")

    leads = await scraper.scrape(query=args.query, location=args.location)
    records = [lead.to_dict() for lead in leads]

    # ── CSV export ──────────────────────────────────────────────────────────
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    print(f"[✓] CSV  saved → {csv_path}  ({len(records)} rows)")

    # ── JSON export ─────────────────────────────────────────────────────────
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    print(f"[✓] JSON saved → {json_path}  ({len(records)} records)")

    print(f"\n[✓] Done – {len(records)} leads scraped.\n")


if __name__ == "__main__":
    setup_logging(logging.INFO)
    asyncio.run(run(parse_args()))
