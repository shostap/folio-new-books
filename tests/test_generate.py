"""Tests for the entry-point helpers in generate.py."""

import argparse
from unittest.mock import MagicMock

from generate import (
    _slugify,
    _write_per_type_pages,
    _resolve_log_file,
    _warn_on_placeholder_config,
)


# ── _slugify ─────────────────────────────────────────────────────────


class TestSlugify:
    def test_simple_lowercase(self):
        assert _slugify("Books") == "books"

    def test_space_to_hyphen(self):
        assert _slugify("Music CD") == "music-cd"

    def test_strips_punctuation(self):
        assert _slugify("Audio/Visual Material!") == "audiovisual-material"

    def test_collapses_consecutive_separators(self):
        assert _slugify("Foo   Bar___Baz") == "foo-bar-baz"

    def test_empty_falls_back_to_other(self):
        assert _slugify("") == "other"
        assert _slugify(None) == "other"


# ── per-type fan-out ──────────────────────────────────────────────────


def _config_for_per_type():
    cfg = MagicMock()
    cfg.primary_color = "#003366"
    cfg.accent_color = "#ffffff"
    cfg.eds_enabled = False
    cfg.output_title = "New Materials"
    cfg.institution_name = "Test Library"
    cfg.institution_logo_url = ""
    cfg.subject_groups = {}
    cfg.lcc_grouping = False
    cfg.default_view = "grid"
    cfg.holdings_display = "summary"
    cfg.material_types = {}
    return cfg


def _item(type_uuid, type_label):
    return {
        "id": "i", "instance_id": "x", "title": "T",
        "author": "A", "publisher": "", "year": "",
        "receipt_date": "2026-04-01",
        "type_uuid": type_uuid, "type_label": type_label,
        "subject_group": "", "subjects": [],
        "call_number": "", "holdings": [],
        "cover_url": None, "placeholder_color": "#2a5e8c",
        "eds_url": None, "isbn": None, "oclc": None,
    }


class TestWritePerTypePages:
    def test_writes_one_file_per_type(self, tmp_path):
        items = [
            _item("uuid-books", "Books"),
            _item("uuid-books", "Books"),
            _item("uuid-dvd",   "DVD"),
        ]
        cfg = _config_for_per_type()
        out = tmp_path / "out" / "new-materials.html"

        envelope = {"items": items, "total_count": 3,
                    "generated_at": "now",
                    "date_range": {"start": "2026-04-01", "end": "2026-05-01"},
                    "institution": "Test Library"}

        count = _write_per_type_pages(
            items=items, config=cfg, material_type_map={},
            output_path=str(out),
            start_date="2026-04-01", end_date="2026-05-01",
            generated_at="now", envelope_full=envelope,
            log=MagicMock(),
        )
        assert count == 2

        out_dir = out.parent
        assert (out_dir / "new-books.html").exists()
        assert (out_dir / "new-dvd.html").exists()
        # Shared assets and data feed written exactly once
        assert (out_dir / "assets" / "styles.css").exists()
        assert (out_dir / "data" / "items.json").exists()

    def test_combined_data_feed_has_all_items(self, tmp_path):
        import json
        items = [_item("uuid-books", "Books"), _item("uuid-dvd", "DVD")]
        cfg = _config_for_per_type()
        out = tmp_path / "out" / "new-materials.html"
        envelope = {"items": items, "total_count": 2,
                    "generated_at": "now",
                    "date_range": {"start": "2026-04-01", "end": "2026-05-01"},
                    "institution": "Test Library"}

        _write_per_type_pages(
            items=items, config=cfg, material_type_map={},
            output_path=str(out),
            start_date="2026-04-01", end_date="2026-05-01",
            generated_at="now", envelope_full=envelope,
            log=MagicMock(),
        )
        data = json.loads((out.parent / "data" / "items.json").read_text())
        assert data["total_count"] == 2


# ── _resolve_log_file ────────────────────────────────────────────────


def _ns(**kwargs):
    return argparse.Namespace(**kwargs)


class TestResolveLogFile:
    def test_cli_wins_over_config(self):
        cfg = MagicMock()
        cfg.log_file = "logs/from-config.log"
        path = _resolve_log_file(_ns(log_file="/var/log/custom.log"), cfg)
        assert path == "/var/log/custom.log"

    def test_falls_back_to_config_when_no_cli(self):
        cfg = MagicMock()
        cfg.log_file = "logs/from-config.log"
        path = _resolve_log_file(_ns(log_file=None), cfg)
        assert path == "logs/from-config.log"

    def test_cli_none_disables_file_logging(self):
        cfg = MagicMock()
        cfg.log_file = "logs/from-config.log"
        assert _resolve_log_file(_ns(log_file="none"), cfg) is None
        assert _resolve_log_file(_ns(log_file="no"), cfg) is None
        assert _resolve_log_file(_ns(log_file=""), cfg) is None

    def test_config_none_disables_file_logging(self):
        cfg = MagicMock()
        cfg.log_file = "none"
        assert _resolve_log_file(_ns(log_file=None), cfg) is None


# ── _warn_on_placeholder_config ──────────────────────────────────────


def _placeholder_config(an_prefix, base_url="https://api.example.com",
                         username="real_user", password="real_pass"):
    cfg = MagicMock()
    cfg.eds_an_prefix = an_prefix
    cfg.folio_base_url = base_url
    cfg.folio_username = username
    cfg.folio_password = password
    return cfg


class TestPlaceholderWarning:
    def test_warns_when_an_prefix_still_says_example(self):
        log = MagicMock()
        cfg = _placeholder_config("scf.oai.edge.example.folio.ebsco.com.fs00001006")
        _warn_on_placeholder_config(cfg, log)
        # At least one warning was logged, mentioning the offending key
        assert log.warning.called
        warning_args = " ".join(str(a) for a in log.warning.call_args.args)
        assert "an_prefix" in warning_args
        assert "example" in warning_args

    def test_no_warning_when_prefix_is_real(self):
        log = MagicMock()
        cfg = _placeholder_config("scf.oai.edge.fivecolleges.folio.ebsco.com.fs00001006")
        _warn_on_placeholder_config(cfg, log)
        assert not log.warning.called

    def test_warns_on_default_credentials(self):
        log = MagicMock()
        cfg = _placeholder_config(
            "scf.oai.edge.fivecolleges.folio.ebsco.com.fs00001006",
            username="your_username",
        )
        _warn_on_placeholder_config(cfg, log)
        assert log.warning.called
