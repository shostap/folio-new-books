"""FOLIO API client — authentication, order-line queries, and instance lookup."""

import logging
import re
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Max instance IDs per mod-search CQL query (avoids URI-too-large errors)
_INSTANCE_BATCH_SIZE = 50


class FolioAuthError(Exception):
    """Raised when FOLIO login fails or the access token cannot be extracted."""


class FolioClient:
    """
    Thin wrapper around the FOLIO Okapi API.

    Authentication uses /authn/login-with-expiry (RTR / cookie-based tokens).
    The access token is cached and refreshed automatically before each request.
    """

    def __init__(self, config) -> None:
        self._base_url = config.folio_base_url
        self._tenant = config.folio_tenant
        self._username = config.folio_username
        self._password = config.folio_password
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0  # Unix timestamp
        self._http = requests.Session()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_new_orders(
        self,
        start_date: str,
        end_date: str,
        material_uuid: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict:
        """
        Query /orders/order-lines for items received in [start_date, end_date].

        Args:
            start_date: ISO date (YYYY-MM-DD), inclusive.
            end_date:   ISO date (YYYY-MM-DD), inclusive.
            material_uuid: Optional physical.materialType UUID to filter on.
            limit:  Maximum results to return per page.
            offset: Pagination offset.

        Returns:
            Raw FOLIO JSON response dict (keys: poLines, totalRecords).
        """
        cql = self._build_orders_cql(start_date, end_date, material_uuid)
        params = {"query": cql, "limit": limit, "offset": offset}
        url = f"{self._base_url}/orders/order-lines"
        logger.debug("Orders query: %s", cql)

        resp = self._get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_material_types(self) -> dict[str, str]:
        """
        Fetch every material-type definition from FOLIO and return UUID → name.

        Useful when no [material_types] config is provided — lets the generator
        show real type names in the dropdown instead of raw UUIDs.
        """
        url = f"{self._base_url}/material-types"
        try:
            resp = self._get(url, params={"limit": 500})
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Material-type lookup failed: %s", exc)
            return {}

        data = resp.json()
        return {mt["id"]: mt.get("name", "") for mt in data.get("mtypes", []) if mt.get("id")}

    def get_locations(self) -> dict[str, str]:
        """
        Fetch every shelving-location definition from FOLIO and return UUID → name.

        Used to translate ``effectiveLocationId`` on items into a human-readable
        label on the fallback (non-RTAC) holdings path.
        """
        url = f"{self._base_url}/locations"
        try:
            resp = self._get(url, params={"limit": 1000})
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Location lookup failed: %s", exc)
            return {}

        data = resp.json()
        return {loc["id"]: loc.get("name", "") for loc in data.get("locations", []) if loc.get("id")}

    def get_instances(self, instance_ids: list[str]) -> dict[str, dict]:
        """
        Fetch instance records from mod-search for a list of UUIDs.

        Batches requests so no single CQL query exceeds safe URI length.

        Returns:
            Dict mapping instance UUID → instance record.
        """
        results: dict[str, dict] = {}
        for i in range(0, len(instance_ids), _INSTANCE_BATCH_SIZE):
            batch = instance_ids[i : i + _INSTANCE_BATCH_SIZE]
            batch_result = self._fetch_instance_batch(batch)
            for inst in batch_result.get("instances", []):
                results[inst["id"]] = inst
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_orders_cql(
        start_date: str, end_date: str, material_uuid: Optional[str]
    ) -> str:
        date_range = (
            f'receiptDate>="{start_date}T00:00:00" '
            f'and receiptDate<="{end_date}T23:59:59"'
        )
        if material_uuid:
            cql = (
                f'(physical.materialType == "{material_uuid}" '
                f"and ({date_range}) "
                f'and receiptStatus=="Fully Received")'
            )
        else:
            cql = (
                f"(({date_range}) "
                f'and receiptStatus=="Fully Received")'
            )
        return cql + " sortby metadata.updatedDate/sort.descending"

    def _fetch_instance_batch(self, instance_ids: list[str]) -> dict:
        if not instance_ids:
            return {"instances": [], "totalRecords": 0}

        cql = "(" + " or ".join(f'id=="{iid}"' for iid in instance_ids) + ")"
        params = {
            "query": cql,
            "limit": len(instance_ids),
            "expandAll": "true",
        }
        url = f"{self._base_url}/search/instances"
        resp = self._get(url, params=params)
        if not resp.ok:
            logger.warning(
                "Instance batch lookup failed: %s %s", resp.status_code, resp.text[:200]
            )
            return {"instances": [], "totalRecords": 0}
        return resp.json()

    def _get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        token = self._ensure_token()
        headers = {
            "x-okapi-tenant": self._tenant,
            "Cookie": f"folioAccessToken={token}",
            "Accept": "application/json",
        }
        return self._http.get(url, headers=headers, params=params, timeout=30)

    def _ensure_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry - 30:
            return self._access_token
        self._authenticate()
        return self._access_token  # type: ignore[return-value]

    def _authenticate(self) -> None:
        """
        POST to /authn/login-with-expiry and extract the folioAccessToken cookie.

        FOLIO sends the token in Set-Cookie headers. requests processes these
        into response.cookies, which is the most reliable extraction path.
        """
        url = f"{self._base_url}/authn/login-with-expiry"
        headers = {
            "Content-Type": "application/json",
            "x-okapi-tenant": self._tenant,
        }
        payload = {"username": self._username, "password": self._password}

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if not resp.ok:
            raise FolioAuthError(
                f"FOLIO login failed: {resp.status_code} {resp.text[:300]}"
            )

        token = self._extract_access_token(resp)
        if not token:
            raise FolioAuthError(
                "FOLIO login succeeded but folioAccessToken was not found in the response cookies. "
                "Verify the base_url and tenant values in config.ini."
            )

        self._access_token = token

        # Parse token expiry from the response body
        try:
            body = resp.json()
            expiry_str = body.get("accessTokenExpiration", "")
            if expiry_str:
                from datetime import datetime, timezone

                dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                self._token_expiry = dt.timestamp()
            else:
                self._token_expiry = time.time() + 600
        except Exception:
            self._token_expiry = time.time() + 600

        logger.info("FOLIO authentication successful (token cached)")

    @staticmethod
    def _extract_access_token(response: requests.Response) -> Optional[str]:
        """
        Extract folioAccessToken from a FOLIO login response.

        Tries response.cookies first (requests handles multiple Set-Cookie headers
        correctly), then falls back to raw header parsing as a safety net.
        """
        token = response.cookies.get("folioAccessToken")
        if token:
            return token

        # Fallback: parse the raw Set-Cookie header text
        raw = response.headers.get("set-cookie", "")
        match = re.search(r"folioAccessToken=([^;,\s]+)", raw)
        return match.group(1) if match else None
