"""
TMDB (The Movie Database) poster lookup.

Uses the /search/multi endpoint for title-based searches and applies the
same title-similarity ranking as the GraphQL reference implementation.
Results are filtered to movie and tv media types only.
"""

import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
TMDB_DEFAULT_POSTER_SIZE = "w500"

_MEDIA_TYPES = {"movie", "tv"}


def fetch_tmdb_poster(
    title: str,
    api_key: str,
    poster_size: str = TMDB_DEFAULT_POSTER_SIZE,
) -> Optional[str]:
    """
    Search TMDB for a title and return the best-matching poster URL.

    Applies title-similarity ranking (ported from the JS reference) to select
    the top result from /search/multi, then returns its poster image URL.

    Args:
        title:       The title to search for (e.g. from a FOLIO order line).
        api_key:     TMDB API key (v3 auth).
        poster_size: TMDB image size slug — w185, w342, w500, w780, original.

    Returns:
        Full poster URL string, or None if not found.
    """
    if not api_key or not title:
        return None

    results = _tmdb_multi_search(title, api_key)
    if not results:
        return None

    media_results = [r for r in results if r.get("media_type") in _MEDIA_TYPES]
    if not media_results:
        return None

    best = _best_match(title, media_results)
    if not best:
        return None

    poster_path = best.get("poster_path")
    if not poster_path:
        return None

    return f"{TMDB_IMAGE_BASE}/{poster_size}{poster_path}"


def _tmdb_multi_search(query: str, api_key: str) -> list[dict]:
    """Call /search/multi and return the raw results list."""
    url = f"{TMDB_BASE_URL}/search/multi"
    params = {"query": query, "api_key": api_key}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("results", [])
    except requests.RequestException as exc:
        logger.warning("TMDB search failed for '%s': %s", query, exc)
    return []


def _best_match(query: str, results: list[dict]) -> Optional[dict]:
    """
    Return the highest-scoring result using title similarity.

    Mirrors the JS reference calculateTitleSimilarity logic:
    - Check for an exact (case-insensitive) match first.
    - Otherwise sort by similarity score descending and return the top result
      if its score is above zero.
    """
    query_lower = query.lower()

    # Exact match takes priority
    for result in results:
        title = result.get("title") or result.get("name") or ""
        if title.lower() == query_lower:
            return result

    if not results:
        return None

    # Score remaining results and pick the best
    scored = sorted(
        results,
        key=lambda r: _title_similarity(query, r.get("title") or r.get("name") or ""),
        reverse=True,
    )
    best_result = scored[0]
    best_score = _title_similarity(query, best_result.get("title") or best_result.get("name") or "")

    return best_result if best_score > 0 else None


def _title_similarity(query: str, title: str) -> int:
    """
    Compute a similarity score (integer) between a search query and a title.

    Ported directly from the JavaScript reference implementation:
      - Normalise: lowercase + strip non-word characters (\\W).
      - Exact normalised match  → 100.
      - Query is substring of title → 75 minus the length difference.
      - Otherwise → 0.

    The score may be negative when the length difference exceeds 75; this
    preserves the reference behaviour and causes such results to sort last.
    """
    if not query or not title:
        return 0

    norm_query = re.sub(r"\W", "", query.lower())
    norm_title = re.sub(r"\W", "", title.lower())

    if norm_query == norm_title:
        return 100

    if norm_query in norm_title:
        length_diff = abs(len(norm_query) - len(norm_title))
        return 75 - length_diff

    return 0
