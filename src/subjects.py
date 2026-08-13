"""
Subject-heading classification.

Two grouping mechanisms are exposed:

  1. Keyword classification (classify_subject) — matches an item's FOLIO
     subjects against a user-defined map of group → keywords.  Curated.

  2. LCC-class lookup (lcc_class_from_call_number) — derives a high-level
     subject area from the item's call number using a longest-prefix match
     against the LCC class map shipped at static/lcc-classes.json.  Automatic.

generate.py uses these in combination: manual groups first, LCC as a
fallback when the manual groups don't match.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_UNGROUPED_LABEL = "Other"


def classify_subject(
    subjects: list,
    subject_groups: dict[str, list[str]],
) -> Optional[str]:
    """
    Return the first matching subject-group name for an item, or None.

    Args:
        subjects:       Instance.subjects array from FOLIO. Items may be either
                        plain strings or dicts shaped like {"value": "Engineering"}.
        subject_groups: Map of group name → list of lowercase keywords.

    Returns:
        Group name string, or None if there's no match (or no groups configured).
    """
    if not subjects or not subject_groups:
        return None

    haystack = _flatten_subjects(subjects)
    if not haystack:
        return None

    for group_name, keywords in subject_groups.items():
        for keyword in keywords:
            kw = keyword.strip().lower()
            if kw and kw in haystack:
                return group_name

    return None


def parse_groups_config(raw: dict[str, str]) -> dict[str, list[str]]:
    """
    Convert a [subject_groups] config section into a normalized dict.

    Each value is a comma-separated keyword list; whitespace and empty
    entries are stripped.

    Example input:  {"Engineering": "computer, programming, physics"}
    Example output: {"Engineering": ["computer", "programming", "physics"]}
    """
    parsed: dict[str, list[str]] = {}
    for name, value in raw.items():
        keywords = [k.strip().lower() for k in value.split(",")]
        keywords = [k for k in keywords if k]
        if name and keywords:
            parsed[name] = keywords
    return parsed


def ungrouped_label() -> str:
    """Label used in the UI for items that match no subject group."""
    return _UNGROUPED_LABEL


# ─────────────────────────────────────────────────────────────────────
# Library of Congress Classification (LCC) lookup.
# The class map lives in static/lcc-classes.json so it can be audited
# and extended without code changes.  Loaded once and cached.
# ─────────────────────────────────────────────────────────────────────

_LCC_JSON_PATH = Path(__file__).parent.parent / "static" / "lcc-classes.json"
_LCC_SUBJECTS_PATH = Path(__file__).parent.parent / "static" / "lcc-subjects.json"
_LCC_MAP_CACHE: Optional[dict] = None
_LCC_SUBJECTS_CACHE: Optional[dict] = None
# Max alpha-prefix length to consider when matching (most LCC subclasses
# are 1-3 letters; a few use 4 but they're rare and not in our map).
_MAX_PREFIX_LEN = 3
# Call number must look like an LCC shelfmark: 1-3 letters + a digit.
# Rejects "Online", "Internet", "[On order]", etc.
_LCC_PATTERN = re.compile(r"^([A-Z]{1,3})\s*\d")
# Format-only "subjects" that shouldn't drive topical classification
_FORMAT_MARKERS = {
    "electronic books", "e-books", "ebooks",
    "online resources", "online publications",
    "audiobooks", "videodiscs", "dvd-roms", "cd-roms",
    "digital books", "streaming video",
}


def load_lcc_map() -> dict:
    """
    Load the LCC class map from static/lcc-classes.json (cached).

    Returns an empty dict on read error.  Comment keys starting with "_"
    are filtered out so they cannot accidentally shadow a real prefix.
    """
    global _LCC_MAP_CACHE
    if _LCC_MAP_CACHE is not None:
        return _LCC_MAP_CACHE
    try:
        with _LCC_JSON_PATH.open(encoding="utf-8") as f:
            raw = json.load(f)
        _LCC_MAP_CACHE = {
            k.upper(): v
            for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, str)
        }
    except (OSError, ValueError) as exc:
        logger.warning("Could not load LCC class map from %s: %s", _LCC_JSON_PATH, exc)
        _LCC_MAP_CACHE = {}
    return _LCC_MAP_CACHE


def load_lcc_subjects_map() -> dict:
    """
    Load the subject-keyword → LCC prefix map (cached).
    Comment / metadata keys starting with "_" are filtered out.
    """
    global _LCC_SUBJECTS_CACHE
    if _LCC_SUBJECTS_CACHE is not None:
        return _LCC_SUBJECTS_CACHE
    try:
        with _LCC_SUBJECTS_PATH.open(encoding="utf-8") as f:
            raw = json.load(f)
        _LCC_SUBJECTS_CACHE = {
            k.lower(): v
            for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, str)
        }
    except (OSError, ValueError) as exc:
        logger.warning("Could not load LCC subject map from %s: %s", _LCC_SUBJECTS_PATH, exc)
        _LCC_SUBJECTS_CACHE = {}
    return _LCC_SUBJECTS_CACHE


def _reset_lcc_cache_for_tests() -> None:
    """Test helper — forces the next load_*_map() call to re-read from disk."""
    global _LCC_MAP_CACHE, _LCC_SUBJECTS_CACHE
    _LCC_MAP_CACHE = None
    _LCC_SUBJECTS_CACHE = None


def _label_for_prefix(prefix: str) -> Optional[str]:
    """Look up an LCC prefix in the class map, shrinking until we hit."""
    lcc_map = load_lcc_map()
    while prefix:
        label = lcc_map.get(prefix)
        if label:
            return label
        prefix = prefix[:-1]
    return None


def lcc_class_from_call_number(call_number: str) -> Optional[str]:
    """
    Map a call number to its LCC class label via longest-prefix lookup.

    Requires the call number to LOOK like LCC: 1-3 letters followed by a
    digit.  This rejects "Online" / "Internet" / "[On order]" placeholders
    that happen to start with letters but carry no classification value.

    Returns None when the call number is empty, non-LCC-shaped, or when
    no class in the map matches the prefix (e.g. unassigned letters).
    """
    if not call_number:
        return None
    cn = call_number.strip().upper()
    match = _LCC_PATTERN.match(cn)
    if not match:
        return None
    return _label_for_prefix(match.group(1))


def lcc_class_from_subjects(subjects: list) -> Optional[str]:
    """
    Derive an LCC class label from subject heading text.

    Used as a fallback when an item has no usable LCC call number (new
    arrivals not yet in EDS, ebooks with "Online" as call number).

    Strategy, per subject in order:
      1. Skip format markers ("Electronic books", "Audiobooks", ...)
      2. Strip LCSH "--" subdivisions and BISAC " / " subdivisions
      3. Try exact match on the main heading
      4. Try multi-word phrases within the main heading (longest first)
      5. Try single words left-to-right

    The first match wins across all subjects; the resolved prefix is
    looked up in the LCC class map for the display label.
    """
    if not subjects:
        return None

    subject_map = load_lcc_subjects_map()
    if not subject_map:
        return None

    for entry in subjects:
        if isinstance(entry, dict):
            text = entry.get("value") or entry.get("subject") or ""
        else:
            text = str(entry)
        text = text.strip().lower()
        if not text or text in _FORMAT_MARKERS:
            continue

        # Strip LCSH "--" or BISAC " / " subdivisions to get the main heading
        main = re.split(r"\s*--\s*|\s+/\s+", text, maxsplit=1)[0].strip()
        if not main:
            continue

        # 1. Exact match
        if main in subject_map:
            label = _label_for_prefix(subject_map[main])
            if label:
                return label

        # 2. Multi-word phrases, longest first (max 3 words)
        words = re.findall(r"[a-z]+(?:'[a-z]+)?", main)
        for n in range(min(len(words), 3), 1, -1):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i : i + n])
                if phrase in subject_map:
                    label = _label_for_prefix(subject_map[phrase])
                    if label:
                        return label

        # 3. Single words in order
        for word in words:
            if word in subject_map:
                label = _label_for_prefix(subject_map[word])
                if label:
                    return label

    return None


def normalize_subjects(subjects: list) -> list[str]:
    """
    Flatten a FOLIO subjects array into a plain list of strings.

    Handles both shapes mod-search may return:
      - ["Subject A", "Subject B"]
      - [{"value": "Subject A"}, {"value": "Subject B"}]
    """
    out: list[str] = []
    for entry in subjects or []:
        if isinstance(entry, str):
            text = entry.strip()
        elif isinstance(entry, dict):
            text = (entry.get("value") or entry.get("subject") or "").strip()
        else:
            continue
        if text:
            out.append(text)
    return out


def _flatten_subjects(subjects: list) -> str:
    """
    Concatenate all subject strings into a single lowercase blob for matching.

    Handles both flat string lists and the FOLIO mod-search shape where each
    subject is wrapped in a dict with a "value" field.
    """
    parts: list[str] = []
    for entry in subjects:
        if isinstance(entry, str):
            parts.append(entry)
        elif isinstance(entry, dict):
            val = entry.get("value") or entry.get("subject") or ""
            if val:
                parts.append(val)
    blob = " | ".join(parts).lower()
    # Collapse punctuation so " -- " subdivisions match as plain text
    return re.sub(r"[^\w\s]", " ", blob)
