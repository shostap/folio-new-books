"""Tests for src/google_images.py — Google Books viewapi integration."""

from unittest.mock import MagicMock

import pytest
import responses as resp_lib

from src.google_images import (
    fetch_cover_image,
    _google_books_lookup,
    _parse_google_books_response,
    GOOGLE_BOOKS_URL,
)

# Sample response text as returned by the Google Books viewapi
_SAMPLE_RESPONSE = (
    'var _GBSBookInfo = {"ISBN:9780735619678":{'
    '"bib_key":"ISBN:9780735619678",'
    '"info_url":"https://books.google.com/books?id=abc",'
    '"preview_url":"https://books.google.com/books?id=abc&printsec=frontcover",'
    '"thumbnail_url":"https://books.google.com/books/content?id=abc&zoom=1",'
    '"preview":"noview","embeddable":false}};'
)

_EMPTY_RESPONSE = "var _GBSBookInfo = {};"


def _config(enabled=True):
    cfg = MagicMock()
    cfg.google_enabled = enabled
    return cfg


# ── Response parser ───────────────────────────────────────────────────


class TestParseGoogleBooksResponse:
    def test_parses_standard_response(self):
        data = _parse_google_books_response(_SAMPLE_RESPONSE)
        assert "ISBN:9780735619678" in data
        assert data["ISBN:9780735619678"]["thumbnail_url"].startswith("https://")

    def test_empty_response_returns_empty_dict(self):
        assert _parse_google_books_response(_EMPTY_RESPONSE) == {}

    def test_whitespace_only_returns_empty_dict(self):
        assert _parse_google_books_response("   ") == {}

    def test_handles_missing_wrapper(self):
        # Some clients might return raw JSON
        assert _parse_google_books_response('{"key": {"thumbnail_url": "x"}}') == {
            "key": {"thumbnail_url": "x"}
        }


# ── Google Books lookup ───────────────────────────────────────────────


class TestGoogleBooksLookup:
    @resp_lib.activate
    def test_returns_thumbnail_for_isbn(self):
        resp_lib.add(
            resp_lib.GET,
            GOOGLE_BOOKS_URL,
            body=_SAMPLE_RESPONSE,
            status=200,
            content_type="text/javascript",
        )
        result = _google_books_lookup("ISBN", "9780735619678")
        assert result == "https://books.google.com/books/content?id=abc&zoom=1"

    @resp_lib.activate
    def test_returns_none_when_no_thumbnail(self):
        # Book found but no thumbnail_url
        resp_lib.add(
            resp_lib.GET,
            GOOGLE_BOOKS_URL,
            body='var _GBSBookInfo = {"ISBN:0000000000":{"bib_key":"ISBN:0000000000"}};',
            status=200,
        )
        result = _google_books_lookup("ISBN", "0000000000")
        assert result is None

    @resp_lib.activate
    def test_returns_none_for_empty_response(self):
        resp_lib.add(resp_lib.GET, GOOGLE_BOOKS_URL, body=_EMPTY_RESPONSE, status=200)
        result = _google_books_lookup("ISBN", "9999999999999")
        assert result is None

    @resp_lib.activate
    def test_returns_none_on_http_error(self):
        resp_lib.add(resp_lib.GET, GOOGLE_BOOKS_URL, status=500)
        result = _google_books_lookup("ISBN", "9780735619678")
        assert result is None

    @resp_lib.activate
    def test_strips_hyphens_from_isbn(self):
        resp_lib.add(resp_lib.GET, GOOGLE_BOOKS_URL, body=_EMPTY_RESPONSE, status=200)
        _google_books_lookup("ISBN", "978-0-7356-1967-8")
        sent_url = resp_lib.calls[0].request.url
        assert "978-0-7356-1967-8" not in sent_url
        assert "9780735619678" in sent_url

    @resp_lib.activate
    def test_strips_non_digits_from_oclc(self):
        resp_lib.add(resp_lib.GET, GOOGLE_BOOKS_URL, body=_EMPTY_RESPONSE, status=200)
        _google_books_lookup("OCLC", "(OCoLC)12345678")
        sent_url = resp_lib.calls[0].request.url
        assert "12345678" in sent_url
        assert "OCoLC" not in sent_url

    def test_returns_none_for_empty_value(self):
        result = _google_books_lookup("ISBN", "")
        assert result is None


# ── Orchestration ─────────────────────────────────────────────────────


class TestFetchCoverImage:
    @resp_lib.activate
    def test_uses_isbn_first(self):
        resp_lib.add(
            resp_lib.GET, GOOGLE_BOOKS_URL,
            body=_SAMPLE_RESPONSE, status=200,
        )
        result = fetch_cover_image(isbn="9780735619678", oclc="12345678")
        assert result is not None
        # Only one request should be made (ISBN succeeded)
        assert len(resp_lib.calls) == 1
        assert "ISBN" in resp_lib.calls[0].request.url

    @resp_lib.activate
    def test_falls_back_to_oclc_when_isbn_misses(self):
        # First call (ISBN) returns empty; second call (OCLC) returns result
        oclc_response = (
            'var _GBSBookInfo = {"OCLC:12345678":{'
            '"thumbnail_url":"https://books.google.com/content?oclc=12345678"}};'
        )
        resp_lib.add(resp_lib.GET, GOOGLE_BOOKS_URL, body=_EMPTY_RESPONSE, status=200)
        resp_lib.add(resp_lib.GET, GOOGLE_BOOKS_URL, body=oclc_response, status=200)

        result = fetch_cover_image(isbn="0000000000", oclc="12345678")
        assert result == "https://books.google.com/content?oclc=12345678"

    @resp_lib.activate
    def test_returns_none_when_both_identifiers_miss(self):
        resp_lib.add(resp_lib.GET, GOOGLE_BOOKS_URL, body=_EMPTY_RESPONSE, status=200)
        resp_lib.add(resp_lib.GET, GOOGLE_BOOKS_URL, body=_EMPTY_RESPONSE, status=200)
        result = fetch_cover_image(isbn="0000000000", oclc="99999999")
        assert result is None

    def test_returns_none_when_disabled_via_config(self):
        result = fetch_cover_image(isbn="9780735619678", config=_config(enabled=False))
        assert result is None

    def test_returns_none_when_no_identifiers(self):
        result = fetch_cover_image(isbn=None, oclc=None)
        assert result is None
