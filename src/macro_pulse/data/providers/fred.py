from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ...core.logging import get_logger
from ...domain.models import AssetSnapshot, ValueFormat
from ..snapshots import build_snapshot


logger = get_logger(__name__)

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
REQUEST_HEADERS = {
    "User-Agent": "Macro-Pulse Bot",
    "Accept": "text/csv,*/*;q=0.8",
}


@dataclass(slots=True, frozen=True)
class FredSeriesDefinition:
    name: str
    series_id: str
    value_format: ValueFormat = ValueFormat.STANDARD_2


def fetch_fred_snapshot(
    definition: FredSeriesDefinition,
    *,
    timeout: int = 15,
) -> AssetSnapshot | None:
    url = FRED_CSV_URL.format(series_id=definition.series_id)

    try:
        request = Request(url, headers=REQUEST_HEADERS)
        with urlopen(request, timeout=timeout) as response:
            csv_text = response.read().decode("utf-8", "ignore")
        return parse_fred_snapshot(definition, csv_text)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        logger.error("Failed to fetch FRED series %s: %s", definition.series_id, exc)
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
            points.append((str(row["DATE"]), float(raw_value)))
        except (KeyError, ValueError):
            continue

    return points


def _format_fred_date(date_value: str) -> str:
    return date_value[5:] if len(date_value) >= 10 else date_value
