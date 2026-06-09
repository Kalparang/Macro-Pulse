from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ...core.logging import get_logger
from ...domain.models import ReportDataset
from ..cache import TtlCache
from ..snapshots import build_snapshot
from .base import ProviderOutput, get_env_token


logger = get_logger(__name__)

SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_CACHE_TTL_SECONDS = 60 * 60 * 6


@dataclass(slots=True, frozen=True)
class SecIssuerDefinition:
    name: str
    cik: str


SEC_TRACKED_ISSUERS = (
    SecIssuerDefinition("Apple", "0000320193"),
    SecIssuerDefinition("Microsoft", "0000789019"),
    SecIssuerDefinition("NVIDIA", "0001045810"),
    SecIssuerDefinition("Amazon", "0001018724"),
    SecIssuerDefinition("Meta", "0001326801"),
    SecIssuerDefinition("Alphabet", "0001652044"),
    SecIssuerDefinition("Tesla", "0001318605"),
)


def fetch_sec_data(
    issuers: tuple[SecIssuerDefinition, ...] = SEC_TRACKED_ISSUERS,
) -> ProviderOutput:
    user_agent = (
        get_env_token("SEC_USER_AGENT")
        or "Macro-Pulse Bot contact@example.com"
    )
    since = date.today() - timedelta(days=7)
    filings = []

    for issuer in issuers:
        payload = fetch_sec_submissions(issuer, user_agent)
        if payload is None:
            continue
        filings.extend(parse_recent_filings(payload, since=since))

    if not filings:
        return ProviderOutput(dataset={"disclosures_us": []})

    eight_k_count = sum(1 for filing in filings if filing["form"] == "8-K")
    periodic_count = sum(1 for filing in filings if filing["form"] in {"10-Q", "10-K"})
    dataset: ReportDataset = {
        "disclosures_us": [
            build_snapshot("SEC Tracked Filings (7d)", len(filings), 0, 0),
            build_snapshot("SEC 8-K Filings (7d)", eight_k_count, 0, 0),
            build_snapshot("SEC 10-Q/K Filings (7d)", periodic_count, 0, 0),
        ]
    }
    return ProviderOutput(dataset=dataset)


def fetch_sec_submissions(
    issuer: SecIssuerDefinition,
    user_agent: str,
    *,
    timeout: int = 30,
) -> dict | None:
    cache = TtlCache()
    cache_key = f"sec:submissions:{issuer.cik}"
    cached_payload = cache.get_json(cache_key, SEC_CACHE_TTL_SECONDS)
    if cached_payload:
        return cached_payload

    url = SEC_SUBMISSIONS_URL.format(cik=issuer.cik)
    try:
        request = Request(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
        )
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "ignore"))
        cache.set_json(cache_key, payload)
        return payload
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to fetch SEC submissions for %s: %s", issuer.name, exc)
        return None


def parse_recent_filings(payload: dict, *, since: date) -> list[dict[str, str]]:
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    filings = []

    for form, filing_date, accession in zip(forms, filing_dates, accessions):
        try:
            parsed_date = date.fromisoformat(str(filing_date))
        except ValueError:
            continue
        if parsed_date < since:
            continue
        filings.append(
            {
                "form": str(form),
                "filing_date": parsed_date.isoformat(),
                "accession": str(accession),
            }
        )
    return filings
