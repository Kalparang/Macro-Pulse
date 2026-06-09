from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, timedelta
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ...core.logging import get_logger
from ...domain.models import AssetSnapshot, ValueFormat
from ..snapshots import build_snapshot


logger = get_logger(__name__)

FRED_CSV_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv"
    "?id={series_id}&cosd={start_date}"
)
REQUEST_HEADERS = {
    "User-Agent": "Macro-Pulse Bot",
    "Accept": "text/csv,*/*;q=0.8",
}
DEFAULT_LOOKBACK_DAYS = 90


@dataclass(slots=True, frozen=True)
class FredSeriesDefinition:
    name: str
    series_id: str
    value_format: ValueFormat = ValueFormat.STANDARD_2


def fetch_fred_snapshot(
    definition: FredSeriesDefinition,
    *,
    timeout: int = 30,
    attempts: int = 2,
    retry_delay: float = 1.0,
) -> AssetSnapshot | None:
    start_date = date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    url = FRED_CSV_URL.format(
        series_id=definition.series_id,
        start_date=start_date.isoformat(),
    )

    for attempt in range(1, attempts + 1):
        try:
            request = Request(url, headers=REQUEST_HEADERS)
            with urlopen(request, timeout=timeout) as response:
                csv_text = response.read().decode("utf-8", "ignore")
            return parse_fred_snapshot(definition, csv_text)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            if attempt == attempts:
                logger.error(
                    "Failed to fetch FRED series %s: %s",
                    definition.series_id,
                    exc,
                )
                return None

            logger.warning(
                "Retrying FRED series %s after attempt %s/%s failed: %s",
                definition.series_id,
                attempt,
                attempts,
                exc,
            )
            sleep(retry_delay)

    return None


def parse_fred_snapshot(
    definition: FredSeriesDefinition,
    csv_text: str,
) -> AssetSnapshot:
    points = _parse_fred_points(csv_text, definition.series_id)
    if not points:
        raise ValueError(f"FRED series {definition.series_id} has no numeric values.")

    latest_points = points[-7:]
    latest_value = latest_points[-1][1]
    previous_value = latest_points[-2][1] if len(latest_points) > 1 else latest_value
    change = latest_value - previous_value

    return build_snapshot(
        definition.name,
        latest_value,
        change,
        None,
        history=[value for _, value in latest_points],
        dates=[_format_fred_date(date_value) for date_value, _ in latest_points],
        value_format=definition.value_format,
    )


def _parse_fred_points(csv_text: str, series_id: str) -> list[tuple[str, float]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    points: list[tuple[str, float]] = []

    for row in reader:
        raw_value = (row.get(series_id) or "").strip()
        if raw_value in {"", "."}:
            continue

        try:
            points.append((_date_from_row(row), float(raw_value)))
        except (KeyError, ValueError):
            continue

    return points


def _date_from_row(row: dict[str, str]) -> str:
    date_value = row.get("observation_date") or row.get("DATE") or row.get("date")
    if not date_value:
        raise KeyError("FRED CSV row does not include a date column.")
    return str(date_value)


def _format_fred_date(date_value: str) -> str:
    return date_value[5:] if len(date_value) >= 10 else date_value
