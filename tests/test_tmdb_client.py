"""Tests for src/tmdb_client.py."""

import pytest
import responses as resp_lib

from src.tmdb_client import (
    fetch_tmdb_poster,
    _tmdb_multi_search,
    _best_match,
    _title_similarity,
    TMDB_BASE_URL,
    TMDB_IMAGE_BASE,
    TMDB_DEFAULT_POSTER_SIZE,
)

_API_KEY = "test-api-key"
_SEARCH_URL = f"{TMDB_BASE_URL}/search/multi"

# Sample TMDB API responses
_MOVIE_RESULT = {
    "id": 11,
    "title": "Star Wars",
    "media_type": "movie",
    "poster_path": "/btTdmkgIvOi0FFip1sPuZI2oQG6.jpg",
    "release_date": "1977-05-25",
}

_TV_RESULT = {
    "id": 99,
    "name": "The Office",
    "media_type": "tv",
    "poster_path": "/qWnJzyZhyy74gjpSjIXWmuk0ifX.jpg",
}

_PERSON_RESULT = {
    "id": 200,
    "name": "Some Person",
    "media_type": "person",
    "poster_path": None,
}


def _search_response(*results):
    return {
        "page": 1,
        "total_results": len(results),
        "total_pages": 1,
        "results": list(results),
    }


# ── Title similarity ──────────────────────────────────────────────────


class TestTitleSimilarity:
    def test_exact_match_scores_100(self):
        assert _title_similarity("Star Wars", "Star Wars") == 100

    def test_case_insensitive_exact_match(self):
        assert _title_similarity("star wars", "Star Wars") == 100

    def test_normalised_exact_match(self):
        # Punctuation stripped before comparison
        assert _title_similarity("Star Wars!", "Star Wars") == 100

    def test_substring_match_scores_75_minus_diff(self):
        # "StarWars" (8 chars) is in "StarWarsANewHope" (16 chars) → 75 - 8 = 67
        score = _title_similarity("Star Wars", "Star Wars: A New Hope")
        assert score == 75 - abs(len("StarWars") - len("StarWarsANewHope"))

    def test_no_match_scores_zero(self):
        assert _title_similarity("Casablanca", "Jurassic Park") == 0

    def test_empty_query_scores_zero(self):
        assert _title_similarity("", "Star Wars") == 0

    def test_empty_title_scores_zero(self):
        assert _title_similarity("Star Wars", "") == 0

    def test_long_title_can_produce_negative_score(self):
        # Very long title → length diff > 75 → negative score
        long_title = "Star Wars " + "x" * 100
        score = _title_similarity("Star Wars", long_title)
        assert score < 0


# ── Best match selection ──────────────────────────────────────────────


class TestBestMatch:
    def test_exact_match_wins_over_substring(self):
        exact = {"title": "Star Wars", "media_type": "movie", "poster_path": "/a.jpg"}
        sub = {"title": "Star Wars: A New Hope", "media_type": "movie", "poster_path": "/b.jpg"}
        assert _best_match("Star Wars", [sub, exact]) is exact

    def test_returns_highest_scoring_result(self):
        close = {"title": "The Office", "media_type": "tv", "poster_path": "/a.jpg"}
        far = {"title": "Office Space Something Longer", "media_type": "movie", "poster_path": "/b.jpg"}
        result = _best_match("The Office", [far, close])
        assert result is close

    def test_returns_none_when_no_positive_score(self):
        unrelated = [
            {"title": "Completely Different Film", "media_type": "movie", "poster_path": "/x.jpg"},
        ]
        assert _best_match("Casablanca", unrelated) is None

    def test_returns_none_for_empty_list(self):
        assert _best_match("Any Title", []) is None

    def test_uses_name_field_for_tv(self):
        tv = {"name": "The Office", "media_type": "tv", "poster_path": "/a.jpg"}
        assert _best_match("The Office", [tv]) is tv


# ── TMDB multi-search ─────────────────────────────────────────────────


class TestTmdbMultiSearch:
    @resp_lib.activate
    def test_returns_results_list(self):
        resp_lib.add(
            resp_lib.GET, _SEARCH_URL,
            json=_search_response(_MOVIE_RESULT),
            status=200,
        )
        results = _tmdb_multi_search("Star Wars", _API_KEY)
        assert len(results) == 1
        assert results[0]["title"] == "Star Wars"

    @resp_lib.activate
    def test_returns_empty_list_on_http_error(self):
        resp_lib.add(resp_lib.GET, _SEARCH_URL, status=401)
        assert _tmdb_multi_search("Star Wars", _API_KEY) == []

    @resp_lib.activate
    def test_api_key_included_in_request(self):
        resp_lib.add(resp_lib.GET, _SEARCH_URL, json=_search_response(), status=200)
        _tmdb_multi_search("Star Wars", _API_KEY)
        assert f"api_key={_API_KEY}" in resp_lib.calls[0].request.url


# ── fetch_tmdb_poster ─────────────────────────────────────────────────


class TestFetchTmdbPoster:
    @resp_lib.activate
    def test_returns_poster_url_for_movie(self):
        resp_lib.add(
            resp_lib.GET, _SEARCH_URL,
            json=_search_response(_MOVIE_RESULT),
            status=200,
        )
        result = fetch_tmdb_poster("Star Wars", _API_KEY)
        expected = (
            f"{TMDB_IMAGE_BASE}/{TMDB_DEFAULT_POSTER_SIZE}"
            f"{_MOVIE_RESULT['poster_path']}"
        )
        assert result == expected

    @resp_lib.activate
    def test_returns_poster_url_for_tv(self):
        resp_lib.add(
            resp_lib.GET, _SEARCH_URL,
            json=_search_response(_TV_RESULT),
            status=200,
        )
        result = fetch_tmdb_poster("The Office", _API_KEY)
        assert result is not None
        assert _TV_RESULT["poster_path"] in result

    @resp_lib.activate
    def test_filters_out_person_results(self):
        resp_lib.add(
            resp_lib.GET, _SEARCH_URL,
            json=_search_response(_PERSON_RESULT),
            status=200,
        )
        result = fetch_tmdb_poster("Some Person", _API_KEY)
        assert result is None

    @resp_lib.activate
    def test_respects_custom_poster_size(self):
        resp_lib.add(
            resp_lib.GET, _SEARCH_URL,
            json=_search_response(_MOVIE_RESULT),
            status=200,
        )
        result = fetch_tmdb_poster("Star Wars", _API_KEY, poster_size="w185")
        assert result.startswith(f"{TMDB_IMAGE_BASE}/w185")

    def test_returns_none_when_no_api_key(self):
        assert fetch_tmdb_poster("Star Wars", "") is None

    def test_returns_none_when_no_title(self):
        assert fetch_tmdb_poster("", _API_KEY) is None

    @resp_lib.activate
    def test_returns_none_when_no_results(self):
        resp_lib.add(
            resp_lib.GET, _SEARCH_URL,
            json=_search_response(),
            status=200,
        )
        assert fetch_tmdb_poster("Unknown Title Nobody Made", _API_KEY) is None

    @resp_lib.activate
    def test_returns_none_when_best_result_has_no_poster(self):
        no_poster = dict(_MOVIE_RESULT, poster_path=None)
        resp_lib.add(
            resp_lib.GET, _SEARCH_URL,
            json=_search_response(no_poster),
            status=200,
        )
        assert fetch_tmdb_poster("Star Wars", _API_KEY) is None
