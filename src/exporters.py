"""
Shared helpers for naming and saving scrape results.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import json
import re


EXPORT_COLUMNS = [
    "place_id",
    "name",
    "category",
    "phone",
    "email",
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
    "search_query",
    "search_location",
]


def slugify(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^\w]+", "-", value.lower()).strip("-")
    return cleaned or fallback


def build_base_name(query: str, location: str, timestamp: datetime | None = None) -> str:
    timestamp = timestamp or datetime.now()
    safe_query = slugify(query, "query")
    safe_location = slugify(location, "location")
    return f"{safe_query}_{safe_location}_{timestamp.strftime('%Y%m%d_%H%M%S')}"


def ensure_output_dirs(project_root: Path | None = None) -> tuple[Path, Path]:
    root = project_root or Path(__file__).resolve().parents[1]
    csv_dir = root / "data" / "excel"
    json_dir = root / "data" / "json"
    csv_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)
    return csv_dir, json_dir


def build_output_paths(
    base_name: str,
    project_root: Path | None = None,
) -> tuple[Path, Path]:
    csv_dir, json_dir = ensure_output_dirs(project_root)
    return csv_dir / f"{base_name}.csv", json_dir / f"{base_name}.json"


def save_records(
    records: list[dict],
    base_name: str,
    project_root: Path | None = None,
) -> dict[str, str]:
    csv_path, json_path = build_output_paths(base_name, project_root)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=EXPORT_COLUMNS,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(records)

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(records, json_file, ensure_ascii=False, indent=2)

    return {
        "csv_file": str(csv_path),
        "json_file": str(json_path),
    }
