from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ...core.logging import get_logger
from ...domain.models import ReportDataset, ValueFormat
from ..cache import TtlCache
from ..snapshots import build_snapshot
from .base import ProviderOutput


logger = get_logger(__name__)

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_CACHE_TTL_SECONDS = 60 * 60 * 12


@dataclass(slots=True, frozen=True)
class BlsSeriesDefinition:
    name: str
    series_id: str
    value_format: ValueFormat = ValueFormat.STANDARD_2


BLS_SERIES = {
    "macro_us": (
        BlsSeriesDefinition("US CPI Index", "CUSR0000SA0"),
        BlsSeriesDefinition(
            "US Unemployment Rate",
            "LNS14000000",
            value_format=ValueFormat.PERCENT_2,
        ),
        BlsSeriesDefinition(
            "US Nonfarm Payrolls",
            "CES0000000001",
            value_format=ValueFormat.THOUSANDS_TO_MILLIONS_1,
        ),
        BlsSeriesDefinition(
            "US Avg Hourly Earnings",
            "CES0500000003",
            value_format=ValueFormat.USD_2,
        ),
    )
}


def fetch_bls_data(
    series_groups: dict[str, tuple[BlsSeriesDefinition, ...]] | None = None,
) -> ProviderOutput:
    logger.info("Fetching BLS data...")
    groups = series_groups or BLS_SERIES
    series_by_id = {
        definition.series_id: definition
        for definitions in groups.values()
        for definition in definitions
    }
    if not series_by_id:
        return ProviderOutput()

    payload = fetch_bls_payload(tuple(series_by_id))
    dataset: ReportDataset = {category: [] for category in groups}
    if payload is None:
        return ProviderOutput(dataset=dataset, warnings=["BLS fetch failed"])

    series_payloads = payload.get("Results", {}).get("series", [])
    snapshots_by_id = {}
    for raw_series in series_payloads:
        series_id = str(raw_series.get("seriesID", ""))
        definition = series_by_id.get(series_id)
        if definition is None:
            continue
        snapshot = parse_bls_snapshot(definition, raw_series)
        if snapshot is not None:
            snapshots_by_id[series_id] = snapshot

    for category, definitions in groups.items():
        for definition in definitions:
            snapshot = snapshots_by_id.get(definition.series_id)
            if snapshot is not None:
                dataset[category].append(snapshot)

    return ProviderOutput(dataset=dataset)


def fetch_bls_payload(series_ids: tuple[str, ...], *, timeout: int = 30) -> dict | None:
    current_year = date.today().year
    registration_key = os.environ.get("BLS_API_KEY", "").strip()
    request_payload = {
        "seriesid": list(series_ids),
        "startyear": str(current_year - 2),
        "endyear": str(current_year),
    }
    if registration_key:
        request_payload["registrationkey"] = registration_key

    cache = TtlCache()
    cache_key = (
        f"bls:v2:{','.join(series_ids)}:{request_payload['startyear']}:"
        f"{request_payload['endyear']}"
    )
    cached_payload = cache.get_json(cache_key, BLS_CACHE_TTL_SECONDS)
    if cached_payload:
        return cached_payload

    try:
        request = Request(
            BLS_API_URL,
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Macro-Pulse Bot",
            },
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "ignore"))
        if payload.get("status") != "REQUEST_SUCCEEDED":
            logger.error("BLS API request failed: %s", payload.get("message"))
            return None
        cache.set_json(cache_key, payload)
        return payload
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to fetch BLS data: %s", exc)
        return None


def parse_bls_snapshot(definition: BlsSeriesDefinition, raw_series: dict):
    points = []
    for item in raw_series.get("data", []):
        period = str(item.get("period", ""))
        if period == "M13":
            continue
        try:
            value = float(item["value"])
            period_order = int(period[1:]) if period.startswith("M") else 0
            points.append(
                (int(item["year"]), period_order, str(item["periodName"]), value)
            )
        except (KeyError, ValueError):
            continue

    if not points:
        return None

    points.sort(key=lambda point: (point[0], point[1]))
    latest_points = points[-7:]
    latest_value = latest_points[-1][3]
    previous_value = latest_points[-2][3] if len(latest_points) > 1 else latest_value
    change = latest_value - previous_value
    change_pct = (change / previous_value) * 100 if previous_value else 0.0
    return build_snapshot(
        definition.name,
        latest_value,
        change,
        change_pct,
        history=[value for _, _, _, value in latest_points],
        dates=[
            f"{year}-{period_name[:3]}" for year, _, period_name, _ in latest_points
        ],
        value_format=definition.value_format,
    )
