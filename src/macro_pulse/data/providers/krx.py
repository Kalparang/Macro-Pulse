from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ...core.logging import get_logger
from ...domain.models import ReportDataset, ValueFormat
from ..cache import TtlCache
from ..snapshots import build_snapshot
from .base import ProviderOutput, empty_provider_output, get_env_token


logger = get_logger(__name__)

KRX_CACHE_TTL_SECONDS = 60 * 60 * 6

KRX_STOCK_DAILY_ENV_URLS = (
    "KRX_KOSPI_STOCK_DAILY_URL",
    "KRX_KOSDAQ_STOCK_DAILY_URL",
)

LEGACY_MARKET_BREADTH_ENV_URL = "KRX_MARKET_BREADTH_URL"

ROW_NAME_FIELD_ALIASES = (
    "IDX_NM",
    "idx_nm",
    "ISU_NM",
    "isu_nm",
    "ISU_ABBRV",
    "isu_abbrv",
    "MKT_NM",
    "mkt_nm",
)

SECURITY_CODE_FIELD_ALIASES = ("ISU_CD", "isu_cd", "ISU_SRT_CD", "isu_srt_cd")

PRICE_FIELD_ALIASES = (
    "CLSPRC_IDX",
    "clsprc_idx",
    "TDD_CLSPRC",
    "tdd_clsprc",
    "close",
    "price",
)

CHANGE_FIELD_ALIASES = (
    "CMPPREVDD_IDX",
    "cmpprevdd_idx",
    "CMPPREVDD_PRC",
    "cmpprevdd_prc",
    "FLUC_VAL",
    "fluc_val",
    "change",
)

CHANGE_PCT_FIELD_ALIASES = ("FLUC_RT", "fluc_rt", "change_pct", "changeRate")

TRADING_VALUE_FIELD_ALIASES = (
    "ACC_TRDVAL",
    "acc_trdval",
    "TRDVAL",
    "trdval",
    "trading_value",
)


@dataclass(slots=True, frozen=True)
class KrxMetricDefinition:
    name: str
    env_urls: tuple[str, ...]
    value_format: ValueFormat
    field_aliases: tuple[str, ...]
    scale: float = 1.0
    aggregate: str = "first"


@dataclass(slots=True, frozen=True)
class KrxSnapshotDefinition:
    category: str
    name: str
    env_urls: tuple[str, ...]
    name_aliases: tuple[str, ...] = ()
    security_codes: tuple[str, ...] = ()
    value_format: ValueFormat = ValueFormat.STANDARD_2


KRX_METRICS = (
    KrxMetricDefinition(
        "KRX Advancing Issues",
        KRX_STOCK_DAILY_ENV_URLS,
        ValueFormat.COUNT_0,
        ("advancers", "up_count", "UP_CNT", "isu_up", "isu_up_cnt"),
        aggregate="advancers",
    ),
    KrxMetricDefinition(
        "KRX Declining Issues",
        KRX_STOCK_DAILY_ENV_URLS,
        ValueFormat.COUNT_0,
        ("decliners", "down_count", "DOWN_CNT", "isu_down", "isu_down_cnt"),
        aggregate="decliners",
    ),
    KrxMetricDefinition(
        "KRX Trading Value",
        KRX_STOCK_DAILY_ENV_URLS,
        ValueFormat.KRW_TRILLION_1,
        TRADING_VALUE_FIELD_ALIASES,
        scale=1 / 1_000_000_000_000,
        aggregate="sum",
    ),
    KrxMetricDefinition(
        "KRX Foreign Net Buy",
        ("KRX_INVESTOR_FLOW_URL",),
        ValueFormat.KRW_EOK_0,
        ("foreign_net_buy", "frgn_ntby", "FRGN_NTBY", "frgn_net_buy"),
        scale=1 / 100_000_000,
    ),
    KrxMetricDefinition(
        "KRX Institution Net Buy",
        ("KRX_INVESTOR_FLOW_URL",),
        ValueFormat.KRW_EOK_0,
        ("institution_net_buy", "inst_ntby", "INST_NTBY", "inst_net_buy"),
        scale=1 / 100_000_000,
    ),
    KrxMetricDefinition(
        "KRX Individual Net Buy",
        ("KRX_INVESTOR_FLOW_URL",),
        ValueFormat.KRW_EOK_0,
        ("individual_net_buy", "indv_ntby", "INDV_NTBY", "indv_net_buy"),
        scale=1 / 100_000_000,
    ),
)

KRX_SNAPSHOTS = (
    KrxSnapshotDefinition(
        "indices_domestic",
        "KOSPI",
        ("KRX_INDEX_KOSPI_URL",),
        name_aliases=("KOSPI", "KOSPI Composite", "코스피"),
    ),
    KrxSnapshotDefinition(
        "indices_domestic",
        "KOSDAQ",
        ("KRX_INDEX_KOSDAQ_URL",),
        name_aliases=("KOSDAQ", "KOSDAQ Composite", "코스닥"),
    ),
    KrxSnapshotDefinition(
        "indices_domestic",
        "KOSPI200",
        ("KRX_INDEX_KOSPI_URL", "KRX_INDEX_KRX_URL"),
        name_aliases=("KOSPI 200", "KOSPI200", "코스피 200"),
    ),
    KrxSnapshotDefinition(
        "sectors_kr",
        "Korea Semiconductors",
        ("KRX_ETF_DAILY_URL",),
        security_codes=("091160",),
    ),
    KrxSnapshotDefinition(
        "sectors_kr",
        "Korea Battery",
        ("KRX_ETF_DAILY_URL",),
        security_codes=("305720",),
    ),
    KrxSnapshotDefinition(
        "sectors_kr",
        "Korea Bio",
        ("KRX_ETF_DAILY_URL",),
        security_codes=("244580",),
    ),
    KrxSnapshotDefinition(
        "sectors_kr",
        "Korea Auto",
        ("KRX_ETF_DAILY_URL",),
        security_codes=("091180",),
    ),
    KrxSnapshotDefinition(
        "sectors_kr",
        "Korea Financials",
        ("KRX_ETF_DAILY_URL",),
        security_codes=("091170",),
    ),
)


def fetch_krx_data() -> ProviderOutput:
    token = get_env_token("KRX_API_KEY")
    if token is None:
        logger.info("KRX_API_KEY is not configured. Skipping KRX data.")
        return empty_provider_output("KRX_API_KEY missing")

    payloads_by_env_url: dict[str, dict | list] = {}
    results: ReportDataset = {
        "indices_domestic": [],
        "sectors_kr": [],
        "market_breadth_kr": [],
    }

    for definition in KRX_SNAPSHOTS:
        payloads = _get_payloads_for_env_urls(
            _active_env_urls(definition.env_urls),
            token,
            payloads_by_env_url,
        )
        snapshot = extract_krx_snapshot(payloads, definition)
        if snapshot is not None:
            results[definition.category].append(snapshot)

    for definition in KRX_METRICS:
        payloads = _get_payloads_for_env_urls(
            _active_env_urls(definition.env_urls),
            token,
            payloads_by_env_url,
        )
        value = extract_krx_metric(payloads, definition)
        if value is None:
            continue
        results["market_breadth_kr"].append(
            build_snapshot(
                definition.name,
                value,
                0,
                0,
                value_format=definition.value_format,
            )
        )

    return ProviderOutput(dataset={key: value for key, value in results.items() if value})


def fetch_krx_payload(
    endpoint_url: str,
    token: str,
    *,
    timeout: int = 30,
) -> dict | list | None:
    cache = TtlCache()
    cache_key = f"krx:{endpoint_url}"
    cached_payload = cache.get_json(cache_key, KRX_CACHE_TTL_SECONDS)
    if cached_payload:
        return cached_payload

    try:
        request = Request(
            endpoint_url,
            headers={
                "User-Agent": "Macro-Pulse Bot",
                "Accept": "application/json",
                "AUTH_KEY": token,
            },
        )
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "ignore"))
        cache.set_json(cache_key, payload)
        return payload
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to fetch KRX payload from %s: %s", endpoint_url, exc)
        return None


def extract_krx_metric(
    payload: dict | list | Sequence[dict | list],
    definition: KrxMetricDefinition,
) -> float | None:
    payloads = _normalize_payloads(payload)
    rows = _extract_rows_from_payloads(payloads)
    direct_value = _extract_direct_metric(rows, definition)
    if direct_value is not None and definition.aggregate != "sum":
        return direct_value

    if definition.aggregate == "advancers":
        return float(
            sum(
                1
                for row in rows
                if isinstance(row, dict) and (_extract_row_change(row) or 0) > 0
            )
        )
    if definition.aggregate == "decliners":
        return float(
            sum(
                1
                for row in rows
                if isinstance(row, dict) and (_extract_row_change(row) or 0) < 0
            )
        )
    if definition.aggregate == "sum":
        total = _sum_row_values(rows, definition.field_aliases)
        if total is not None:
            return total * definition.scale
        return direct_value

    return direct_value


def extract_krx_snapshot(
    payloads: Sequence[dict | list],
    definition: KrxSnapshotDefinition,
):
    for row in _extract_rows_from_payloads(payloads):
        if not isinstance(row, dict) or not _row_matches_definition(row, definition):
            continue
        price = _extract_first_number(row, PRICE_FIELD_ALIASES)
        if price is None:
            continue
        change = _extract_first_number(row, CHANGE_FIELD_ALIASES) or 0.0
        change_pct = _extract_first_number(row, CHANGE_PCT_FIELD_ALIASES) or 0.0
        return build_snapshot(
            definition.name,
            price,
            change,
            change_pct,
            value_format=definition.value_format,
        )
    return None


def _get_payloads_for_env_urls(
    env_urls: Iterable[str],
    token: str,
    payloads_by_env_url: dict[str, dict | list],
) -> list[dict | list]:
    payloads: list[dict | list] = []
    for env_url in env_urls:
        endpoint_url = os.environ.get(env_url, "").strip()
        if not endpoint_url:
            continue
        if env_url not in payloads_by_env_url:
            payload = fetch_krx_payload(endpoint_url, token)
            if payload is None:
                continue
            payloads_by_env_url[env_url] = payload
        payloads.append(payloads_by_env_url[env_url])
    return payloads


def _active_env_urls(env_urls: tuple[str, ...]) -> tuple[str, ...]:
    if env_urls == KRX_STOCK_DAILY_ENV_URLS:
        configured_stock_urls = tuple(
            env_url for env_url in env_urls if os.environ.get(env_url, "").strip()
        )
        if configured_stock_urls:
            return configured_stock_urls
        return (LEGACY_MARKET_BREADTH_ENV_URL,)
    return env_urls


def _normalize_payloads(payload: dict | list | Sequence[dict | list]) -> list[dict | list]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        if payload and all(isinstance(item, (dict, list)) for item in payload):
            first = payload[0]
            if isinstance(first, dict) and _looks_like_response_payload(first):
                return payload
        return [payload]
    return list(payload)


def _looks_like_response_payload(payload: dict) -> bool:
    return any(key in payload for key in ("output", "data", "list", "OutBlock_1"))


def _extract_rows_from_payloads(payloads: Sequence[dict | list]) -> list:
    rows: list = []
    for payload in payloads:
        rows.extend(_extract_rows(payload))
    return rows


def _extract_rows(payload: dict | list) -> list:
    if isinstance(payload, list):
        return payload
    for key in (
        "output",
        "data",
        "list",
        "OutBlock_1",
        "OutBlock1",
        "result",
        "items",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [value]
    return [payload]


def _extract_direct_metric(
    rows: Sequence,
    definition: KrxMetricDefinition,
) -> float | None:
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = _extract_first_number(row, definition.field_aliases)
        if value is not None:
            return value * definition.scale
    return None


def _sum_row_values(rows: Sequence, aliases: tuple[str, ...]) -> float | None:
    found = False
    total = 0.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = _extract_first_number(row, aliases)
        if value is None:
            continue
        found = True
        total += value
    return total if found else None


def _extract_row_change(row: dict) -> float | None:
    value = _extract_first_number(row, CHANGE_FIELD_ALIASES)
    if value is not None:
        return value

    close_price = _extract_first_number(row, ("TDD_CLSPRC", "tdd_clsprc", "close"))
    previous_price = _extract_first_number(
        row,
        ("PREV_DD_CLSPRC", "prev_dd_clsprc", "previous_close"),
    )
    if close_price is not None and previous_price is not None:
        return close_price - previous_price
    return None


def _extract_first_number(row: dict, aliases: tuple[str, ...]) -> float | None:
    for alias in aliases:
        if alias not in row:
            continue
        return _parse_number(row[alias])
    return None


def _row_matches_definition(row: dict, definition: KrxSnapshotDefinition) -> bool:
    if definition.security_codes:
        security_code = _extract_first_text(row, SECURITY_CODE_FIELD_ALIASES)
        if security_code and _normalize_security_code(security_code) in {
            _normalize_security_code(code) for code in definition.security_codes
        }:
            return True

    if definition.name_aliases:
        row_name = _extract_first_text(row, ROW_NAME_FIELD_ALIASES)
        if row_name and any(_text_matches(row_name, alias) for alias in definition.name_aliases):
            return True

    return False


def _extract_first_text(row: dict, aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        value = row.get(alias)
        if value is not None:
            return str(value).strip()
    return None


def _normalize_security_code(value: str) -> str:
    return re.sub(r"\D", "", value).zfill(6)


def _text_matches(value: str, alias: str) -> bool:
    return _normalize_text(value) == _normalize_text(alias)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _parse_number(value) -> float:
    normalized = str(value).strip()
    if normalized in {"", "-", "None"}:
        return 0.0
    normalized = (
        normalized.replace(",", "")
        .replace("%", "")
        .replace("+", "")
        .replace("KRW", "")
        .strip()
    )
    return float(normalized)
