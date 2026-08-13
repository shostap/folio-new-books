#!/usr/bin/env python3
"""
Generate the public demo site (docs/) using fully synthetic data.

Used by GitHub Pages to serve a working preview of the page at
https://smithcollegelibraries.github.io/folio-new-material/ so that
prospective users can see the page function before installing.

No FOLIO credentials are read.  No real records are fetched.  All
items, libraries, and patron-facing strings below are invented for
demonstration.

Run from the project root:

    python3 tools/generate_demo.py

The script writes:
    docs/index.html
    docs/.nojekyll
    docs/assets/{styles.css, app.js, lcc-classes.json, lcc-subjects.json}
    docs/data/items.json
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

# Make sure the project root is on sys.path when running directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.html_generator import (
    build_items,
    generate_html,
    build_data_envelope,
    write_output,
)


# ──────────────────────────────────────────────────────────────────────
# Demo configuration — synthetic values throughout
# ──────────────────────────────────────────────────────────────────────

DEMO_LOGO_DATA_URI = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 140 56'>"
    "<rect width='140' height='56' fill='%23ffffff' rx='4'/>"
    "<text x='70' y='36' fill='%23003366' text-anchor='middle' "
    "font-family='system-ui,sans-serif' font-weight='700' "
    "font-size='18'>LIBRARY</text></svg>"
)

DEMO_BANNER_HTML = """
    <div role="status" style="background:#fff7e6;border:1px solid #f4c14d;border-radius:6px;padding:.85rem 1rem;margin:0 0 1rem;color:#5a3d00;font-size:.95rem;line-height:1.5;">
      <strong style="color:#3d2900;">This is a demonstration page.</strong>
      Every item shown below uses synthetic data invented for this preview
      &mdash; nothing here represents a real library's collection.
      See the
      <a href="https://github.com/SmithCollegeLibraries/folio-new-material"
         style="color:#0044aa;font-weight:600;">project README</a>
      for installation instructions.
    </div>
"""


def make_config():
    """Build a config object stub matching what generate.py would produce."""
    cfg = MagicMock()
    # Header / branding
    cfg.output_title = "New Materials"
    cfg.institution_name = "Sample Library (Demo)"
    cfg.institution_logo_url = DEMO_LOGO_DATA_URI
    cfg.primary_color = "#003366"
    cfg.accent_color = "#ffffff"
    # Behaviour
    cfg.default_view = "grid"
    cfg.holdings_display = "summary"
    cfg.subject_groups = {}
    cfg.lcc_grouping = True
    # EDS disabled in the demo — synthetic AN prefixes won't resolve to
    # real records anyway, and clicking through to a 404 would be a
    # worse demo experience than non-clickable titles.
    cfg.eds_enabled = False
    cfg.eds_db_id = ""
    cfg.eds_catalog_db = ""
    cfg.eds_an_prefix = ""
    cfg.eds_an_separator = "dots"
    cfg.eds_link_strategy = "openurl"
    return cfg


# ──────────────────────────────────────────────────────────────────────
# Synthetic data
# ──────────────────────────────────────────────────────────────────────

# Material type UUIDs are arbitrary in the demo — they only need to be
# stable so the type filter dropdown gets reasonable counts.
MT_BOOK = "demo-mt-book"
MT_DVD = "demo-mt-dvd"
MT_MUSIC = "demo-mt-music"
MT_EBOOK = "demo-mt-ebook"

MATERIAL_TYPES = {
    MT_BOOK: "Books",
    MT_DVD: "DVDs",
    MT_MUSIC: "Music CDs",
    MT_EBOOK: "Ebooks",
}

# (title, author, year, isbn, oclc, call_number, status, library, location, mtype, subjects, copies)
DEMO_ITEMS = [
    (
        "Pride and Prejudice",
        "Austen, Jane",
        "2024", "9780141439518", "319234",
        "PR4034 .P7 2024", "Available",
        "Sample Main", "Stacks", MT_BOOK,
        ["English fiction -- 19th century", "Courtship -- Fiction"], 1,
    ),
    (
        "The Pragmatic Programmer: Your Journey to Mastery, 20th Anniversary Edition with Notes from the Original Authors",
        "Hunt, Andrew; Thomas, David",
        "2024", "9780135957059", "1158259993",
        "QA76.6 .H86 2024", "Available",
        "Sample Engineering", "Reserves", MT_BOOK,
        ["Computer programming", "Software engineering"], 3,
    ),
    (
        "A Brief History of Time",
        "Hawking, Stephen W.",
        "2024", "9780553380163", "39945544",
        "QB981 .H37 2024", "Checked out",
        "Sample Main", "Stacks", MT_BOOK,
        ["Cosmology", "Astrophysics -- Popular works"], 1,
    ),
    (
        "The Origin of Species",
        "Darwin, Charles",
        "2024", "9780451529060", "456829118",
        "QH365 .O2 2024", "Available",
        "Sample Main", "Stacks", MT_BOOK,
        ["Evolution (Biology)", "Natural selection"], 1,
    ),
    (
        "Walden",
        "Thoreau, Henry David",
        "2024", "9780691096124", "47008261",
        "PS3048 .A1 2024", "Available",
        "Sample Main", "Special Collections", MT_BOOK,
        ["Natural history -- Massachusetts", "Solitude"], 1,
    ),
    (
        "The Republic",
        "Plato",
        "2024", "9780872201361", "300321712",
        "JC71 .P513 2024", "Available",
        "Sample Main", "Stacks", MT_BOOK,
        ["Political science -- Early works to 1800", "Justice"], 2,
    ),
    (
        "Microeconomics",
        "Mankiw, N. Gregory",
        "2024", "9780357133507", "1192462195",
        "HB172.5 .M36 2024", "Available",
        "Sample Business", "Course Reserves", MT_BOOK,
        ["Microeconomics", "Economics"], 5,
    ),
    (
        "Sapiens: A Brief History of Humankind",
        "Harari, Yuval Noah",
        "2024", "9780062316097", "868058384",
        "CB113 .H37 2024", "Checked out",
        "Sample Main", "Stacks", MT_BOOK,
        ["Civilization -- History", "Human evolution"], 1,
    ),
    (
        "Concise Engineering Mathematics",
        "Bird, John",
        "2024", "9780367643737", "1226270519",
        "TA330 .B57 2024", "Available",
        "Sample Engineering", "Stacks", MT_BOOK,
        ["Engineering mathematics", "Mathematics -- Textbooks"], 1,
    ),
    (
        "Quantum Computing Since Democritus",
        "Aaronson, Scott",
        "2024", "9780521199568", "830374859",
        "QA76.889 .A27 2024", "Available",
        "Sample Engineering", "Stacks", MT_BOOK,
        ["Quantum computing", "Computer science -- Mathematics"], 1,
    ),
    (
        "The Goldfinch",
        "Tartt, Donna",
        "2024", "9780316055437", "857058574",
        "PS3570 .A657 G65 2024", "Available",
        "Sample Main", "Stacks", MT_BOOK,
        ["Coming-of-age stories", "Psychological fiction"], 1,
    ),
    (
        "Modern Inorganic Chemistry",
        "Glasstone, Samuel; Lewis, David",
        "2024", "9789388017879", "1117239340",
        "QD151.3 .M63 2024", "Available",
        "Sample Main", "Stacks", MT_BOOK,
        ["Chemistry, Inorganic -- Textbooks"], 1,
    ),
    (
        "Citizen Kane",
        "Welles, Orson (director)",
        "2024", "", "1141593024",
        "PN1997 .C58 2024 [DVD]", "Available",
        "Sample Main", "Media Collection", MT_DVD,
        ["Motion pictures -- 20th century"], 1,
    ),
    (
        "Casablanca",
        "Curtiz, Michael (director)",
        "2024", "", "892970517",
        "PN1997 .C37 2024 [DVD]", "Available",
        "Sample Main", "Media Collection", MT_DVD,
        ["Motion pictures -- 20th century"], 1,
    ),
    (
        "The Office: Season 1",
        "Daniels, Greg (creator)",
        "2024", "", "59565013",
        "PN1992.77 .O44 2024 [DVD]", "Checked out",
        "Sample Main", "Media Collection", MT_DVD,
        ["Television comedies"], 2,
    ),
    (
        "Planet Earth",
        "Attenborough, David (narrator)",
        "2024", "", "85765317",
        "QL49 .P52 2024 [DVD]", "Available",
        "Sample Main", "Media Collection", MT_DVD,
        ["Natural history -- Pictorial works", "Documentary films"], 1,
    ),
    (
        "Symphony No. 9 in D Minor, Op. 125",
        "Beethoven, Ludwig van",
        "2024", "", "70547421",
        "M1001 .B47 op.125 2024", "Available",
        "Sample Music", "Stacks", MT_MUSIC,
        ["Symphonies -- Scores"], 1,
    ),
    (
        "The Goldberg Variations",
        "Bach, Johann Sebastian; Gould, Glenn (performer)",
        "2024", "", "30094267",
        "M22 .B12 BWV 988 2024", "Available",
        "Sample Music", "Stacks", MT_MUSIC,
        ["Keyboard music", "Variations (Music)"], 1,
    ),
    (
        "Kind of Blue",
        "Davis, Miles",
        "2024", "", "1234567",
        "M1366 .D38 K56 2024", "Available",
        "Sample Music", "Stacks", MT_MUSIC,
        ["Jazz", "Bebop"], 1,
    ),
    # Ebook — exercises the "Online" call number → subject-text fallback
    (
        "Why Women Have Better Sex Under Socialism: And Other Arguments for Economic Independence",
        "Ghodsee, Kristen R.",
        "2024", "9781568588872", "1038035832",
        "Online", "Available",
        "Sample E-Resources", "Online", MT_EBOOK,
        [
            "Women and socialism",
            "Women's rights",
            "Communist countries -- Social conditions",
            "Electronic books",
        ], 1,
    ),
    (
        "The Long Walk to Freedom",
        "Mandela, Nelson",
        "2024", "9780316322409", "31375037",
        "DT1949 .M35 2024", "Available",
        "Sample Main", "Stacks", MT_BOOK,
        ["Mandela, Nelson", "Anti-apartheid movements"], 1,
    ),
    (
        "Crime and Punishment",
        "Dostoevsky, Fyodor",
        "2024", "9780486415871", "44966327",
        "PG3326 .P7 2024", "Available",
        "Sample Main", "Stacks", MT_BOOK,
        ["Russian fiction -- 19th century", "Guilt -- Fiction"], 1,
    ),
    # In-process item — call number from classifications, status "In process"
    (
        "What a Time to Be Alive: A Novel",
        "Mustard, Jenny",
        "2025", "9781639369812", "1492480245",
        "PR6113.U85 W43 2025", "In process",
        "Sample Main", "Receiving", MT_BOOK,
        ["Young women -- Fiction", "Universities and colleges -- Fiction"], 1,
    ),
    # Multi-library consortium item — three copies at different libraries
    (
        "Norton Anthology of American Literature, Shorter Tenth Edition",
        "Levine, Robert S. (editor)",
        "2024", "9780393886184", "1335718388",
        "PS507 .N66 2024", "Available",
        "Sample Main", "Course Reserves", MT_BOOK,
        ["American literature -- Anthologies"], 3,
    ),
    (
        "Microelectronic Circuits",
        "Sedra, Adel S.; Smith, Kenneth C.",
        "2024", "9780190853464", "1019702480",
        "TK7867 .S39 2024", "Available",
        "Sample Engineering", "Reserves", MT_BOOK,
        ["Electronic circuits", "Integrated circuits"], 2,
    ),
]


def build_demo_orders_and_instances():
    """Construct fake orders/instances/holdings to feed through build_items."""
    today = date.today()
    order_lines = []
    instances = {}
    rtac_holdings = {}

    for idx, item in enumerate(DEMO_ITEMS):
        (title, author, year, isbn, oclc, cn, status, library, location,
         mt_uuid, subjects, copies) = item

        instance_id = f"demo-instance-{idx:03d}"
        order_id = f"demo-order-{idx:03d}"
        # Spread receipts across the last 30 days
        days_ago = (idx * 31) % 30
        receipt_iso = (today - timedelta(days=days_ago)).isoformat() + "T00:00:00.000+00:00"

        # Order line
        order_lines.append({
            "id": order_id,
            "instanceId": instance_id,
            "titleOrPackage": title,
            "receiptDate": receipt_iso,
            "receiptStatus": "Fully Received",
            "physical": {"materialType": mt_uuid},
            # Tag with queried UUID so the format filter works reliably
            "_queried_material_uuid": mt_uuid,
        })

        # Instance — shaped like a mod-search response
        identifiers = []
        if isbn:
            identifiers.append({"value": isbn, "identifierTypeId": "isbn-type"})
        if oclc:
            identifiers.append({"value": f"(OCoLC){oclc}", "identifierTypeId": "oclc-type"})

        instances[instance_id] = {
            "id": instance_id,
            "title": title,
            "contributors": [{
                "name": author,
                "primary": True,
                "contributorNameTypeId": "personal",
            }],
            "publication": [{
                "publisher": "Sample Press",
                "dateOfPublication": year,
                "place": "Northampton",
            }],
            "identifiers": identifiers,
            "subjects": [{"value": s} for s in subjects],
            "classifications": [{"classificationNumber": cn, "classificationTypeId": "lcc"}],
        }

        # RTAC holdings — multiple copies for consortium-flavoured demos
        if copies > 1:
            holdings = []
            libraries = ["Sample Main", "Sample Engineering", "Sample Music"][:copies]
            locations = ["Stacks", "Reserves", "Stacks"][:copies]
            statuses = [status, "Available", "Available"][:copies]
            for c_idx in range(copies):
                holdings.append({
                    "call_number": cn if c_idx == 0 else f"{cn} c.{c_idx+1}",
                    "library": libraries[c_idx % len(libraries)],
                    "library_code": "SAM",
                    "location": locations[c_idx % len(locations)],
                    "location_code": "STAC",
                    "status": statuses[c_idx % len(statuses)],
                    "due_date": (today + timedelta(days=14)).isoformat()
                                if statuses[c_idx % len(statuses)] == "Checked out" else "",
                    "loan_type": "Standard Loan",
                    "barcode": f"DEMO{idx:03d}{c_idx}",
                    "material_type": MATERIAL_TYPES[mt_uuid].rstrip("s"),
                })
            rtac_holdings[instance_id] = holdings
        else:
            rtac_holdings[instance_id] = [{
                "call_number": cn,
                "library": library,
                "library_code": "SAM",
                "location": location,
                "location_code": "STAC",
                "status": status,
                "due_date": (today + timedelta(days=14)).isoformat()
                            if status == "Checked out" else "",
                "loan_type": "Standard Loan",
                "barcode": f"DEMO{idx:03d}",
                "material_type": MATERIAL_TYPES[mt_uuid].rstrip("s"),
            }]

    return order_lines, instances, rtac_holdings


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────


def main() -> int:
    cfg = make_config()
    order_lines, instances, rtac_holdings = build_demo_orders_and_instances()

    items = build_items(
        order_lines=order_lines,
        instances=instances,
        material_types=MATERIAL_TYPES,
        config=cfg,
        rtac_holdings=rtac_holdings,
    )

    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    end = today.isoformat()
    generated_at = today.isoformat() + " 06:00"

    html = generate_html(
        items=items,
        material_types=MATERIAL_TYPES,
        start_date=start,
        end_date=end,
        generated_at=generated_at,
        config=cfg,
    )

    # Inject the demo banner right after <main>.  The banner is purely
    # informational and styled inline so it doesn't depend on styles.css
    # changes — keeps the production template unaware of demo concerns.
    main_open = '<main id="main-content" class="site-main">'
    html = html.replace(main_open, main_open + DEMO_BANNER_HTML, 1)

    envelope = build_data_envelope(
        items=items,
        start_date=start,
        end_date=end,
        generated_at=generated_at,
        institution_name=cfg.institution_name,
    )

    docs_dir = PROJECT_ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    output_path = docs_dir / "index.html"
    write_output(html, str(output_path), envelope=envelope)

    # .nojekyll tells GitHub Pages to skip Jekyll processing.  Our
    # assets/ and data/ folders contain underscored / JSON files that
    # Jekyll might otherwise refuse to serve.
    (docs_dir / ".nojekyll").write_text("")

    print(f"Demo site written to {docs_dir.relative_to(PROJECT_ROOT)}/")
    print(f"  {len(items)} items, {len(MATERIAL_TYPES)} material types")
    print("Test it locally:  python3 -m http.server -d docs 8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
