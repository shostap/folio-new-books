"""Configuration loading and validation for FOLIO New Materials."""

import configparser
import logging
from pathlib import Path

from src.subjects import parse_groups_config

logger = logging.getLogger(__name__)

# Keys inside [subject_groups] that are NOT actual group names but flags
# controlling the grouping mode.  Filtered out before manual-group parsing.
_RESERVED_GROUP_KEYS = {"lcc_grouping", "auto_group"}


class ConfigError(Exception):
    """Raised when a required configuration value is missing or invalid."""


class Config:
    """
    Loads and exposes settings from a .ini file.

    Required sections and keys:
        [folio] base_url, username, password
    All other values have defaults documented in config.ini.example.
    """

    def __init__(self, config_path: str = "config.ini") -> None:
        path = Path(config_path)
        if not path.exists():
            raise ConfigError(
                f"Config file not found: {config_path}\n"
                "Copy config.ini.example to config.ini and fill in your values."
            )
        self._parser = configparser.ConfigParser()
        # Preserve case in keys so subject-group names like "Engineering"
        # are not lowercased.  Standard config keys (base_url, etc.) are
        # written lowercase by convention, so this is safe.
        self._parser.optionxform = str
        self._parser.read(config_path)
        self._validate()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        required = [
            ("folio", "base_url"),
            ("folio", "username"),
            ("folio", "password"),
        ]
        for section, key in required:
            if not self._get(section, key):
                raise ConfigError(f"Missing required config: [{section}] {key}")

    def _get(self, section: str, key: str, fallback: str = "") -> str:
        return self._parser.get(section, key, fallback=fallback).strip()

    # ------------------------------------------------------------------
    # FOLIO
    # ------------------------------------------------------------------

    @property
    def folio_base_url(self) -> str:
        return self._get("folio", "base_url").rstrip("/")

    @property
    def folio_tenant(self) -> str:
        return self._get("folio", "tenant", "fs00001006")

    @property
    def folio_username(self) -> str:
        return self._get("folio", "username")

    @property
    def folio_password(self) -> str:
        return self._get("folio", "password")

    @property
    def folio_edge_api(self) -> str:
        return self._get("folio", "edge_api").rstrip("/")

    @property
    def folio_edge_api_key(self) -> str:
        return self._get("folio", "edge_api_key")

    @property
    def edge_enabled(self) -> bool:
        """Edge RTAC is only used when both the URL and API key are set."""
        return bool(self.folio_edge_api and self.folio_edge_api_key)

    # ------------------------------------------------------------------
    # EDS
    # ------------------------------------------------------------------

    @property
    def eds_db_id(self) -> str:
        return self._get("eds", "db_id")

    @property
    def eds_catalog_db(self) -> str:
        return self._get("eds", "catalog_db")

    @property
    def eds_an_prefix(self) -> str:
        return self._get("eds", "an_prefix")

    @property
    def eds_an_separator(self) -> str:
        """Either 'dots' (default) or 'dashes' for UUID formatting in EDS links."""
        return self._get("eds", "an_separator", "dots")

    @property
    def eds_enabled(self) -> bool:
        return bool(self.eds_db_id and self.eds_catalog_db and self.eds_an_prefix)

    @property
    def eds_link_strategy(self) -> str:
        """
        How to build EDS deep links: ``openurl`` (default) or ``search``.

        ``openurl`` — OpenURL with the FOLIO access number as the primary id,
        plus rft.isbn / rft.oclc as supplementary identifiers.  EDS resolves
        the AN first (works for indexed records), then falls back to ISBN
        or OCLC lookup.  Single click to the catalog record when it works.

        ``search`` — Direct EDS Discovery search URL (research.ebsco.com)
        keyed on ISBN, OCLC, or title.  Always lands on a results page so
        the patron is never staring at a broken link, at the cost of an
        extra click to pick the right record.
        """
        raw = self._get("eds", "link_strategy", "openurl").lower()
        return raw if raw in ("openurl", "search") else "openurl"

    # ------------------------------------------------------------------
    # Google
    # ------------------------------------------------------------------

    @property
    def google_enabled(self) -> bool:
        """True unless explicitly set to false/0/no in [google] enabled."""
        raw = self._get("google", "enabled", "true").lower()
        return raw not in ("false", "0", "no")

    # ------------------------------------------------------------------
    # TMDB
    # ------------------------------------------------------------------

    @property
    def tmdb_api_key(self) -> str:
        return self._get("tmdb", "api_key")

    @property
    def tmdb_poster_size(self) -> str:
        """TMDB image size slug: w185, w342, w500, w780, original."""
        return self._get("tmdb", "poster_size", "w500")

    @property
    def tmdb_enabled(self) -> bool:
        return bool(self.tmdb_api_key)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    @property
    def output_days(self) -> int:
        try:
            return int(self._get("output", "days", "30"))
        except ValueError:
            return 30

    @property
    def output_file(self) -> str:
        return self._get("output", "output_file", "output/new-materials.html")

    @property
    def output_title(self) -> str:
        return self._get("output", "title", "New Materials")

    @property
    def institution_name(self) -> str:
        return self._get("output", "institution_name", "Library")

    @property
    def institution_logo_url(self) -> str:
        return self._get("output", "logo_url")

    @property
    def primary_color(self) -> str:
        return self._get("output", "primary_color", "#003366")

    @property
    def accent_color(self) -> str:
        return self._get("output", "accent_color", "#ffffff")

    @property
    def default_view(self) -> str:
        """Initial view when the user has no saved preference: 'grid' or 'table'."""
        raw = self._get("output", "default_view", "grid").lower()
        return raw if raw in ("grid", "table") else "grid"

    @property
    def holdings_display(self) -> str:
        """How richly to render multi-holding items: none | compact | summary | detailed."""
        raw = self._get("output", "holdings_display", "summary").lower()
        return raw if raw in ("none", "compact", "summary", "detailed") else "summary"

    @property
    def log_file(self) -> str:
        """
        Path to the log file (relative paths resolve against the cwd of the
        cron job).  Defaults to ``logs/folio-new-books.log``.

        Set to an empty string or ``none`` / ``false`` to disable file
        logging (console-only).
        """
        return self._get("output", "log_file", "logs/folio-new-books.log")

    @property
    def pages_per_type(self) -> bool:
        """
        When true, generate one HTML page per material type instead of one
        combined page with a format dropdown.  Useful for staff who want
        a shareable per-format list (e.g. new-books.html, new-dvds.html).
        Uses [material_types] when set; otherwise the types discovered in
        the data.
        """
        raw = self._get("output", "pages_per_type", "false").lower()
        return raw in ("true", "1", "yes")

    # ------------------------------------------------------------------
    # Material types
    # ------------------------------------------------------------------

    @property
    def material_types(self) -> dict[str, str]:
        """
        Returns an ordered dict mapping material-type UUID to display label.
        An empty dict means: query all types without UUID filtering.
        """
        if not self._parser.has_section("material_types"):
            return {}
        return {
            k: v
            for k, v in self._parser.items("material_types")
            if k and v and not k.startswith("#")
        }

    # ------------------------------------------------------------------
    # Subject groups
    # ------------------------------------------------------------------

    @property
    def subject_groups(self) -> dict[str, list[str]]:
        """
        Returns a map of group name → list of keywords.
        Used to classify items by subject heading for grouped display.

        Reserved flag keys (``lcc_grouping``, ``auto_group``) are filtered
        out so they cannot accidentally become a manual group with a single
        keyword ``true`` — a subtle config-compatibility bug we hit when
        renaming auto_group → lcc_grouping.
        """
        if not self._parser.has_section("subject_groups"):
            return {}
        raw = {
            k: v for k, v in self._parser.items("subject_groups")
            if k.lower() not in _RESERVED_GROUP_KEYS
        }
        return parse_groups_config(raw)

    @property
    def lcc_grouping(self) -> bool:
        """
        Enable Library-of-Congress-class subject grouping derived from call
        numbers via longest-prefix lookup (see static/lcc-classes.json).

        Honours the legacy key ``auto_group = true`` as an alias so older
        config files keep working; logs a deprecation notice on first read.
        """
        if not self._parser.has_section("subject_groups"):
            return False

        new_val = self._parser.get(
            "subject_groups", "lcc_grouping", fallback=""
        ).strip().lower()
        if new_val in ("true", "1", "yes"):
            return True

        legacy_val = self._parser.get(
            "subject_groups", "auto_group", fallback=""
        ).strip().lower()
        if legacy_val in ("true", "1", "yes"):
            logger.warning(
                "[subject_groups] auto_group is deprecated — "
                "rename it to 'lcc_grouping' in your config.ini"
            )
            return True

        return False
