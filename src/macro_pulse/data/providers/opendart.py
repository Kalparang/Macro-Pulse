from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ...core.logging import get_logger
from ...domain.models import ReportDataset, ValueFormat
from ..cache import TtlCache
from ..snapshots import build_snapshot
from .base import ProviderOutput, empty_provider_output, get_env_token


logger = get_logger(__name__)

OPENDART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
OPENDART_CACHE_TTL_SECONDS = 60 * 60 * 6


@dataclass(slots=True, frozen=True)
class OpenDartDisclosureQuery:
    name: str
    params: dict[str, str]


OPENDART_DISCLOSURE_QUERIES = (
    OpenDartDisclosureQuery("DART Filings (7d)", {}),
    OpenDartDisclosureQuery("DART Major Issue Filings (7d)", {"pblntf_ty": "B"}),
    OpenDartDisclosureQuery("DART Issuance Filings (7d)", {"pblntf_ty": "C"}),
    OpenDartDisclosureQuery("DART KOSPI Filings (7d)", {"corp_cls": "Y"}),
    OpenDartDisclosureQuery("DART KOSDAQ Filings (7d)", {"corp_cls": "K"}),
)


def fetch_opendart_data() -> ProviderOutput:
    token = get_env_token("OPENDART_API_KEY")
    if token is None:
        logger.info("OPENDART_API_KEY is not configured. Skipping OpenDART data.")
        return empty_provider_output("OPENDART_API_KEY missing")

    end_date = date.today()
    start_date = end_date - timedelta(days=7)
    snapshots = []
    for query in OPENDART_DISCLOSURE_QUERIES:
        payload = fetch_opendart_list(
            token,
            start_date=start_date,
            end_date=end_date,
            extra_params=query.params,
        )
        if payload is None:
            continue
        snapshots.append(
            build_snapshot(
                query.name,
                parse_opendart_total_count(payload),
                0,
                0,
                value_format=ValueFormat.COUNT_0,
            )
        )

    return ProviderOutput(dataset={"disclosures_kr": snapshots})


def fetch_opendart_list(
    token: str,
    *,
    start_date: date,
    end_date: date,
    extra_params: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict | None:
    params = {
        "crtfc_key": token,
        "bgn_de": start_date.strftime("%Y%m%d"),
        "end_de": end_date.strftime("%Y%m%d"),
        "last_reprt_at": "N",
        "sort": "date",
        "sort_mth": "desc",
        "page_no": "1",
        "page_count": "100",
    }
    params.update(extra_params or {})
    cache_key = f"opendart:list:{urlencode(sorted(params.items()))}"
    cache = TtlCache()
    cached_payload = cache.get_json(cache_key, OPENDART_CACHE_TTL_SECONDS)
    if cached_payload:
        return cached_payload

    request_url = f"{OPENDART_LIST_URL}?{urlencode(params)}"
    try:
        request = Request(
            request_url,
            headers={
                "User-Agent": "Macro-Pulse Bot",
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "ignore"))
        status = str(payload.get("status", ""))
        if status not in {"000", "013"}:
            logger.error(
                "OpenDART request failed: %s %s",
                status,
                payload.get("message"),
            )
            return None
        cache.set_json(cache_key, payload)
        return payload
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to fetch OpenDART disclosures: %s", exc)
        return None


def parse_opendart_total_count(payload: dict) -> int:
    if "total_count" in payload:
        try:
            return int(str(payload["total_count"]).replace(",", ""))
        except ValueError:
            return 0
    return len(payload.get("list", []))
