"""HTML5 output generation for FOLIO New Materials."""

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from src.subjects import (
    classify_subject,
    lcc_class_from_call_number,
    lcc_class_from_subjects,
    normalize_subjects,
    ungrouped_label,
)

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"
_STATIC_DIR = _PROJECT_ROOT / "static"

# Identifier type names that indicate an ISBN
_ISBN_TYPE_NAMES = {"isbn", "isbn-10", "isbn-13"}

# Key used internally to tag an order line with the material UUID we queried
# with.  Lets us filter reliably even when /orders does not echo back
# physical.materialType in the response payload.
_QUERIED_TYPE_KEY = "_queried_material_uuid"

# Used to pick LCC-shaped values when an instance has multiple classifications
# (Dewey + LCC + local).  Mirrors src.subjects._LCC_PATTERN.
_LCC_LOOKS_LIKE = re.compile(r"^[A-Z]{1,3}\s*\d")

# Curated palette for placeholder covers — picked for legibility on white text
# and reasonable colour-blind separation.  Items get a stable colour derived
# from their material-type UUID so the same format always looks the same.
_PLACEHOLDER_PALETTE = [
    "#2a5e8c",  # deep blue
    "#7d3f5d",  # plum
    "#3a6b50",  # forest
    "#8a5a2b",  # russet
    "#5a4b8a",  # indigo
    "#0f6e6e",  # teal
    "#8a4040",  # brick
    "#4a4a4a",  # graphite
]


def build_items(
    order_lines: list[dict],
    instances: dict[str, dict],
    material_types: dict[str, str],
    config,
    rtac_holdings: Optional[dict[str, list[dict]]] = None,
    locations_map: Optional[dict[str, str]] = None,
) -> list[dict]:
    """
    Merge order-line, mod-search instance, and (optional) edge-RTAC holdings
    data into a flat list of display items.

    Holdings source priority:
      1. RTAC (live data, library names, status, due dates)
      2. instance.items[] from mod-search (call numbers, location IDs)
      3. instance.holdings[] from mod-search (legacy)

    Args:
        order_lines:    Raw poLines records from the FOLIO orders API.
        instances:      Map of instance UUID → instance record from mod-search.
        material_types: UUID → label map from config (empty = all types).
        config:         Application config object.
        rtac_holdings:  Optional map of instance UUID → list of normalized
                        holding dicts (from edge_client.normalize_holdings).
        locations_map:  Optional map of location UUID → display name, used to
                        translate effectiveLocationId on the fallback path.

    Returns:
        List of item dicts ready for the JSON envelope and HTML template.
    """
    rtac_holdings = rtac_holdings or {}
    locations_map = locations_map or {}
    configured_groups = getattr(config, "subject_groups", {}) or {}
    lcc_on = getattr(config, "lcc_grouping", False)

    items = []
    for line in order_lines:
        instance_id = line.get("instanceId") or line.get("instanceid")
        if not instance_id:
            logger.debug("Skipping order line %s — no instanceId", line.get("id"))
            continue

        instance = instances.get(instance_id, {})

        # The cataloged classification call number (MARC 050) is the single
        # most reliable source — set the moment the record is created in
        # FOLIO, before items are shelved or EDS syncs the bib.
        classification_cn = _classification_call_number(instance)

        # Holdings priority: live RTAC data first, fallback from mod-search
        # items[] when RTAC has nothing for this instance.
        holdings = rtac_holdings.get(instance_id) or []
        if holdings:
            # RTAC holdings may have empty call_number on items still "In process"
            # — supplement with the cataloged classification so the display is
            # populated immediately, not the day after the EDS sync runs.
            if classification_cn:
                for h in holdings:
                    if not h.get("call_number"):
                        h["call_number"] = classification_cn
        else:
            holdings = build_fallback_holdings(instance, locations_map)

        raw_subjects = instance.get("subjects") or []

        type_uuid = _material_uuid_from_line(line)
        type_label = (
            material_types.get(type_uuid)
            or _infer_type_label(instance)
            or "Other"
        )

        call_number = _primary_call_number(holdings, line, instance)

        # Subject grouping is a three-stage pipeline:
        #   1. Manual keyword match against [subject_groups] keywords (curated)
        #   2. LCC class from the call number itself (works for cataloged items)
        #   3. LCC class derived from subject heading text (works for new
        #      arrivals not yet in EDS, ebooks with "Online" call numbers, and
        #      anything else where stage 2 misses)
        # First non-empty result wins; everything else is "Other".
        subject_group = ""
        manual_match = (
            classify_subject(raw_subjects, configured_groups)
            if configured_groups else None
        )
        if manual_match:
            subject_group = manual_match
        elif lcc_on:
            subject_group = (
                lcc_class_from_call_number(call_number)
                or lcc_class_from_subjects(raw_subjects)
                or ungrouped_label()
            )
        elif configured_groups:
            # Manual groups configured but neither matched nor LCC available
            subject_group = ungrouped_label()

        item = {
            "id": line.get("id", instance_id),
            "instance_id": instance_id,
            "title": instance.get("title") or line.get("titleOrPackage", "Unknown title"),
            "author": _primary_author(instance),
            "publisher": _publisher(instance),
            "year": _pub_year(instance),
            "receipt_date": _format_date(line.get("receiptDate", "")),
            "type_uuid": type_uuid,
            "type_label": type_label,
            "subject_group": subject_group,
            "subjects": normalize_subjects(raw_subjects),
            "call_number": call_number,
            "holdings": holdings,
            "cover_url": None,  # populated later by generate.py if images enabled
            "placeholder_color": _placeholder_color(type_uuid or type_label),
            "eds_url": _eds_url(
                instance_id,
                _isbn(instance),
                _oclc(instance),
                instance.get("title") or line.get("titleOrPackage", ""),
                config,
            ),
            "isbn": _isbn(instance),
            "oclc": _oclc(instance),
        }
        items.append(item)

    return items


def build_fallback_holdings(
    instance: dict,
    locations_map: dict[str, str],
) -> list[dict]:
    """
    Build display-shape holdings from a mod-search instance record.

    Used when RTAC is unavailable or returned no data.  Walks
    instance.items[] for call numbers and statuses, joins each item's
    effectiveLocationId against ``locations_map`` for the display name.

    Falls back to the cataloged classification number (MARC 050 from
    instance.classifications) when an item has no effectiveCallNumber yet
    — that's normal for "In process" items that have been received but
    not shelved.

    Returns a list of holding dicts matching the shape used by
    edge_client.normalize_holdings, so downstream rendering is identical
    regardless of source.
    """
    classification_cn = _classification_call_number(instance)
    out: list[dict] = []
    for item in instance.get("items") or []:
        cn_components = item.get("effectiveCallNumberComponents") or {}
        status = (item.get("status") or {}).get("name", "")
        loc_id = item.get("effectiveLocationId", "")
        call_number = cn_components.get("callNumber") or classification_cn
        out.append({
            "call_number":   call_number,
            "location":      locations_map.get(loc_id, ""),
            "location_code": "",
            "library":       "",
            "library_code":  "",
            "status":        status,
            "due_date":      "",
            "loan_type":     "",
            "barcode":       item.get("barcode", ""),
            "material_type": "",
        })
    return out


def _classification_call_number(instance: dict) -> str:
    """
    Return the most useful classification call number from instance.classifications.

    When a record has multiple classifications (typically Dewey + LCC + a
    local scheme), prefer the LCC-shaped value since that's what drives
    both the display and the LCC subject grouping.  Falls back to the
    first available classification when none look like LCC (Dewey-only
    catalogs, for instance).
    """
    numbers = [
        (c.get("classificationNumber") or "").strip()
        for c in (instance.get("classifications") or [])
    ]
    numbers = [n for n in numbers if n]
    if not numbers:
        return ""
    for n in numbers:
        if _LCC_LOOKS_LIKE.match(n.upper()):
            return n
    return numbers[0]


def generate_html(
    items: list[dict],
    material_types: dict[str, str],
    start_date: str,
    end_date: str,
    generated_at: str,
    config,
) -> str:
    """
    Render the HTML5 output from the Jinja2 template.

    Returns:
        Rendered HTML string.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,  # all templates are HTML; escape everything by default
    )
    template = env.get_template("new_materials.html.j2")

    # Build the set of types that actually appear in the item list
    seen_types: dict[str, str] = {}
    for item in items:
        uuid = item["type_uuid"]
        if uuid and uuid not in seen_types:
            seen_types[uuid] = item["type_label"]

    # If configured types were given, keep their order; otherwise sort by label
    if material_types:
        active_types = {
            uuid: label
            for uuid, label in material_types.items()
            if uuid in seen_types
        }
    else:
        active_types = dict(sorted(seen_types.items(), key=lambda kv: kv[1]))

    counts = {
        uuid: sum(1 for i in items if i["type_uuid"] == uuid)
        for uuid in active_types
    }

    # Subject groups that actually appear in the item list.
    # Items can carry either a manual group name (matched by keywords) or
    # an LCC class label (fallback).  Build the dropdown from what's there:
    #   - Manual groups first, in config order
    #   - LCC labels next, sorted by frequency
    #   - "Other" at the end if any items couldn't be classified
    configured_groups = getattr(config, "subject_groups", None) or {}
    lcc_on = getattr(config, "lcc_grouping", False)
    active_subject_groups: dict[str, int] = {}

    if configured_groups or lcc_on:
        # Count every distinct subject_group value present in items
        all_counts: dict[str, int] = {}
        for item in items:
            g = item.get("subject_group") or ""
            if not g:
                continue
            all_counts[g] = all_counts.get(g, 0) + 1

        # 1. Configured manual groups first, in config order (when present in data)
        for name in configured_groups:
            if name in all_counts:
                active_subject_groups[name] = all_counts.pop(name)

        # 2. Pop "Other" so it can be appended at the end
        other_count = all_counts.pop(ungrouped_label(), 0)

        # 3. Everything left over is an LCC label (or another unforeseen
        # group); sort by frequency, then alphabetical for stable order
        for name, gcount in sorted(all_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            active_subject_groups[name] = gcount

        # 4. "Other" at the end
        if other_count:
            active_subject_groups[ungrouped_label()] = other_count

    # Embed the items as a JSON string inside <script type="application/json">.
    # The escape pass below prevents an item's title/author from breaking
    # out of the script tag (XSS) — even though all string content is also
    # autoescaped when interpolated into the DOM by app.js.
    envelope = build_data_envelope(
        items=items,
        start_date=start_date,
        end_date=end_date,
        generated_at=generated_at,
        institution_name=config.institution_name,
    )
    items_json = _safe_json_for_html(envelope)

    return template.render(
        title=config.output_title,
        institution_name=config.institution_name,
        logo_url=config.institution_logo_url,
        primary_color=config.primary_color,
        accent_color=config.accent_color,
        start_date=start_date,
        end_date=end_date,
        generated_at=generated_at,
        items=items,
        items_json=items_json,
        active_types=active_types,
        counts=counts,
        subject_groups=active_subject_groups,
        subject_grouping_enabled=bool(active_subject_groups),
        ungrouped_label=ungrouped_label(),
        default_view=getattr(config, "default_view", "grid"),
        holdings_display=getattr(config, "holdings_display", "summary"),
        total_count=len(items),
    )


def build_data_envelope(
    items: list[dict],
    start_date: str,
    end_date: str,
    generated_at: str,
    institution_name: str,
) -> dict:
    """
    Build the JSON envelope that wraps the items array.

    The envelope adds machine-readable metadata so programmatic consumers
    (RSS bridges, dashboards, analytics) have context without parsing the HTML.
    """
    return {
        "generated_at":     generated_at,
        "date_range":       {"start": start_date, "end": end_date},
        "institution":      institution_name,
        "total_count":      len(items),
        "items":            items,
    }


def write_assets(output_html_path: str) -> None:
    """
    Copy CSS and JS from /static to <output>/assets/ so the HTML can link them.

    Called from generate.py once per run; safe to re-run (always overwrites).
    """
    out_dir = Path(output_html_path).parent
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    # Style, behaviour, and the LCC reference maps (auditable / editable data)
    for filename in ("styles.css", "app.js", "lcc-classes.json", "lcc-subjects.json"):
        src = _STATIC_DIR / filename
        if not src.exists():
            logger.warning("Static asset missing: %s", src)
            continue
        shutil.copy2(src, assets_dir / filename)
    logger.debug("Assets copied to %s", assets_dir)


def write_json_data(envelope: dict, output_html_path: str) -> None:
    """
    Write items.json alongside the HTML so RSS bridges and other consumers
    can read the data without parsing markup.

    The HTML also embeds the same JSON inline, so this file is purely for
    programmatic clients.
    """
    out_dir = Path(output_html_path).parent
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / "items.json"
    json_path.write_text(
        json.dumps(envelope, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.debug("Item data written to %s", json_path)


def _safe_json_for_html(data: dict) -> str:
    """
    Serialise a dict to a JSON string that is safe to embed inside a
    <script type="application/json"> block.

    The escape pattern below blocks three attack vectors:
      </script>  → script-tag breakout
      <!--       → HTML-comment context confusion
      U+2028 /29 → JS line-terminator quirks in legacy parsers
    """
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return (
        raw.replace("<", "\\u003c")
           .replace(">", "\\u003e")
           .replace("&", "\\u0026")
           .replace(" ", "\\u2028")
           .replace(" ", "\\u2029")
    )


def write_output(
    html: str,
    output_path: str,
    *,
    envelope: Optional[dict] = None,
) -> None:
    """
    Write the rendered HTML to disk and (optionally) the parallel JSON and assets.

    Args:
        html:         Rendered HTML string.
        output_path:  Path for the main HTML file.
        envelope:     If provided, also write data/items.json and copy
                      assets/ (styles.css, app.js) into the same directory.
                      Pass None when generating a single-file standalone HTML.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    logger.info("HTML written to %s", path.resolve())

    if envelope is not None:
        write_assets(output_path)
        write_json_data(envelope, output_path)


# ------------------------------------------------------------------
# Private extraction helpers
# ------------------------------------------------------------------


def _material_uuid_from_line(line: dict) -> str:
    """
    Return the material-type UUID for an order line.

    Prefers the queried UUID tagged by generate.py (always set when we asked
    for a specific type) so filtering stays accurate even when /orders does
    not echo physical.materialType in its response.
    """
    queried = line.get(_QUERIED_TYPE_KEY)
    if queried:
        return queried
    physical = line.get("physical") or {}
    return physical.get("materialType") or physical.get("materialTypeId") or ""


def _primary_call_number(holdings: list, line: dict, instance: dict) -> str:
    """
    Best-effort primary call number for the card.

    Source priority (most authoritative first):
      1. The first holding's call_number (RTAC or fallback — already merged
         with the cataloged classification by build_items)
      2. instance.classifications[] direct (safety net in case the merge
         step was bypassed)
      3. The order line's physical.location.callNumber
      4. The instance's first holdings record's callNumber (legacy)
      5. Empty string when nothing is available
    """
    for h in holdings or []:
        cn = h.get("call_number")
        if cn:
            return cn

    cn = _classification_call_number(instance)
    if cn:
        return cn

    physical = line.get("physical") or {}
    loc = physical.get("location") or {}
    cn = loc.get("callNumber")
    if cn:
        return cn

    for holding in instance.get("holdings") or []:
        cn = holding.get("callNumber")
        if cn:
            return cn
    return ""


def _primary_author(instance: dict) -> str:
    contributors = instance.get("contributors") or []
    primary = next((c for c in contributors if c.get("primary")), None)
    chosen = primary or (contributors[0] if contributors else None)
    return chosen.get("name", "") if chosen else ""


def _publisher(instance: dict) -> str:
    pubs = instance.get("publication") or []
    return pubs[0].get("publisher", "") if pubs else ""


def _pub_year(instance: dict) -> str:
    pubs = instance.get("publication") or []
    return pubs[0].get("dateOfPublication", "") if pubs else ""


def _isbn(instance: dict) -> Optional[str]:
    """Return the first ISBN-looking identifier from the instance record."""
    for ident in instance.get("identifiers") or []:
        value = ident.get("value", "").replace("-", "").replace(" ", "")
        if re.fullmatch(r"\d{10}|\d{13}", value):
            return value
    return None


def _oclc(instance: dict) -> Optional[str]:
    """
    Return the OCLC number from instance identifiers if present.

    FOLIO stores OCLC numbers either as bare digits or with an "(OCoLC)" prefix.
    Returns the bare numeric string so it can be passed directly to the Google Books API.
    """
    for ident in instance.get("identifiers") or []:
        value = ident.get("value", "").strip()
        match = re.match(r"^\(OCoLC\)(\d+)$", value)
        if match:
            return match.group(1)
    return None


def _format_date(iso_date: str) -> str:
    """Return the date portion of an ISO datetime string (YYYY-MM-DD)."""
    return iso_date[:10] if iso_date else ""


def _placeholder_color(seed: str) -> str:
    """
    Pick a consistent placeholder-cover background colour for a given seed.

    Uses a stable hash of the seed (typically the material-type UUID) so the
    same format gets the same colour every time the page is regenerated.
    """
    if not seed:
        return _PLACEHOLDER_PALETTE[-1]
    digest = sum(ord(c) for c in seed)
    return _PLACEHOLDER_PALETTE[digest % len(_PLACEHOLDER_PALETTE)]


def _infer_type_label(instance: dict) -> str:
    """Best-effort label when the material type UUID is not in config."""
    formats = instance.get("instanceFormats") or []
    if formats:
        return formats[0].get("name", "Other")
    return "Other"


def _eds_url(
    instance_id: str,
    isbn: Optional[str],
    oclc: Optional[str],
    title: str,
    config,
) -> Optional[str]:
    """
    Build an EDS deep link for an item.

    Honours config.eds_link_strategy:
      - ``openurl`` (default) — enriched OpenURL with the FOLIO access
        number as the id parameter plus rft.isbn / rft.oclc as
        supplementary identifiers.  EDS tries them in order, so new
        records that aren't AN-indexed yet still resolve via ISBN/OCLC.
      - ``search`` — direct EDS Discovery search URL using whichever
        identifier is available, in priority order isbn > oclc > title.
        Always lands on a results page; never 404s.
    """
    if not config.eds_enabled:
        return None

    strategy = getattr(config, "eds_link_strategy", "openurl")
    if strategy == "search":
        return _eds_search_url(isbn, oclc, title, config)
    return _eds_openurl(instance_id, isbn, oclc, config)


def _eds_openurl(
    instance_id: str,
    isbn: Optional[str],
    oclc: Optional[str],
    config,
) -> Optional[str]:
    """
    Enriched OpenURL with AN + rft.isbn + rft.oclc.

    EDS's openurl resolver tries the namespaced ``id`` first, then falls
    back to rft.* identifiers.  Combining all three in one URL gives the
    best chance of landing on the correct record even when the AN hasn't
    yet been indexed (typical for items received but not synced to EDS).
    """
    from urllib.parse import quote

    parts: list[str] = ["sid=ebsco:plink"]

    if instance_id and config.eds_an_prefix and config.eds_catalog_db:
        sep = "-" if config.eds_an_separator == "dashes" else "."
        formatted_id = instance_id.replace("-", sep)
        an_value = f"{config.eds_an_prefix}.{formatted_id}"
        parts.append(f"id=ebsco:{config.eds_catalog_db}:{an_value}")

    if isbn:
        parts.append(f"rft.isbn={quote(isbn, safe='')}")
    if oclc:
        parts.append(f"rft.oclc={quote(str(oclc), safe='')}")

    parts.append("crl=f")
    parts.append("prompt=none")

    return f"https://openurl.ebsco.com/c/{config.eds_db_id}/openurl?" + "&".join(parts)


def _eds_search_url(
    isbn: Optional[str],
    oclc: Optional[str],
    title: str,
    config,
) -> Optional[str]:
    """
    Direct EDS Discovery search URL.

    Useful when AN-based openurls are unreliable (sync lag, unsupported
    record types).  Lands on a results page where the patron picks the
    right record, but never produces a broken link.
    """
    from urllib.parse import urlencode

    if isbn:
        query = f"ISBN:{isbn}"
    elif oclc:
        query = f"OCLC:{oclc}"
    elif title:
        # Quote the title for a phrase search; cap length to avoid URL bloat
        query = f'TI:"{title[:120]}"'
    else:
        return None

    params = {"q": query}
    if config.eds_catalog_db:
        params["db"] = config.eds_catalog_db
    return f"https://research.ebsco.com/c/{config.eds_db_id}/search?{urlencode(params)}"
