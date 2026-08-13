"""Tests for src/edge_client.py."""

import responses as resp_lib

from src.edge_client import EdgeClient, normalize_holdings


_BASE = "https://edge.example.com"
_RTAC_URL = f"{_BASE}/prod/rtac/folioRTAC"
_API_KEY = "test-edge-key"

_SAMPLE_RTAC = {
    "instanceId": "3ef6cd0b-190d-4464-97ce-d44b417aae39",
    "holdings": [
        {
            "id": "f85c0ace-9c88-4eda-b21c-aecd3e260228",
            "callNumber": "DG676.8 .W37 2026",
            "location": "Smith College Neilson Stacks",
            "locationCode": "SNSTK",
            "status": "Checked out",
            "dueDate": "2027-05-02T03:59:59.000+00:00",
            "permanentLoanType": "Standard Loan",
            "barcode": "310183693971169",
            "materialType": {
                "id": "2d72aa13-2451-41fe-afc7-b3dc7c131389",
                "name": "Book",
            },
            "library": {"name": "SC Neilson Library", "code": "SCNLS"},
        },
        {
            "id": "another-uuid",
            "callNumber": "DG676.8 .W37 2026 c.2",
            "location": "Mount Holyoke Stacks",
            "locationCode": "MHSTK",
            "status": "Available",
            "library": {"name": "MH Library", "code": "MHL"},
            "materialType": {"id": "...", "name": "Book"},
        },
    ],
}


# ── EdgeClient.get_rtac ───────────────────────────────────────────────


class TestGetRtac:
    @resp_lib.activate
    def test_returns_response_dict(self):
        resp_lib.add(resp_lib.GET, _RTAC_URL, json=_SAMPLE_RTAC, status=200)
        client = EdgeClient(_BASE, _API_KEY)
        result = client.get_rtac("3ef6cd0b-190d-4464-97ce-d44b417aae39")
        assert result["instanceId"] == "3ef6cd0b-190d-4464-97ce-d44b417aae39"
        assert len(result["holdings"]) == 2

    @resp_lib.activate
    def test_includes_apikey_param(self):
        resp_lib.add(resp_lib.GET, _RTAC_URL, json={"holdings": []}, status=200)
        client = EdgeClient(_BASE, _API_KEY)
        client.get_rtac("instance-id")
        sent = resp_lib.calls[0].request.url
        assert "apikey=" + _API_KEY in sent
        assert "mms_id=instance-id" in sent

    @resp_lib.activate
    def test_sends_accept_json_header(self):
        # Without Accept: application/json, RTAC returns XML — would break resp.json()
        resp_lib.add(resp_lib.GET, _RTAC_URL, json={"holdings": []}, status=200)
        client = EdgeClient(_BASE, _API_KEY)
        client.get_rtac("instance-id")
        sent_headers = resp_lib.calls[0].request.headers
        assert sent_headers.get("Accept") == "application/json"

    @resp_lib.activate
    def test_returns_none_on_http_error(self):
        resp_lib.add(resp_lib.GET, _RTAC_URL, status=500)
        client = EdgeClient(_BASE, _API_KEY)
        assert client.get_rtac("any-id") is None

    @resp_lib.activate
    def test_returns_none_on_invalid_json(self):
        resp_lib.add(resp_lib.GET, _RTAC_URL, body="not json", status=200)
        client = EdgeClient(_BASE, _API_KEY)
        assert client.get_rtac("any-id") is None


# ── EdgeClient.get_rtac_batch ─────────────────────────────────────────


class TestGetRtacBatch:
    @resp_lib.activate
    def test_returns_map_keyed_by_instance_id(self):
        resp_lib.add(resp_lib.GET, _RTAC_URL, json=_SAMPLE_RTAC, status=200)
        resp_lib.add(resp_lib.GET, _RTAC_URL, json=_SAMPLE_RTAC, status=200)
        client = EdgeClient(_BASE, _API_KEY)
        result = client.get_rtac_batch(["id-1", "id-2"])
        assert set(result.keys()) == {"id-1", "id-2"}

    @resp_lib.activate
    def test_empty_list_returns_empty_dict(self):
        client = EdgeClient(_BASE, _API_KEY)
        assert client.get_rtac_batch([]) == {}

    @resp_lib.activate
    def test_failed_instances_are_omitted(self):
        # First call succeeds, second 500s
        resp_lib.add(resp_lib.GET, _RTAC_URL, json=_SAMPLE_RTAC, status=200)
        resp_lib.add(resp_lib.GET, _RTAC_URL, status=500)
        client = EdgeClient(_BASE, _API_KEY)
        # Use single worker so order is deterministic
        result = client.get_rtac_batch(["id-1", "id-2"], max_workers=1)
        # One of them should be present; failure should be silently dropped
        assert len(result) == 1


# ── normalize_holdings ────────────────────────────────────────────────


class TestNormalizeHoldings:
    def test_flattens_to_display_shape(self):
        result = normalize_holdings(_SAMPLE_RTAC)
        assert len(result) == 2
        first = result[0]
        assert first["call_number"]   == "DG676.8 .W37 2026"
        assert first["location"]      == "Smith College Neilson Stacks"
        assert first["library"]       == "SC Neilson Library"
        assert first["library_code"]  == "SCNLS"
        assert first["status"]        == "Checked out"
        assert first["due_date"]      == "2027-05-02"   # trimmed to date
        assert first["loan_type"]     == "Standard Loan"
        assert first["barcode"]       == "310183693971169"
        assert first["material_type"] == "Book"

    def test_empty_response_returns_empty_list(self):
        assert normalize_holdings({}) == []
        assert normalize_holdings(None) == []
        assert normalize_holdings({"holdings": []}) == []

    def test_missing_fields_become_empty_strings(self):
        sparse = {"holdings": [{"callNumber": "X"}]}
        result = normalize_holdings(sparse)
        assert result[0]["call_number"] == "X"
        assert result[0]["location"] == ""
        assert result[0]["library"]  == ""
        assert result[0]["status"]   == ""
