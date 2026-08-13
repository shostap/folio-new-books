"""Tests for src/folio_client.py."""

import time
from unittest.mock import MagicMock, patch

import pytest
import responses as resp_lib
import requests

from src.folio_client import FolioClient, FolioAuthError, _INSTANCE_BATCH_SIZE


# ── Helpers ───────────────────────────────────────────────────────────


def _make_config(
    base_url="https://api.example.com",
    tenant="test-tenant",
    username="user",
    password="pass",
):
    cfg = MagicMock()
    cfg.folio_base_url = base_url
    cfg.folio_tenant = tenant
    cfg.folio_username = username
    cfg.folio_password = password
    return cfg


def _auth_response(access_token="test-access-token"):
    """Returns headers and body that a successful FOLIO login would return."""
    return {
        "headers": {
            "Set-Cookie": f"folioAccessToken={access_token}; Path=/; HttpOnly; Secure",
            "Content-Type": "application/json",
        },
        "json": {
            "accessTokenExpiration": "2099-01-01T00:00:00Z",
            "refreshTokenExpiration": "2099-01-01T00:00:00Z",
        },
        "status": 200,
    }


# ── CQL builder ───────────────────────────────────────────────────────


class TestBuildOrdersCql:
    def test_with_material_uuid(self):
        cql = FolioClient._build_orders_cql(
            "2024-01-01", "2024-01-31", "uuid-123"
        )
        assert 'physical.materialType == "uuid-123"' in cql
        assert 'receiptDate>="2024-01-01T00:00:00"' in cql
        assert 'receiptDate<="2024-01-31T23:59:59"' in cql
        assert 'receiptStatus=="Fully Received"' in cql
        assert "sortby metadata.updatedDate/sort.descending" in cql

    def test_without_material_uuid(self):
        cql = FolioClient._build_orders_cql("2024-01-01", "2024-01-31", None)
        assert "physical.materialType" not in cql
        assert 'receiptDate>="2024-01-01T00:00:00"' in cql
        assert "sortby metadata.updatedDate/sort.descending" in cql


# ── Token extraction ──────────────────────────────────────────────────


class TestExtractAccessToken:
    def test_extracts_from_cookies(self):
        mock_resp = MagicMock()
        mock_resp.cookies = {"folioAccessToken": "my-token"}
        result = FolioClient._extract_access_token(mock_resp)
        assert result == "my-token"

    def test_falls_back_to_header(self):
        mock_resp = MagicMock()
        mock_resp.cookies = {}
        mock_resp.headers = {
            "set-cookie": "folioAccessToken=header-token; Path=/; Secure"
        }
        result = FolioClient._extract_access_token(mock_resp)
        assert result == "header-token"

    def test_returns_none_when_not_present(self):
        mock_resp = MagicMock()
        mock_resp.cookies = {}
        mock_resp.headers = {"set-cookie": "someOtherCookie=value"}
        result = FolioClient._extract_access_token(mock_resp)
        assert result is None


# ── Authentication ────────────────────────────────────────────────────


class TestAuthenticate:
    @resp_lib.activate
    def test_successful_auth(self):
        auth = _auth_response()
        resp_lib.add(
            resp_lib.POST,
            "https://api.example.com/authn/login-with-expiry",
            headers=auth["headers"],
            json=auth["json"],
            status=200,
        )

        client = FolioClient(_make_config())
        client._authenticate()

        assert client._access_token == "test-access-token"
        assert client._token_expiry > time.time()

    @resp_lib.activate
    def test_raises_on_http_error(self):
        resp_lib.add(
            resp_lib.POST,
            "https://api.example.com/authn/login-with-expiry",
            json={"errors": [{"message": "Bad credentials"}]},
            status=401,
        )

        client = FolioClient(_make_config())
        with pytest.raises(FolioAuthError):
            client._authenticate()

    @resp_lib.activate
    def test_raises_when_no_token_in_cookies(self):
        resp_lib.add(
            resp_lib.POST,
            "https://api.example.com/authn/login-with-expiry",
            json={"accessTokenExpiration": "2099-01-01T00:00:00Z"},
            status=200,
        )

        client = FolioClient(_make_config())
        with pytest.raises(FolioAuthError, match="folioAccessToken"):
            client._authenticate()


# ── Order line queries ────────────────────────────────────────────────


class TestGetNewOrders:
    @resp_lib.activate
    def test_returns_po_lines(self):
        auth = _auth_response()
        resp_lib.add(
            resp_lib.POST,
            "https://api.example.com/authn/login-with-expiry",
            headers=auth["headers"],
            json=auth["json"],
            status=200,
        )
        resp_lib.add(
            resp_lib.GET,
            "https://api.example.com/orders/order-lines",
            json={"poLines": [{"id": "line-1", "instanceId": "inst-1"}], "totalRecords": 1},
            status=200,
        )

        client = FolioClient(_make_config())
        result = client.get_new_orders("2024-01-01", "2024-01-31")

        assert result["totalRecords"] == 1
        assert result["poLines"][0]["id"] == "line-1"

    @resp_lib.activate
    def test_query_contains_material_uuid(self):
        auth = _auth_response()
        resp_lib.add(
            resp_lib.POST,
            "https://api.example.com/authn/login-with-expiry",
            headers=auth["headers"],
            json=auth["json"],
            status=200,
        )
        resp_lib.add(
            resp_lib.GET,
            "https://api.example.com/orders/order-lines",
            json={"poLines": [], "totalRecords": 0},
            status=200,
        )

        client = FolioClient(_make_config())
        client.get_new_orders("2024-01-01", "2024-01-31", material_uuid="mat-uuid")

        sent_query = resp_lib.calls[-1].request.url
        assert "mat-uuid" in sent_query


# ── Instance batch lookup ─────────────────────────────────────────────


class TestGetInstances:
    @resp_lib.activate
    def test_returns_instance_map(self):
        auth = _auth_response()
        resp_lib.add(
            resp_lib.POST,
            "https://api.example.com/authn/login-with-expiry",
            headers=auth["headers"],
            json=auth["json"],
            status=200,
        )
        resp_lib.add(
            resp_lib.GET,
            "https://api.example.com/search/instances",
            json={
                "instances": [
                    {"id": "inst-1", "title": "Book One"},
                    {"id": "inst-2", "title": "Book Two"},
                ],
                "totalRecords": 2,
            },
            status=200,
        )

        client = FolioClient(_make_config())
        result = client.get_instances(["inst-1", "inst-2"])

        assert "inst-1" in result
        assert result["inst-1"]["title"] == "Book One"

    @resp_lib.activate
    def test_empty_list_returns_empty_dict(self):
        client = FolioClient(_make_config())
        # No HTTP calls should be made
        result = client.get_instances([])
        assert result == {}

    @resp_lib.activate
    def test_batches_large_lists(self):
        """More IDs than _INSTANCE_BATCH_SIZE triggers multiple requests."""
        auth = _auth_response()
        resp_lib.add(
            resp_lib.POST,
            "https://api.example.com/authn/login-with-expiry",
            headers=auth["headers"],
            json=auth["json"],
            status=200,
        )
        # Register two batch responses
        for _ in range(2):
            resp_lib.add(
                resp_lib.GET,
                "https://api.example.com/search/instances",
                json={"instances": [], "totalRecords": 0},
                status=200,
            )

        ids = [f"id-{i}" for i in range(_INSTANCE_BATCH_SIZE + 1)]
        client = FolioClient(_make_config())
        client.get_instances(ids)

        # One auth call + two batch calls
        search_calls = [
            c for c in resp_lib.calls
            if "/search/instances" in c.request.url
        ]
        assert len(search_calls) == 2
