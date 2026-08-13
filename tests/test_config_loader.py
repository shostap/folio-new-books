"""Tests for src/config_loader.py."""

import configparser
import textwrap
from pathlib import Path

import pytest

from src.config_loader import Config, ConfigError


# ── Fixtures ─────────────────────────────────────────────────────────


def _write_config(tmp_path: Path, content: str) -> str:
    """Write an INI string to a temp file and return its path."""
    p = tmp_path / "config.ini"
    p.write_text(textwrap.dedent(content))
    return str(p)


MINIMAL_CONFIG = """
    [folio]
    base_url = https://api.example.com
    username = testuser
    password = testpass
"""

FULL_CONFIG = """
    [folio]
    base_url    = https://api.example.com
    tenant      = mytenant
    username    = testuser
    password    = testpass
    edge_api    = https://edge.example.com/

    [eds]
    db_id       = abcdef
    catalog_db  = cat12345
    an_prefix   = scf.oai.edge.example.com.tenant01
    an_separator = dots

    [google]
    enabled = true

    [tmdb]
    api_key     = TMDB_KEY
    poster_size = w342

    [output]
    days            = 14
    output_file     = /tmp/new-materials.html
    title           = New Books
    institution_name = Test Library
    logo_url        = https://example.com/logo.png
    primary_color   = #cc0000
    accent_color    = #ffeeee

    [material_types]
    2d72aa13-2451-41fe-afc7-b3dc7c131389 = Books
    faa0cd0a-e408-4b57-acff-1c3f9171723d = DVD
"""


# ── Positive tests ────────────────────────────────────────────────────


class TestMinimalConfig:
    def setup_method(self, _, tmp_path=None):
        # pytest passes tmp_path via fixture, not setup_method
        pass

    def test_loads_required_values(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.folio_base_url == "https://api.example.com"
        assert cfg.folio_username == "testuser"
        assert cfg.folio_password == "testpass"

    def test_default_tenant(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.folio_tenant == "fs00001006"

    def test_default_days(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.output_days == 30

    def test_google_enabled_by_default(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.google_enabled is True

    def test_eds_disabled_when_not_configured(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert not cfg.eds_enabled

    def test_material_types_empty_by_default(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.material_types == {}

    def test_tmdb_disabled_when_not_configured(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.tmdb_enabled is False

    def test_subject_groups_empty_by_default(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.subject_groups == {}

    def test_default_view_is_grid(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.default_view == "grid"

    def test_default_view_falls_back_to_grid_on_invalid(self, tmp_path):
        content = MINIMAL_CONFIG + "\n[output]\ndefault_view = nonsense\n"
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.default_view == "grid"

    def test_subject_groups_parses_keywords(self, tmp_path):
        content = MINIMAL_CONFIG + (
            "\n[subject_groups]\n"
            "Engineering = computer, programming\n"
            "Sciences = biology, chemistry\n"
        )
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.subject_groups == {
            "Engineering": ["computer", "programming"],
            "Sciences": ["biology", "chemistry"],
        }

    def test_lcc_grouping_false_by_default(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.lcc_grouping is False

    def test_lcc_grouping_true_when_set(self, tmp_path):
        content = MINIMAL_CONFIG + "\n[subject_groups]\nlcc_grouping = true\n"
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.lcc_grouping is True

    def test_lcc_grouping_key_excluded_from_groups_dict(self, tmp_path):
        content = MINIMAL_CONFIG + (
            "\n[subject_groups]\n"
            "lcc_grouping = false\n"
            "Engineering = computer\n"
        )
        cfg = Config(_write_config(tmp_path, content))
        assert "lcc_grouping" not in cfg.subject_groups
        assert cfg.subject_groups == {"Engineering": ["computer"]}

    def test_pages_per_type_false_by_default(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.pages_per_type is False

    def test_pages_per_type_true_when_set(self, tmp_path):
        content = MINIMAL_CONFIG + "\n[output]\npages_per_type = true\n"
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.pages_per_type is True

    def test_auto_group_back_compat_enables_lcc(self, tmp_path):
        """Regression: legacy auto_group = true should map to lcc_grouping."""
        content = MINIMAL_CONFIG + "\n[subject_groups]\nauto_group = true\n"
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.lcc_grouping is True

    def test_auto_group_filtered_from_manual_groups(self, tmp_path):
        """Regression: auto_group must not become a fake manual group."""
        content = MINIMAL_CONFIG + "\n[subject_groups]\nauto_group = true\n"
        cfg = Config(_write_config(tmp_path, content))
        # The bug: auto_group would parse as a manual group {"auto_group": ["true"]}
        # and short-circuit everything to "Other"
        assert cfg.subject_groups == {}

    def test_log_file_default(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.log_file == "logs/folio-new-books.log"

    def test_log_file_can_be_disabled(self, tmp_path):
        content = MINIMAL_CONFIG + "\n[output]\nlog_file = none\n"
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.log_file == "none"

    def test_log_file_custom_path(self, tmp_path):
        content = MINIMAL_CONFIG + "\n[output]\nlog_file = /var/log/folio.log\n"
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.log_file == "/var/log/folio.log"

    def test_edge_disabled_when_no_key(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.edge_enabled is False
        assert cfg.folio_edge_api_key == ""

    def test_edge_enabled_when_url_and_key_set(self, tmp_path):
        content = MINIMAL_CONFIG + (
            "\n[folio]\n"
            "edge_api = https://edge.example.com\n"
            "edge_api_key = secret-key\n"
        )
        # Re-using [folio] section in a tmp INI works because configparser merges
        # — but for cleanliness rewrite minimal config inline:
        content = (
            "[folio]\n"
            "base_url = https://api.example.com\n"
            "username = u\n"
            "password = p\n"
            "edge_api = https://edge.example.com/\n"
            "edge_api_key = secret-key\n"
        )
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.edge_enabled is True
        assert cfg.folio_edge_api == "https://edge.example.com"
        assert cfg.folio_edge_api_key == "secret-key"

    def test_holdings_display_default(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.holdings_display == "summary"

    def test_holdings_display_accepts_valid_values(self, tmp_path):
        for mode in ("none", "compact", "summary", "detailed"):
            content = MINIMAL_CONFIG + f"\n[output]\nholdings_display = {mode}\n"
            cfg = Config(_write_config(tmp_path, content))
            assert cfg.holdings_display == mode

    def test_holdings_display_invalid_falls_back_to_summary(self, tmp_path):
        content = MINIMAL_CONFIG + "\n[output]\nholdings_display = bogus\n"
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.holdings_display == "summary"


class TestFullConfig:
    def test_folio_values(self, tmp_path):
        cfg = Config(_write_config(tmp_path, FULL_CONFIG))
        assert cfg.folio_tenant == "mytenant"
        # Trailing slash on edge_api should be stripped
        assert cfg.folio_edge_api == "https://edge.example.com"

    def test_eds_values(self, tmp_path):
        cfg = Config(_write_config(tmp_path, FULL_CONFIG))
        assert cfg.eds_db_id == "abcdef"
        assert cfg.eds_catalog_db == "cat12345"
        assert cfg.eds_an_prefix == "scf.oai.edge.example.com.tenant01"
        assert cfg.eds_an_separator == "dots"
        assert cfg.eds_enabled is True

    def test_eds_link_strategy_default(self, tmp_path):
        cfg = Config(_write_config(tmp_path, MINIMAL_CONFIG))
        assert cfg.eds_link_strategy == "openurl"

    def test_eds_link_strategy_search(self, tmp_path):
        content = MINIMAL_CONFIG + "\n[eds]\nlink_strategy = search\n"
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.eds_link_strategy == "search"

    def test_eds_link_strategy_invalid_falls_back(self, tmp_path):
        content = MINIMAL_CONFIG + "\n[eds]\nlink_strategy = bogus\n"
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.eds_link_strategy == "openurl"

    def test_google_enabled_true(self, tmp_path):
        cfg = Config(_write_config(tmp_path, FULL_CONFIG))
        assert cfg.google_enabled is True

    def test_google_disabled_when_false(self, tmp_path):
        content = MINIMAL_CONFIG + "\n[google]\nenabled = false\n"
        cfg = Config(_write_config(tmp_path, content))
        assert cfg.google_enabled is False

    def test_tmdb_values(self, tmp_path):
        cfg = Config(_write_config(tmp_path, FULL_CONFIG))
        assert cfg.tmdb_api_key == "TMDB_KEY"
        assert cfg.tmdb_poster_size == "w342"
        assert cfg.tmdb_enabled is True

    def test_output_values(self, tmp_path):
        cfg = Config(_write_config(tmp_path, FULL_CONFIG))
        assert cfg.output_days == 14
        assert cfg.output_file == "/tmp/new-materials.html"
        assert cfg.output_title == "New Books"
        assert cfg.institution_name == "Test Library"
        assert cfg.institution_logo_url == "https://example.com/logo.png"
        assert cfg.primary_color == "#cc0000"
        assert cfg.accent_color == "#ffeeee"

    def test_material_types(self, tmp_path):
        cfg = Config(_write_config(tmp_path, FULL_CONFIG))
        types = cfg.material_types
        assert len(types) == 2
        assert types["2d72aa13-2451-41fe-afc7-b3dc7c131389"] == "Books"
        assert types["faa0cd0a-e408-4b57-acff-1c3f9171723d"] == "DVD"


# ── Error tests ───────────────────────────────────────────────────────


def test_raises_when_file_missing():
    with pytest.raises(ConfigError, match="not found"):
        Config("/nonexistent/config.ini")


def test_raises_when_base_url_missing(tmp_path):
    content = "[folio]\nusername = u\npassword = p\n"
    with pytest.raises(ConfigError, match="base_url"):
        Config(_write_config(tmp_path, content))


def test_raises_when_username_missing(tmp_path):
    content = "[folio]\nbase_url = https://x.com\npassword = p\n"
    with pytest.raises(ConfigError, match="username"):
        Config(_write_config(tmp_path, content))


def test_raises_when_password_missing(tmp_path):
    content = "[folio]\nbase_url = https://x.com\nusername = u\n"
    with pytest.raises(ConfigError, match="password"):
        Config(_write_config(tmp_path, content))


def test_invalid_days_falls_back_to_default(tmp_path):
    content = MINIMAL_CONFIG + "\n[output]\ndays = notanumber\n"
    cfg = Config(_write_config(tmp_path, content))
    assert cfg.output_days == 30
