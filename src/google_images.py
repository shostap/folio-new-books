"""Cover-image lookup via the Google Books viewapi (free, no API key required)."""

import json
import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GOOGLE_BOOKS_URL = "https://books.google.com/books"


def fetch_cover_image(
    isbn: Optional[str],
    oclc: Optional[str] = None,
    config=None,
) -> Optional[str]:
    """
    Return a thumbnail URL from the Google Books viewapi, or None if not found.

    Tries ISBN first, then OCLC number if provided.
    The Google Books viewapi is free and requires no API key.
    Pass config to allow disabling via [google] enabled = false in config.ini.
    """
    if config is not None and not config.google_enabled:
        return None

    if isbn:
        result = _google_books_lookup("ISBN", isbn)
        if result:
            return result

    if oclc:
        result = _google_books_lookup("OCLC", oclc)
        if result:
            return result

    return None


def _google_books_lookup(key_type: str, key_value: str) -> Optional[str]:
    """
    Query the Google Books viewapi for a cover thumbnail.

    Args:
        key_type:  "ISBN" or "OCLC"
        key_value: The identifier value (hyphens/spaces are stripped for ISBN;
                   non-digits are stripped for OCLC).

    Returns:
        thumbnail_url string, or None if the book has no cover in Google Books.
    """
    if key_type == "OCLC":
        clean_value = re.sub(r"[^0-9]", "", str(key_value))
    else:
        clean_value = key_value.replace("-", "").replace(" ", "")

    if not clean_value:
        return None

    bibkey = f"{key_type}:{clean_value}"
    params = {"jscmd": "viewapi", "bibkeys": bibkey}

    try:
        resp = requests.get(GOOGLE_BOOKS_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = _parse_google_books_response(resp.text)
        book = data.get(bibkey, {})
        return book.get("thumbnail_url") or None
    except requests.RequestException as exc:
        logger.warning("Google Books lookup failed for %s: %s", bibkey, exc)
    except (ValueError, KeyError) as exc:
        logger.debug("Google Books response parse error for %s: %s", bibkey, exc)

    return None


def _parse_google_books_response(text: str) -> dict:
    """
    Parse the Google Books viewapi JSONP-style response.

    The API returns JavaScript like:
        var _GBSBookInfo = {"ISBN:...": {...}};

    We strip the variable-assignment wrapper and parse the inner JSON object.
    An empty response (no book found) returns "{}".
    """
    text = text.strip()
    # Remove: var _GBSBookInfo = {...}; — strip up to the first '{'
    text = re.sub(r"^var\s+\w+\s*=\s*", "", text)
    text = text.rstrip(";").strip()

    if not text or text == "{}":
        return {}

    return json.loads(text)
