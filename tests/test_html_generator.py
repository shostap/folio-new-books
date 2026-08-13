"""Tests for src/html_generator.py."""

from unittest.mock import MagicMock

import pytest

import json

from src.html_generator import (
    build_items,
    build_fallback_holdings,
    generate_html,
    build_data_envelope,
    write_output,
    write_assets,
    write_json_data,
    _safe_json_for_html,
    _classification_call_number,
    _eds_url,
    _primary_author,
    _publisher,
    _pub_year,
    _isbn,
    _oclc,
    _format_date,
    _material_uuid_from_line,
)


# ── Fixtures ──────────────────────────────────────────────────────────


def _config(
    primary_color="#003366",
    accent_color="#ffffff",
    eds_enabled=True,
    eds_db_id="4e4lys",
    eds_catalog_db="cat09206a",
    eds_an_prefix="scf.oai.edge.example.com.tenant01",
    eds_an_separator="dots",
    eds_link_strategy="openurl",
    output_title="New Materials",
    institution_name="Test Library",
    institution_logo_url="",
    subject_groups=None,
    lcc_grouping=False,
    default_view="grid",
    holdings_display="summary",
):
    cfg = MagicMock()
    cfg.primary_color = primary_color
    cfg.accent_color = accent_color
    cfg.eds_enabled = eds_enabled
    cfg.eds_db_id = eds_db_id
    cfg.eds_catalog_db = eds_catalog_db
    cfg.eds_an_prefix = eds_an_prefix
    cfg.eds_an_separator = eds_an_separator
    cfg.eds_link_strategy = eds_link_strategy
    cfg.output_title = output_title
    cfg.institution_name = institution_name
    cfg.institution_logo_url = institution_logo_url
    cfg.subject_groups = subject_groups or {}
    cfg.lcc_grouping = lcc_grouping
    cfg.default_view = default_view
    cfg.holdings_display = holdings_display
    return cfg


SAMPLE_INSTANCE = {
    "id": "eb83a0c0-c9f8-4b09-8362-2bbcc06f0a16",
    "title": "The Great Library Book",
    "contributors": [
        {"name": "Smith, Jane", "primary": True, "contributorNameTypeId": "2b94c631-fca9-4892-a730-03ee529ffe2a"},
        {"name": "Doe, John", "primary": False, "contributorNameTypeId": "2b94c631-fca9-4892-a730-03ee529ffe2a"},
    ],
    "publication": [
        {"publisher": "Academic Press", "dateOfPublication": "2023", "place": "New York"},
    ],
    "identifiers": [
        {"value": "9780123456789", "identifierTypeId": "isbn-type-id"},
        {"value": "(OCoLC)12345678", "identifierTypeId": "oclc-type-id"},
        {"value": "SomeOtherValue", "identifierTypeId": "other-type-id"},
    ],
}

SAMPLE_ORDER_LINE = {
    "id": "order-line-uuid",
    "instanceId": "eb83a0c0-c9f8-4b09-8362-2bbcc06f0a16",
    "titleOrPackage": "Fallback Title",
    "receiptDate": "2024-03-15T00:00:00.000+00:00",
    "receiptStatus": "Fully Received",
    "physical": {
        "materialType": "2d72aa13-2451-41fe-afc7-b3dc7c131389",
    },
}


# ── Helper function tests ─────────────────────────────────────────────


def test_primary_author_picks_primary_contributor():
    assert _primary_author(SAMPLE_INSTANCE) == "Smith, Jane"


def test_primary_author_falls_back_to_first():
    instance = {
        "contributors": [
            {"name": "Doe, John", "primary": False},
        ]
    }
    assert _primary_author(instance) == "Doe, John"


def test_primary_author_empty_for_no_contributors():
    assert _primary_author({}) == ""


def test_publisher_returns_first():
    assert _publisher(SAMPLE_INSTANCE) == "Academic Press"


def test_publisher_empty_for_no_publication():
    assert _publisher({}) == ""


def test_pub_year():
    assert _pub_year(SAMPLE_INSTANCE) == "2023"


def test_isbn_extracts_numeric():
    assert _isbn(SAMPLE_INSTANCE) == "9780123456789"


def test_isbn_returns_none_when_none_present():
    assert _isbn({"identifiers": [{"value": "notanisbn", "identifierTypeId": "x"}]}) is None


def test_oclc_extracts_from_ocolc_prefix():
    assert _oclc(SAMPLE_INSTANCE) == "12345678"


def test_oclc_returns_none_when_absent():
    instance = {"identifiers": [{"value": "9780123456789", "identifierTypeId": "isbn"}]}
    assert _oclc(instance) is None


def test_format_date_trims_to_date():
    assert _format_date("2024-03-15T00:00:00.000+00:00") == "2024-03-15"


def test_format_date_handles_empty():
    assert _format_date("") == ""


def test_material_uuid_from_line():
    assert _material_uuid_from_line(SAMPLE_ORDER_LINE) == "2d72aa13-2451-41fe-afc7-b3dc7c131389"


def test_material_uuid_empty_when_no_physical():
    assert _material_uuid_from_line({}) == ""


def test_material_uuid_prefers_queried_tag():
    """generate.py tags lines with the queried UUID; that should win."""
    line = {
        "_queried_material_uuid": "queried-uuid",
        "physical": {"materialType": "other-uuid"},
    }
    assert _material_uuid_from_line(line) == "queried-uuid"


class TestClassificationCallNumber:
    def test_single_lcc_classification(self):
        instance = {"classifications": [{"classificationNumber": "PR6113.U85 W43 2025"}]}
        assert _classification_call_number(instance) == "PR6113.U85 W43 2025"

    def test_prefers_lcc_when_dewey_is_first(self):
        # Cataloger may list Dewey first; LCC-shaped value should still win
        instance = {"classifications": [
            {"classificationNumber": "823.91", "classificationTypeId": "dewey"},
            {"classificationNumber": "PR6113.U85", "classificationTypeId": "lc"},
        ]}
        assert _classification_call_number(instance) == "PR6113.U85"

    def test_falls_back_to_first_when_no_lcc(self):
        instance = {"classifications": [
            {"classificationNumber": "823.91"},
            {"classificationNumber": "813.6"},
        ]}
        assert _classification_call_number(instance) == "823.91"

    def test_returns_empty_string_when_no_classifications(self):
        assert _classification_call_number({}) == ""
        assert _classification_call_number({"classifications": []}) == ""


# ── EDS URL ───────────────────────────────────────────────────────────


class TestEdsUrl:
    def test_builds_correct_url_with_dots(self):
        cfg = _config(eds_an_separator="dots")
        url = _eds_url(
            "eb83a0c0-c9f8-4b09-8362-2bbcc06f0a16",
            isbn=None, oclc=None, title="", config=cfg,
        )
        assert "openurl.ebsco.com/c/4e4lys/openurl" in url
        assert "eb83a0c0.c9f8.4b09.8362.2bbcc06f0a16" in url
        assert "ebsco:plink" in url
        assert "ebsco:cat09206a" in url

    def test_builds_correct_url_with_dashes(self):
        cfg = _config(eds_an_separator="dashes")
        url = _eds_url(
            "eb83a0c0-c9f8-4b09-8362-2bbcc06f0a16",
            isbn=None, oclc=None, title="", config=cfg,
        )
        assert "eb83a0c0-c9f8-4b09-8362-2bbcc06f0a16" in url

    def test_returns_none_when_eds_disabled(self):
        cfg = _config(eds_enabled=False)
        url = _eds_url("some-uuid", isbn=None, oclc=None, title="", config=cfg)
        assert url is None

    def test_openurl_includes_rft_isbn_when_available(self):
        cfg = _config()
        url = _eds_url(
            "eb83a0c0-c9f8-4b09-8362-2bbcc06f0a16",
            isbn="1639369813", oclc=None, title="", config=cfg,
        )
        # Both the AN id and the rft.isbn fallback identifier are in the URL
        assert "id=ebsco:cat09206a:" in url
        assert "rft.isbn=1639369813" in url

    def test_openurl_includes_rft_oclc_when_available(self):
        cfg = _config()
        url = _eds_url(
            "eb83a0c0-c9f8-4b09-8362-2bbcc06f0a16",
            isbn=None, oclc="1492480245", title="", config=cfg,
        )
        assert "rft.oclc=1492480245" in url

    def test_openurl_combines_all_identifiers(self):
        cfg = _config()
        url = _eds_url(
            "eb83a0c0-c9f8-4b09-8362-2bbcc06f0a16",
            isbn="1639369813", oclc="1492480245",
            title="A novel", config=cfg,
        )
        # EDS resolves in order: AN id → rft.isbn → rft.oclc — give it all
        assert "id=ebsco:cat09206a:" in url
        assert "rft.isbn=1639369813" in url
        assert "rft.oclc=1492480245" in url

    def test_search_strategy_uses_research_ebsco(self):
        cfg = _config(eds_link_strategy="search")
        url = _eds_url(
            "any-uuid",
            isbn="1639369813", oclc=None, title="A novel", config=cfg,
        )
        # Search URL lands on the EDS Discovery results page
        assert "research.ebsco.com" in url
        assert "q=ISBN%3A1639369813" in url

    def test_search_strategy_prefers_isbn_over_oclc(self):
        cfg = _config(eds_link_strategy="search")
        url = _eds_url(
            "any-uuid",
            isbn="9781234567890", oclc="555", title="X", config=cfg,
        )
        assert "9781234567890" in url
        assert "555" not in url

    def test_search_strategy_falls_back_to_title(self):
        cfg = _config(eds_link_strategy="search")
        url = _eds_url(
            "any-uuid",
            isbn=None, oclc=None,
            title="What a time to be alive", config=cfg,
        )
        assert "TI" in url
        assert "What" in url or "What%20a" in url or "What+a" in url

    def test_search_strategy_returns_none_with_no_identifiers(self):
        cfg = _config(eds_link_strategy="search")
        url = _eds_url("any-uuid", isbn=None, oclc=None, title="", config=cfg)
        assert url is None


# ── build_items ───────────────────────────────────────────────────────


class TestBuildItems:
    def test_merges_order_and_instance_data(self):
        instances = {SAMPLE_INSTANCE["id"]: SAMPLE_INSTANCE}
        types = {"2d72aa13-2451-41fe-afc7-b3dc7c131389": "Books"}
        items = build_items([SAMPLE_ORDER_LINE], instances, types, _config())

        assert len(items) == 1
        item = items[0]
        assert item["title"] == "The Great Library Book"
        assert item["author"] == "Smith, Jane"
        assert item["publisher"] == "Academic Press"
        assert item["year"] == "2023"
        assert item["receipt_date"] == "2024-03-15"
        assert item["type_label"] == "Books"
        assert item["isbn"] == "9780123456789"
        assert item["oclc"] == "12345678"
        assert item["eds_url"] is not None

    def test_uses_titleOrPackage_when_no_instance(self):
        items = build_items([SAMPLE_ORDER_LINE], {}, {}, _config())
        assert items[0]["title"] == "Fallback Title"

    def test_skips_lines_without_instance_id(self):
        line = {"id": "no-instance", "receiptDate": "2024-01-01"}
        items = build_items([line], {}, {}, _config())
        assert len(items) == 0

    def test_assigns_placeholder_color(self):
        instances = {SAMPLE_INSTANCE["id"]: SAMPLE_INSTANCE}
        items = build_items([SAMPLE_ORDER_LINE], instances, {}, _config())
        assert items[0]["placeholder_color"].startswith("#")

    def test_subject_classification_when_groups_configured(self):
        cfg = _config(subject_groups={"Sciences": ["chemistry", "biology"]})
        instance = dict(SAMPLE_INSTANCE, subjects=["Inorganic chemistry"])
        items = build_items([SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, cfg)
        assert items[0]["subject_group"] == "Sciences"

    def test_subject_group_empty_when_no_groups(self):
        items = build_items(
            [SAMPLE_ORDER_LINE],
            {SAMPLE_INSTANCE["id"]: SAMPLE_INSTANCE},
            {},
            _config(),
        )
        assert items[0]["subject_group"] == ""

    def test_call_number_from_holdings(self):
        instance = dict(SAMPLE_INSTANCE, holdings=[{"callNumber": "QA76.5"}])
        items = build_items([SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, _config())
        assert items[0]["call_number"] == "QA76.5"

    def test_rtac_holdings_override_instance_call_number(self):
        instance = dict(SAMPLE_INSTANCE, holdings=[{"callNumber": "OLD-CN"}])
        rtac = {instance["id"]: [
            {"call_number": "RTAC-CN", "location": "Stacks", "library": "Main"},
            {"call_number": "RTAC-CN-2", "location": "Annex", "library": "Branch"},
        ]}
        items = build_items(
            [SAMPLE_ORDER_LINE],
            {instance["id"]: instance},
            {},
            _config(),
            rtac_holdings=rtac,
        )
        assert items[0]["call_number"] == "RTAC-CN"
        assert len(items[0]["holdings"]) == 2

    def test_subjects_included_in_item_dict(self):
        instance = dict(SAMPLE_INSTANCE, subjects=["History", "Chemistry"])
        items = build_items(
            [SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, _config(),
        )
        assert items[0]["subjects"] == ["History", "Chemistry"]

    def test_subjects_normalized_from_dict_shape(self):
        instance = dict(SAMPLE_INSTANCE, subjects=[
            {"value": "Engineering"}, {"value": "Mathematics"},
        ])
        items = build_items(
            [SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, _config(),
        )
        assert items[0]["subjects"] == ["Engineering", "Mathematics"]

    def test_lcc_grouping_classifies_by_call_number(self):
        cfg = _config(lcc_grouping=True)
        rtac = {SAMPLE_INSTANCE["id"]: [
            {"call_number": "QA76.5 .S5", "library": "Main", "location": "Stacks"},
        ]}
        items = build_items(
            [SAMPLE_ORDER_LINE],
            {SAMPLE_INSTANCE["id"]: SAMPLE_INSTANCE},
            {},
            cfg,
            rtac_holdings=rtac,
        )
        # QA → Mathematics; Computer Science (more granular than just "Science")
        assert items[0]["subject_group"] == "Mathematics; Computer Science"

    def test_unsynced_record_uses_classification_call_number(self):
        """User's Jenny Mustard example: RTAC empty CN, classifications populated."""
        cfg = _config(lcc_grouping=True)
        instance = dict(
            SAMPLE_INSTANCE,
            classifications=[
                {"classificationNumber": "PR6113.U85 W43 2025", "classificationTypeId": "lc"},
            ],
            items=[{"effectiveCallNumberComponents": {}, "status": {"name": "In process"}}],
        )
        # RTAC returns the holding but call_number is empty (item not yet shelved)
        rtac = {instance["id"]: [
            {"call_number": "", "library": "UM Du Bois", "status": "In process"},
        ]}
        items = build_items(
            [SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, cfg,
            rtac_holdings=rtac,
        )
        item = items[0]
        # Call number was filled in from instance.classifications
        assert item["call_number"] == "PR6113.U85 W43 2025"
        # The RTAC holding was supplemented (not replaced)
        assert item["holdings"][0]["call_number"] == "PR6113.U85 W43 2025"
        assert item["holdings"][0]["library"] == "UM Du Bois"
        assert item["holdings"][0]["status"] == "In process"
        # LCC grouping now classifies it via PR
        assert item["subject_group"] == "English Literature"

    def test_rtac_call_number_wins_over_classification(self):
        """When RTAC has its own call_number, the merge doesn't overwrite it."""
        cfg = _config(lcc_grouping=True)
        instance = dict(
            SAMPLE_INSTANCE,
            classifications=[{"classificationNumber": "PR6113.X1 2025"}],
        )
        rtac = {instance["id"]: [{"call_number": "QA76.5 .S5 LIVE", "library": "Main"}]}
        items = build_items(
            [SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, cfg,
            rtac_holdings=rtac,
        )
        # RTAC's call number is unchanged
        assert items[0]["holdings"][0]["call_number"] == "QA76.5 .S5 LIVE"
        # Primary call_number reflects what's in holdings, which is the RTAC value
        assert items[0]["call_number"] == "QA76.5 .S5 LIVE"

    def test_fallback_holdings_use_classification_when_item_cn_empty(self):
        """No RTAC at all + items[] with no call number → use classification."""
        cfg = _config(lcc_grouping=True)
        instance = dict(
            SAMPLE_INSTANCE,
            classifications=[{"classificationNumber": "PN51 .T7 2022"}],
            items=[{
                "effectiveCallNumberComponents": {},  # empty
                "status": {"name": "In process"},
                "effectiveLocationId": "loc-uuid",
            }],
        )
        items = build_items(
            [SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, cfg,
            rtac_holdings={},  # no RTAC at all
            locations_map={"loc-uuid": "Stacks"},
        )
        assert items[0]["holdings"][0]["call_number"] == "PN51 .T7 2022"
        assert items[0]["subject_group"] == "Literature (General); Drama; Journalism"

    def test_subject_fallback_when_call_number_is_online(self):
        """Ebooks have call_number 'Online' — must fall through to subjects."""
        cfg = _config(lcc_grouping=True)
        instance = dict(SAMPLE_INSTANCE, subjects=[
            "Women and socialism--Communist countries",
            "Women's Studies",
            "Electronic books",
        ])
        rtac = {instance["id"]: [{"call_number": "Online", "library": "UM"}]}
        items = build_items(
            [SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, cfg,
            rtac_holdings=rtac,
        )
        # Should land in HQ via "women", not "Other"
        assert items[0]["subject_group"] == "Family; Marriage; Sex"

    def test_subject_fallback_when_call_number_empty(self):
        """New arrivals not yet in EDS have empty call_number."""
        cfg = _config(lcc_grouping=True)
        instance = dict(SAMPLE_INSTANCE, subjects=["Astronomy", "Cosmology"])
        items = build_items(
            [SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, cfg,
            rtac_holdings={},  # nothing from RTAC
        )
        assert items[0]["subject_group"] == "Astronomy"

    def test_manual_groups_fall_through_to_lcc_when_no_keyword_matches(self):
        """Regression: manual groups used to short-circuit to Other on a miss."""
        cfg = _config(
            subject_groups={"Engineering": ["computer", "programming"]},
            lcc_grouping=True,
        )
        # Item is literature (PN51), manual keywords don't match — should fall
        # through to LCC instead of getting "Other"
        rtac = {SAMPLE_INSTANCE["id"]: [{"call_number": "PN51 .T7 2022", "library": "Main"}]}
        instance = dict(SAMPLE_INSTANCE, subjects=["Communism and literature"])
        items = build_items(
            [SAMPLE_ORDER_LINE],
            {instance["id"]: instance},
            {},
            cfg,
            rtac_holdings=rtac,
        )
        assert items[0]["subject_group"] == "Literature (General); Drama; Journalism"

    def test_lcc_grouping_assigns_other_for_dewey(self):
        cfg = _config(lcc_grouping=True)
        rtac = {SAMPLE_INSTANCE["id"]: [
            {"call_number": "641.5 SMI", "library": "Main", "location": "Stacks"},
        ]}
        items = build_items(
            [SAMPLE_ORDER_LINE],
            {SAMPLE_INSTANCE["id"]: SAMPLE_INSTANCE},
            {},
            cfg,
            rtac_holdings=rtac,
        )
        assert items[0]["subject_group"] == "Other"

    def test_manual_groups_take_precedence_over_lcc(self):
        cfg = _config(
            subject_groups={"Sciences": ["chemistry"]},
            lcc_grouping=True,
        )
        instance = dict(SAMPLE_INSTANCE, subjects=["Chemistry -- General"])
        items = build_items(
            [SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, cfg,
        )
        assert items[0]["subject_group"] == "Sciences"

    def test_fallback_holdings_from_instance_items(self):
        """When RTAC has nothing, build holdings from instance.items[]."""
        instance = dict(SAMPLE_INSTANCE, items=[
            {
                "id": "item-1",
                "barcode": "12345",
                "status": {"name": "Available"},
                "effectiveLocationId": "loc-uuid-1",
                "effectiveCallNumberComponents": {"callNumber": "QA76.5 .S5"},
            },
        ])
        locations = {"loc-uuid-1": "Smith Neilson Stacks"}
        items = build_items(
            [SAMPLE_ORDER_LINE],
            {instance["id"]: instance},
            {},
            _config(),
            rtac_holdings={},   # RTAC empty
            locations_map=locations,
        )
        assert len(items[0]["holdings"]) == 1
        assert items[0]["holdings"][0]["call_number"] == "QA76.5 .S5"
        assert items[0]["holdings"][0]["location"] == "Smith Neilson Stacks"
        assert items[0]["holdings"][0]["status"] == "Available"
        assert items[0]["call_number"] == "QA76.5 .S5"

    def test_rtac_takes_priority_over_fallback(self):
        """RTAC data wins even when instance.items[] has its own call numbers."""
        instance = dict(SAMPLE_INSTANCE, items=[
            {"effectiveCallNumberComponents": {"callNumber": "STALE-CN"}},
        ])
        rtac = {instance["id"]: [{"call_number": "LIVE-CN", "library": "Main"}]}
        items = build_items(
            [SAMPLE_ORDER_LINE], {instance["id"]: instance}, {}, _config(),
            rtac_holdings=rtac,
        )
        assert items[0]["call_number"] == "LIVE-CN"


# ── generate_html ─────────────────────────────────────────────────────


class TestGenerateHtml:
    def _sample_item(self, **kwargs):
        base = {
            "id": "item-1",
            "instance_id": "inst-1",
            "title": "Test Book",
            "author": "Author Name",
            "publisher": "Publisher",
            "year": "2024",
            "receipt_date": "2024-01-15",
            "type_uuid": "2d72aa13-2451-41fe-afc7-b3dc7c131389",
            "type_label": "Books",
            "subject_group": "",
            "subjects": [],
            "call_number": "",
            "holdings": [],
            "cover_url": None,
            "placeholder_color": "#2a5e8c",
            "eds_url": "https://openurl.ebsco.com/c/abc/openurl?sid=ebsco:plink&id=x",
            "isbn": None,
            "oclc": None,
        }
        base.update(kwargs)
        return base

    def test_renders_valid_html(self):
        # Items are no longer rendered as HTML; they live in the embedded JSON
        # block and are populated into the DOM by app.js at view time.
        items = [self._sample_item()]
        types = {"2d72aa13-2451-41fe-afc7-b3dc7c131389": "Books"}
        html = generate_html(items, types, "2024-01-01", "2024-01-31", "2024-02-01 06:00", _config())

        assert "<!DOCTYPE html>" in html
        # Title appears in the embedded JSON
        assert "Test Book" in html
        assert "Author Name" in html
        # External assets are linked, not inlined
        assert 'href="assets/styles.css"' in html
        assert 'src="assets/app.js"' in html
        assert 'id="items-data"' in html

    def test_renders_empty_state_when_no_items(self):
        html = generate_html([], {}, "2024-01-01", "2024-01-31", "2024-02-01 06:00", _config())
        assert "No new materials" in html

    def test_includes_noscript_fallback(self):
        items = [self._sample_item()]
        types = {"2d72aa13-2451-41fe-afc7-b3dc7c131389": "Books"}
        html = generate_html(items, types, "2024-01-01", "2024-01-31", "now", _config())
        assert "<noscript>" in html
        assert "data/items.json" in html

    def test_includes_eds_link(self):
        items = [self._sample_item()]
        types = {"2d72aa13-2451-41fe-afc7-b3dc7c131389": "Books"}
        html = generate_html(items, types, "2024-01-01", "2024-01-31", "2024-02-01 06:00", _config())
        # EDS URL appears in embedded JSON
        assert "openurl.ebsco.com" in html

    def test_includes_institution_name(self):
        cfg = _config(institution_name="Smith College Libraries")
        html = generate_html([], {}, "2024-01-01", "2024-01-31", "now", cfg)
        assert "Smith College Libraries" in html

    def test_loads_external_js(self):
        html = generate_html([], {}, "2024-01-01", "2024-01-31", "now", _config())
        # JS bundle is linked regardless of items / dropdowns
        assert 'src="assets/app.js"' in html

    def test_no_xss_in_title(self):
        """User-supplied config values must be escaped in HTML output."""
        cfg = _config(institution_name='<script>alert("xss")</script>')
        html = generate_html([], {}, "2024-01-01", "2024-01-31", "now", cfg)
        assert "<script>alert" not in html

    def test_renders_subject_filter_when_groups_enabled(self):
        cfg = _config(subject_groups={"Sciences": ["biology"]})
        item = self._sample_item(subject_group="Sciences")
        html = generate_html([item], {}, "2024-01-01", "2024-01-31", "now", cfg)
        assert 'id="subject-filter"' in html
        assert "Sciences" in html

    def test_omits_subject_filter_when_groups_disabled(self):
        item = self._sample_item()
        html = generate_html([item], {}, "2024-01-01", "2024-01-31", "now", _config())
        assert 'id="subject-filter"' not in html

    def test_renders_both_view_containers(self):
        item = self._sample_item()
        html = generate_html([item], {}, "2024-01-01", "2024-01-31", "now", _config())
        # Empty containers that JS will populate
        assert 'id="materials-table"' in html
        assert 'id="materials-grid"' in html

    def test_default_view_table_hides_grid_container(self):
        cfg = _config(default_view="table")
        item = self._sample_item()
        html = generate_html([item], {}, "2024-01-01", "2024-01-31", "now", cfg)
        # Grid container has the hidden attribute when table is default view
        assert 'aria-label="New materials (grid view)"' in html
        # Verify hidden attribute follows the grid container marker
        grid_start = html.find('aria-label="New materials (grid view)"')
        following = html[grid_start:grid_start + 200]
        assert "hidden" in following

    def test_placeholder_color_appears_in_embedded_json(self):
        item = self._sample_item(cover_url=None, placeholder_color="#7d3f5d")
        html = generate_html([item], {}, "2024-01-01", "2024-01-31", "now", _config())
        assert "#7d3f5d" in html  # present in the JSON data block

    def test_format_counts_render_when_lcc_grouping_enabled(self):
        """Regression: counts variable was shadowed inside the LCC branch."""
        cfg = _config(lcc_grouping=True)
        items = [
            self._sample_item(type_uuid="uuid-1", type_label="Books"),
            self._sample_item(type_uuid="uuid-1", type_label="Books"),
            self._sample_item(type_uuid="uuid-2", type_label="DVD"),
        ]
        html = generate_html(items, {"uuid-1": "Books", "uuid-2": "DVD"},
                              "2024-01-01", "2024-01-31", "now", cfg)
        assert "Books (2)" in html
        assert "DVD (1)" in html

    def test_format_dropdown_hidden_when_single_type(self):
        # Single material type in the data → dropdown is useless, hide it
        item = self._sample_item(type_uuid="only-one", type_label="Books")
        html = generate_html([item], {}, "2024-01-01", "2024-01-31", "now", _config())
        assert 'id="format-filter"' not in html

    def test_format_dropdown_visible_with_two_types(self):
        items = [
            self._sample_item(type_uuid="uuid-1", type_label="Books"),
            self._sample_item(type_uuid="uuid-2", type_label="DVD"),
        ]
        html = generate_html(items, {}, "2024-01-01", "2024-01-31", "now", _config())
        assert 'id="format-filter"' in html


# ── Data envelope & write helpers ─────────────────────────────────────


class TestBuildDataEnvelope:
    def test_envelope_structure(self):
        items = [{"id": "x", "title": "T"}]
        env = build_data_envelope(items, "2024-01-01", "2024-01-31", "now", "Lib")
        assert env["total_count"] == 1
        assert env["date_range"] == {"start": "2024-01-01", "end": "2024-01-31"}
        assert env["institution"] == "Lib"
        assert env["items"] == items


class TestSafeJsonForHtml:
    def test_escapes_script_breakout(self):
        data = {"title": "</script><img>"}
        out = _safe_json_for_html(data)
        assert "</script>" not in out
        assert "\\u003c" in out

    def test_escapes_html_comment_start(self):
        data = {"title": "<!-- nope"}
        out = _safe_json_for_html(data)
        assert "<!--" not in out

    def test_round_trips_through_json_parse(self):
        # The escaped sequences are valid JSON — parsing should yield the original
        data = {"a": "</script>", "b": "<!-- "}
        out = _safe_json_for_html(data)
        parsed = json.loads(out)
        assert parsed == data


class TestWriteOutput:
    def _sample_item(self):
        return {
            "id": "x", "instance_id": "i", "title": "T",
            "author": "A", "publisher": "P", "year": "2024",
            "receipt_date": "2024-01-15", "type_uuid": "u",
            "type_label": "Books", "subject_group": "",
            "call_number": "", "cover_url": None,
            "placeholder_color": "#2a5e8c", "eds_url": None,
            "isbn": None, "oclc": None,
        }

    def test_writes_assets_and_json(self, tmp_path):
        out_html = tmp_path / "out" / "new-materials.html"
        env = build_data_envelope(
            [self._sample_item()], "2024-01-01", "2024-01-31", "now", "Lib",
        )
        write_output("<html></html>", str(out_html), envelope=env)

        assert out_html.exists()
        assert (out_html.parent / "assets" / "styles.css").exists()
        assert (out_html.parent / "assets" / "app.js").exists()
        assert (out_html.parent / "data" / "items.json").exists()

    def test_json_file_is_valid_json(self, tmp_path):
        out_html = tmp_path / "out" / "new-materials.html"
        env = build_data_envelope(
            [self._sample_item()], "2024-01-01", "2024-01-31", "now", "Lib",
        )
        write_output("<html></html>", str(out_html), envelope=env)

        data = json.loads((out_html.parent / "data" / "items.json").read_text())
        assert data["total_count"] == 1
        assert data["items"][0]["title"] == "T"

    def test_skips_assets_when_no_envelope(self, tmp_path):
        out_html = tmp_path / "out" / "new-materials.html"
        write_output("<html></html>", str(out_html))
        assert out_html.exists()
        assert not (out_html.parent / "assets").exists()
