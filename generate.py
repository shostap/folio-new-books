#!/usr/bin/env python3
"""
FOLIO New Materials — HTML generator.

Queries the FOLIO orders API for recently received items and writes a
self-contained HTML5 file that library staff can open in any browser.

Usage:
    python generate.py [options]

Options:
    --config PATH     Path to config.ini  (default: config.ini)
    --start DATE      Start date YYYY-MM-DD  (overrides --days)
    --end   DATE      End date YYYY-MM-DD    (overrides --days)
    --days  N         Days to look back from today  (overrides config)
    --output PATH     Output HTML file  (overrides config)
    --no-images       Skip cover-image lookup

Run this script from *outside* the project directory so that config.ini
is not accidentally exposed by a web server:

    cd /some/other/dir && python /opt/folio-new-books/generate.py \\
        --config /opt/folio-new-books/config.ini \\
        --output /var/www/html/new-materials.html
"""

import argparse
import logging
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from src.config_loader import Config, ConfigError
from src.folio_client import FolioClient, FolioAuthError
from src.edge_client import EdgeClient, normalize_holdings
from src.google_images import fetch_cover_image
from src.tmdb_client import fetch_tmdb_poster
from src.html_generator import (
    build_items,
    generate_html,
    write_output,
    build_data_envelope,
)


def _setup_logging(verbose: bool, log_file: Optional[str]) -> None:
    """
    Configure root logger with console + optional rotating file handler.

    Console gets the configured level (INFO or DEBUG); the file always
    captures DEBUG so post-mortem cron debugging has the full story.
    Rotation: 10 MB × 5 backups, so the file can't grow unbounded.
    """
    console_level = logging.DEBUG if verbose else logging.INFO

    formatter = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers: list[logging.Handler] = []

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(console_level)
    handlers.append(console)

    if log_file:
        try:
            from logging.handlers import RotatingFileHandler
            log_path = Path(log_file).expanduser()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_h = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_h.setFormatter(formatter)
            file_h.setLevel(logging.DEBUG)
            handlers.append(file_h)
        except OSError as exc:
            # Don't abort the run; just warn that we can't write the log file
            print(
                f"Warning: could not open log file {log_file}: {exc}",
                file=sys.stderr,
            )

    # Root logger must be at DEBUG so debug records reach the file handler
    # even when the console is filtering to INFO
    logging.basicConfig(level=logging.DEBUG, handlers=handlers, force=True)


def _warn_on_placeholder_config(config, log) -> None:
    """
    Spot common deployment mistakes where a user left a placeholder value
    from config.ini.example in their live config.ini.

    EDS won't actually fail loudly when this happens — it just returns
    '/not_found/detailv2' for every link, which is easy to miss in a
    cron-driven workflow.  Warn at startup so operators see it.
    """
    checks = [
        ("eds", "an_prefix",  config.eds_an_prefix,
         "example", "your tenant identifier (e.g. fivecolleges, mit, ...)"),
        ("folio", "base_url", config.folio_base_url,
         "api-example.folio.ebsco.com", "your Okapi gateway"),
        ("folio", "username", config.folio_username,
         "your_username", "an actual FOLIO username"),
        ("folio", "password", config.folio_password,
         "your_password", "the matching FOLIO password"),
    ]
    for section, key, value, placeholder, expected in checks:
        if placeholder.lower() in (value or "").lower():
            log.warning(
                "[%s] %s appears to contain the placeholder %r from "
                "config.ini.example — replace it with %s.  EDS will "
                "return 'not_found' for every link otherwise.",
                section, key, placeholder, expected,
            )


def _resolve_log_file(args: argparse.Namespace, config) -> Optional[str]:
    """
    Decide where (if anywhere) to write the log file.

    Resolution order:
      1. --log-file CLI argument (use 'no' / 'none' / 'false' to disable)
      2. [output] log_file from config.ini (same disable values)
      3. Default: logs/folio-new-books.log
    """
    if args.log_file is not None:
        candidate = args.log_file
    else:
        candidate = getattr(config, "log_file", "logs/folio-new-books.log")

    if not candidate or candidate.strip().lower() in ("no", "none", "false", ""):
        return None
    return candidate.strip()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a new-materials HTML page from FOLIO.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        default="config.ini",
        metavar="PATH",
        help="Path to config.ini (default: config.ini)",
    )
    parser.add_argument(
        "--start",
        metavar="YYYY-MM-DD",
        help="Start date (overrides --days)",
    )
    parser.add_argument(
        "--end",
        metavar="YYYY-MM-DD",
        help="End date (default: today)",
    )
    parser.add_argument(
        "--days",
        type=int,
        metavar="N",
        help="Days to look back from today (overrides config setting)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Output HTML file (overrides config setting)",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip all cover-image lookups",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help=(
            "Path to log file (default: logs/folio-new-books.log). "
            "Use 'no' or 'none' to disable file logging."
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging on the console (file always captures DEBUG)",
    )
    return parser.parse_args()


def _resolve_dates(args: argparse.Namespace, config: Config) -> tuple[str, str]:
    """Return (start_date, end_date) as YYYY-MM-DD strings."""
    today = date.today()
    end = date.fromisoformat(args.end) if args.end else today

    if args.start:
        start = date.fromisoformat(args.start)
    else:
        lookback = args.days if args.days is not None else config.output_days
        start = end - timedelta(days=lookback)

    return start.isoformat(), end.isoformat()


def _fetch_all_order_lines(client: FolioClient, start: str, end: str, config: Config) -> list[dict]:
    """
    Retrieve order lines from FOLIO for each configured material type.

    If no material types are configured, a single query fetches all types.
    Paginates automatically if there are more results than the default page size.
    """
    material_types = config.material_types  # UUID → label; empty = all
    queries = list(material_types.keys()) if material_types else [None]

    page_size = 200
    all_lines: list[dict] = []
    seen_ids: set[str] = set()

    for mat_uuid in queries:
        offset = 0
        while True:
            data = client.get_new_orders(
                start, end,
                material_uuid=mat_uuid,
                limit=page_size,
                offset=offset,
            )
            lines = data.get("poLines") or []
            total = data.get("totalRecords", 0)

            for line in lines:
                lid = line.get("id")
                if lid and lid not in seen_ids:
                    seen_ids.add(lid)
                    # Tag the line with the queried UUID so the format filter
                    # works even when /orders does not echo physical.materialType
                    if mat_uuid:
                        line["_queried_material_uuid"] = mat_uuid
                    all_lines.append(line)

            offset += len(lines)
            if offset >= total or not lines:
                break

    return all_lines


def _enrich_with_images(items: list[dict], config: Config, skip: bool) -> None:
    """
    Fetch cover images for each item in-place using a two-step fallback chain.

    Step 1 — Google Books viewapi (free, no key): tried when an ISBN or OCLC
              number is available.  Good for books and other print materials.
    Step 2 — TMDB poster (requires api_key in [tmdb]): tried when Google Books
              returns nothing.  Good for DVDs, Blu-rays, and video recordings.

    Rate-limited to one request per second per external service to stay within
    typical API rate limits.
    """
    if skip:
        return

    any_source = config.google_enabled or config.tmdb_enabled
    if not any_source:
        return

    log = logging.getLogger(__name__)
    log.info("Fetching cover images for %d items …", len(items))

    for idx, item in enumerate(items):
        url: Optional[str] = None  # type: ignore[name-defined]

        # --- Google Books (ISBN / OCLC) ---
        if config.google_enabled and (item.get("isbn") or item.get("oclc")):
            url = fetch_cover_image(
                isbn=item.get("isbn"),
                oclc=item.get("oclc"),
                config=config,
            )

        # --- TMDB fallback (title search) ---
        if not url and config.tmdb_enabled:
            url = fetch_tmdb_poster(
                title=item["title"],
                api_key=config.tmdb_api_key,
                poster_size=config.tmdb_poster_size,
            )

        item["cover_url"] = url
        if idx > 0 and idx % 10 == 0:
            time.sleep(1)  # be polite to external APIs


def main() -> int:
    args = _parse_args()

    # Load config FIRST so log_file (which may be set there) is available
    # before logging is initialised.  Config errors fall back to stderr.
    try:
        config = Config(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    # Now wire up logging — file logging happens to capture the rest of
    # this run, but config errors above had to use plain stderr
    _setup_logging(args.verbose, _resolve_log_file(args, config))
    log = logging.getLogger(__name__)

    # Run banner so successive cron runs have clear log boundaries
    from datetime import datetime
    log.info("─" * 70)
    log.info("FOLIO New Materials — run starting %s",
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Config: %s", args.config)

    # Catch the most common deployment mistake: leaving placeholder
    # values from config.ini.example in the live config.  EDS will
    # silently return /not_found/detailv2 for every link in that case.
    _warn_on_placeholder_config(config, log)

    # Resolve date window
    start_date, end_date = _resolve_dates(args, config)
    log.info("Date range: %s → %s", start_date, end_date)

    # Connect to FOLIO
    client = FolioClient(config)
    try:
        order_lines = _fetch_all_order_lines(client, start_date, end_date, config)
    except FolioAuthError as exc:
        log.error("FOLIO authentication failed: %s", exc)
        return 1
    except Exception as exc:
        log.error("Error fetching orders from FOLIO: %s", exc)
        return 1

    log.info("Retrieved %d order lines", len(order_lines))
    if not order_lines:
        log.warning("No order lines found for this date range — HTML will show an empty state.")

    # Fetch instance details
    instance_ids = [
        ln.get("instanceId") or ln.get("instanceid")
        for ln in order_lines
        if ln.get("instanceId") or ln.get("instanceid")
    ]
    try:
        instances = client.get_instances(list(set(instance_ids)))
    except Exception as exc:
        log.warning("Instance lookup failed: %s — titles from order lines will be used.", exc)
        instances = {}

    log.info("Fetched details for %d instances", len(instances))

    # Build the material-type label map.
    # When the user has configured specific types, use that map directly.
    # Otherwise, fetch every defined material type from FOLIO so the dropdown
    # can show real names instead of raw UUIDs.
    if config.material_types:
        material_type_map = config.material_types
    else:
        try:
            material_type_map = client.get_material_types()
            log.info("Discovered %d material types from FOLIO", len(material_type_map))
        except Exception as exc:
            log.warning("Could not fetch material types: %s", exc)
            material_type_map = {}

    # Fetch live holdings from the Edge RTAC endpoint when configured.
    # Provides authoritative call numbers, locations, statuses, and supports
    # consortia where a single instance has copies at multiple libraries.
    rtac_holdings: dict[str, list[dict]] = {}
    if config.edge_enabled and instance_ids:
        log.info("Fetching live holdings via Edge RTAC for %d instances …", len(set(instance_ids)))
        edge = EdgeClient(config.folio_edge_api, config.folio_edge_api_key)
        rtac_raw = edge.get_rtac_batch(list(set(instance_ids)))
        rtac_holdings = {iid: normalize_holdings(data) for iid, data in rtac_raw.items()}
        log.info("Got RTAC data for %d / %d instances", len(rtac_holdings), len(set(instance_ids)))

    # Fetch the locations map so the fallback (non-RTAC) holdings path can
    # show human-readable location names rather than UUIDs.
    try:
        locations_map = client.get_locations()
        log.info("Loaded %d location definitions", len(locations_map))
    except Exception as exc:
        log.warning("Could not fetch locations: %s", exc)
        locations_map = {}

    # Build display items
    items = build_items(
        order_lines, instances, material_type_map, config,
        rtac_holdings=rtac_holdings,
        locations_map=locations_map,
    )

    # Optionally enrich with cover images
    _enrich_with_images(items, config, skip=args.no_images)

    # Render HTML
    from datetime import datetime
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    output_path = args.output or config.output_file

    # Single combined data feed is always written; per-type pages embed
    # filtered JSON but consumers of items.json get the full set.
    envelope_full = build_data_envelope(
        items=items,
        start_date=start_date,
        end_date=end_date,
        generated_at=generated_at,
        institution_name=config.institution_name,
    )

    try:
        if config.pages_per_type:
            written = _write_per_type_pages(
                items=items,
                config=config,
                material_type_map=material_type_map,
                output_path=output_path,
                start_date=start_date,
                end_date=end_date,
                generated_at=generated_at,
                envelope_full=envelope_full,
                log=log,
            )
            log.info("Done — wrote %d per-type page(s) plus shared assets/ and data/items.json", written)
        else:
            html = generate_html(
                items=items,
                material_types=config.material_types,
                start_date=start_date,
                end_date=end_date,
                generated_at=generated_at,
                config=config,
            )
            write_output(html, output_path, envelope=envelope_full)
            log.info(
                "Done — %d items written to %s (plus assets/ and data/items.json)",
                len(items), output_path,
            )
    except OSError as exc:
        log.error("Failed to write output: %s", exc)
        return 1

    return 0


def _slugify(text: str) -> str:
    """Convert a label like 'Music CD' into a URL-safe slug 'music-cd'."""
    cleaned = re.sub(r"[^\w\s-]", "", (text or "").lower())
    slug = re.sub(r"[\s_-]+", "-", cleaned).strip("-")
    return slug or "other"


def _write_per_type_pages(
    items, config, material_type_map, output_path,
    start_date, end_date, generated_at, envelope_full, log,
):
    """
    Generate one HTML page per material type.

    File naming: new-{slug(type_label)}.html, sibling to ``output_path``.
    Each page embeds only its own items; the combined data feed is still
    written once to data/items.json next to the first page.

    Returns the number of pages written.
    """
    # Group items by type_uuid
    by_type: dict[str, list[dict]] = {}
    for item in items:
        key = item.get("type_uuid") or ""
        by_type.setdefault(key, []).append(item)

    if not by_type:
        # No items at all — write a single empty page so the cron job's
        # output is still consistent
        empty_html = generate_html(
            items=[], material_types={}, start_date=start_date, end_date=end_date,
            generated_at=generated_at, config=config,
        )
        write_output(empty_html, output_path, envelope=envelope_full)
        return 1

    output_dir = Path(output_path).parent
    pages_written = 0
    written_combined_feed = False
    used_slugs: set[str] = set()

    for type_uuid, type_items in by_type.items():
        type_label = type_items[0].get("type_label") or material_type_map.get(type_uuid) or "Other"

        # Ensure unique filename across colliding slugs (rare but possible)
        slug_base = _slugify(type_label)
        slug = slug_base
        n = 2
        while slug in used_slugs:
            slug = f"{slug_base}-{n}"
            n += 1
        used_slugs.add(slug)

        page_path = output_dir / f"new-{slug}.html"
        log.info("Writing %d %s items → %s", len(type_items), type_label, page_path.name)

        # Build a per-type label map so the page header / metadata reflect
        # only this one format
        per_type_labels = {type_uuid: type_label} if type_uuid else {}

        html = generate_html(
            items=type_items,
            material_types=per_type_labels,
            start_date=start_date,
            end_date=end_date,
            generated_at=generated_at,
            config=config,
        )

        # Write assets and the combined data feed once; subsequent pages
        # just need the HTML alongside.
        if not written_combined_feed:
            write_output(html, str(page_path), envelope=envelope_full)
            written_combined_feed = True
        else:
            write_output(html, str(page_path))  # HTML only — no envelope

        pages_written += 1

    return pages_written


if __name__ == "__main__":
    sys.exit(main())
