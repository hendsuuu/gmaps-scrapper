"""
Shared utility helpers.
"""

import logging
import re
import unicodedata
from typing import Generator, TypeVar

T = TypeVar("T")


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with a sensible format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Suppress noisy third-party loggers
    for noisy in ("urllib3", "asyncio", "playwright", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def sanitise_text(text: str) -> str:
    """Normalise unicode, strip control characters, collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    # Remove control characters except newlines/tabs
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse multi-spaces
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def chunk_list(lst: list[T], size: int) -> Generator[list[T], None, None]:
    """Yield successive *size*-sized chunks from *lst*."""
    for i in range(0, len(lst), size):
        yield lst[i: i + size]


def flatten_dict(d: dict, parent_key: str = "", sep: str = "_") -> dict:
    """Recursively flatten a nested dict."""
    items: list = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
