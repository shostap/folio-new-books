"""
FOLIO Edge API client (apikey-authenticated).

Used for the RTAC (Real-Time Availability Check) endpoint which returns
rich per-instance holdings data: call numbers, locations, statuses, due
dates, loan types, and material types.  This is the canonical source for
"where is the physical copy" information when the orders/inventory data
is incomplete.

Edge auth is completely separate from the Okapi RTR cookie flow used by
FolioClient — it takes a simple apikey query parameter.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class EdgeClient:
    """Thin wrapper around the FOLIO Edge RTAC endpoint."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 10) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def get_rtac(self, instance_id: str) -> Optional[dict]:
        """
        Fetch RTAC holdings for a single instance.

        Returns the raw JSON dict (with keys ``instanceId`` and ``holdings``),
        or None if the lookup fails.  Failures are logged but do not raise so
        that one bad instance does not abort the batch.

        The Accept header is critical: without it the Edge RTAC endpoint
        defaults to XML, which resp.json() cannot parse.
        """
        url = f"{self._base_url}/prod/rtac/folioRTAC"
        params = {"mms_id": instance_id, "apikey": self._api_key}
        headers = {
            "Accept":       "application/json",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("RTAC lookup failed for %s: %s", instance_id, exc)
        except ValueError as exc:
            logger.warning(
                "RTAC returned non-JSON for %s (Accept header may not be honored): %s",
                instance_id, exc,
            )
        return None

    def get_rtac_batch(
        self,
        instance_ids: list,
        max_workers: int = 5,
    ) -> dict:
        """
        Fetch RTAC data for many instances concurrently.

        Returns a dict mapping instance_id → RTAC response dict.  Instances
        that fail or return no data are simply omitted from the result.
        """
        if not instance_ids:
            return {}

        results: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(self.get_rtac, iid): iid for iid in instance_ids}
            for future in as_completed(futures):
                iid = futures[future]
                try:
                    data = future.result(timeout=self._timeout + 5)
                    if data:
                        results[iid] = data
                except Exception as exc:  # pragma: no cover — defensive
                    logger.warning("RTAC future failed for %s: %s", iid, exc)
        return results


def normalize_holdings(rtac_response: dict) -> list:
    """
    Flatten an RTAC response into a list of holding dicts shaped for display.

    Each holding dict has the keys the UI / JSON feed expect:
        call_number, location, library, status, due_date, loan_type,
        barcode, material_type

    Missing fields are returned as empty strings rather than None so the
    JSON feed has a consistent shape that downstream consumers can rely on.
    """
    if not rtac_response:
        return []

    holdings = []
    for h in rtac_response.get("holdings") or []:
        material = h.get("materialType") or {}
        library = h.get("library") or {}
        holdings.append({
            "call_number":   h.get("callNumber") or "",
            "location":      h.get("location") or "",
            "location_code": h.get("locationCode") or "",
            "library":       library.get("name") or "",
            "library_code":  library.get("code") or "",
            "status":        h.get("status") or "",
            "due_date":      _format_due_date(h.get("dueDate") or ""),
            "loan_type":     h.get("permanentLoanType") or "",
            "barcode":       h.get("barcode") or "",
            "material_type": material.get("name") or "",
        })
    return holdings


def _format_due_date(iso_dt: str) -> str:
    """Trim an ISO datetime to YYYY-MM-DD for display."""
    return iso_dt[:10] if iso_dt else ""
