"""
CLI runner for local scraping without the web frontend.
"""

from pathlib import Path
import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from exporters import build_base_name, build_output_paths, save_records
from scraper import GoogleMapsScraper, load_proxies
from utils import sanitise_text, setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Google Maps Leads Scraper - local runner"
    )
    parser.add_argument("--query", "-q", required=True, help="Search keyword")
    parser.add_argument("--location", "-l", required=True, help="Location to search")
    parser.add_argument(
        "--max",
        "-m",
        type=int,
        default=50,
        help="Maximum number of results to scrape (default: 50)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="",
        help=(
            "Base output filename (without extension). "
            "Both .csv and .json are always saved into data/excel and data/json."
        ),
    )
    parser.add_argument(
        "--proxies",
        "-p",
        default="proxies.txt",
        help="Path to proxies.txt file (default: proxies.txt)",
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
        help="Run browser in visible mode for debugging",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    project_root = Path(__file__).resolve().parent
    proxy_list = load_proxies(str(project_root / args.proxies))

    scraper = GoogleMapsScraper(
        max_results=args.max,
        headless=args.headless,
        proxy_list=proxy_list,
    )

    base_name = Path(args.output).stem if args.output else build_base_name(
        args.query,
        args.location,
    )
    csv_path, json_path = build_output_paths(base_name, project_root)

    print(f"\n{'=' * 60}")
    print(f"  Query    : {args.query}")
    print(f"  Location : {args.location}")
    print(f"  Max      : {args.max}")
    print(
        f"  Proxies  : {len(proxy_list)} loaded" if proxy_list else "  Proxies  : none"
    )
    print(f"  CSV out  : {csv_path}")
    print(f"  JSON out : {json_path}")
    print(f"{'=' * 60}\n")

    leads = await scraper.scrape(query=args.query, location=args.location)
    records: list[dict] = []
    for lead in leads:
        record = lead.to_dict()
        record["search_query"] = args.query
        record["search_location"] = args.location
        record["name"] = sanitise_text(record.get("name", ""))
        record["address"] = sanitise_text(record.get("address", ""))
        records.append(record)

    saved_files = save_records(records, base_name, project_root)

    print(f"[OK] CSV  saved -> {saved_files['csv_file']}  ({len(records)} rows)")
    print(f"[OK] JSON saved -> {saved_files['json_file']}  ({len(records)} records)")
    print(f"\n[OK] Done - {len(records)} leads scraped.\n")


if __name__ == "__main__":
    setup_logging(logging.INFO)
    asyncio.run(run(parse_args()))
