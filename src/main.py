"""
Apify Actor entry point for Google Maps Leads Scraper.
Handles input validation, orchestration, dataset storage,
and CSV + JSON export via Apify Key-Value Store.
"""

from utils import setup_logging, sanitise_text
from scraper import GoogleMapsScraper
import asyncio
import csv
import io
import json
import logging
import os
import sys

from apify import Actor

# Ensure src is importable when run via Apify
sys.path.insert(0, os.path.dirname(__file__))


logger = logging.getLogger(__name__)

# ── Default column order exported to Google Sheets / CSV ─────────────────────
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


async def main() -> None:
    setup_logging()

    async with Actor:
        actor_input = await Actor.get_input() or {}

        # ── Required inputs ────────────────────────────────────────────────────
        queries: list[str] = actor_input.get("queries", [])
        locations: list[str] = actor_input.get("locations", [])

        # Legacy single-value support
        if not queries and actor_input.get("query"):
            queries = [actor_input["query"]]
        if not locations and actor_input.get("location"):
            locations = [actor_input["location"]]

        if not queries:
            await Actor.fail(status_message="Input 'queries' is required (e.g. ['restaurant', 'hotel'])")
            return
        if not locations:
            await Actor.fail(status_message="Input 'locations' is required (e.g. ['Bali, Indonesia', 'New York'])")
            return

        # ── Optional inputs ────────────────────────────────────────────────────
        max_results_per_query: int = int(
            actor_input.get("maxResultsPerQuery", 100))
        headless: bool = bool(actor_input.get("headless", True))
        language: str = actor_input.get("language", "en")

        # ── Proxy list ─────────────────────────────────────────────────────────
        # Accept a list of proxy URLs directly from input (one URL per element)
        proxy_list: list[str] = actor_input.get("proxyList", [])
        if not proxy_list:
            # Fallback: try reading proxies.txt from the actor root
            proxies_path = os.path.join(
                os.path.dirname(__file__), "..", "proxies.txt")
            from scraper import load_proxies
            proxy_list = load_proxies(os.path.normpath(proxies_path))

        # ── Run scraper for every query × location combination ─────────────────
        scraper = GoogleMapsScraper(
            max_results=max_results_per_query,
            headless=headless,
            language=language,
            proxy_list=proxy_list,
        )

        dataset = await Actor.open_dataset()
        all_leads = []

        total_combinations = len(queries) * len(locations)
        done = 0

        for location in locations:
            for query in queries:
                done += 1
                logger.info(
                    "[%d/%d] Scraping query=%r in location=%r",
                    done, total_combinations, query, location,
                )
                await Actor.set_status_message(
                    f"[{done}/{total_combinations}] {query} – {location}"
                )

                try:
                    leads = await scraper.scrape(query=query, location=location)
                except Exception as exc:
                    logger.error("Scrape failed for %r in %r: %s",
                                 query, location, exc)
                    leads = []

                for lead in leads:
                    record = lead.to_dict()
                    record["search_query"] = query
                    record["search_location"] = location
                    record["name"] = sanitise_text(record.get("name", ""))
                    record["address"] = sanitise_text(
                        record.get("address", ""))
                    all_leads.append(record)
                    await dataset.push_data(record)

                logger.info("  → %d leads found", len(leads))

        logger.info("Total leads collected: %d", len(all_leads))

        export_cols = COLUMNS + ["search_query", "search_location"]

        # ── CSV export to Key-Value Store ──────────────────────────────────────
        logger.info("Saving CSV …")
        await Actor.set_status_message("Saving CSV …")
        try:
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf, fieldnames=export_cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_leads)
            kvs = await Actor.open_key_value_store()
            await kvs.set_value(
                "leads.csv",
                buf.getvalue(),
                content_type="text/csv; charset=utf-8",
            )
            logger.info("CSV saved to Key-Value Store as leads.csv")
        except Exception as exc:
            logger.error("CSV export failed: %s", exc)

        # ── JSON export to Key-Value Store ─────────────────────────────────────
        logger.info("Saving JSON …")
        try:
            kvs = await Actor.open_key_value_store()
            await kvs.set_value(
                "leads.json",
                json.dumps(all_leads, ensure_ascii=False, indent=2),
                content_type="application/json; charset=utf-8",
            )
            logger.info("JSON saved to Key-Value Store as leads.json")
        except Exception as exc:
            logger.error("JSON export failed: %s", exc)

        await Actor.set_status_message(
            f"Done! Collected {len(all_leads)} leads. Download CSV/JSON from Key-Value Store."
        )


if __name__ == "__main__":
    asyncio.run(main())
