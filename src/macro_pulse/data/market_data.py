import math
from concurrent.futures import ThreadPoolExecutor

from ..core.logging import get_logger
from ..domain.models import (
    ReportDataset,
    ValueFormat,
    coerce_cnbc_quote,
)
from .exchange_rates import build_exchange_snapshots
from .providers.cnbc import CNBC_FX_SYMBOLS, CNBC_MARKET_SYMBOLS, fetch_cnbc_data
from .providers.fred import FredSeriesDefinition, fetch_fred_snapshots
from .providers.base import ProviderOutput
from .providers.bls import fetch_bls_data
from .providers.bea import fetch_bea_data
from .providers.ecos import fetch_ecos_data
from .providers.kosis import fetch_kosis_data
from .providers.krx import fetch_krx_data
from .providers.opendart import fetch_opendart_data
from .providers.sec import fetch_sec_data
from .providers.yahoo import (
    YF_RATES_HISTORY,
    YF_TICKERS,
    configure_yfinance_cache,
    fetch_yahoo_rate_histories,
    fetch_yahoo_snapshots,
)
from .snapshots import build_snapshot


logger = get_logger(__name__)


FRED_SERIES = {
    "commodities_rates": (
        FredSeriesDefinition(
            "US 2Y Treasury",
            "DGS2",
            value_format=ValueFormat.YIELD_3,
        ),
        FredSeriesDefinition(
            "US 10Y-2Y Spread",
            "T10Y2Y",
            value_format=ValueFormat.YIELD_3,
        ),
    ),
    "risk": (
        FredSeriesDefinition(
            "US High Yield Spread",
            "BAMLH0A0HYM2",
            value_format=ValueFormat.YIELD_3,
        ),
    ),
}


def fetch_all_data() -> ReportDataset:
    configure_yfinance_cache()
    results = _empty_report_dataset()

    with ThreadPoolExecutor(max_workers=4) as executor:
        yahoo_rates_future = executor.submit(fetch_yahoo_rate_histories)
        cnbc_future = executor.submit(
            fetch_cnbc_data,
            [*CNBC_MARKET_SYMBOLS, *CNBC_FX_SYMBOLS],
        )
        yahoo_future = executor.submit(fetch_yahoo_snapshots, YF_TICKERS)
        fred_future = executor.submit(fetch_fred_snapshots, FRED_SERIES)
        optional_futures = [
            executor.submit(provider)
            for provider in (
                fetch_bls_data,
                fetch_bea_data,
                fetch_sec_data,
                fetch_krx_data,
                fetch_ecos_data,
                fetch_kosis_data,
                fetch_opendart_data,
            )
        ]

        yf_rates_data = yahoo_rates_future.result()
        cnbc_data = cnbc_future.result()
        _merge_dataset(results, yahoo_future.result())
        _merge_dataset(results, fred_future.result())
        for future in optional_futures:
            _merge_provider_output(results, future.result())

    results["exchange"].extend(build_exchange_snapshots(cnbc_data, yf_rates_data))
    _append_cnbc_market_snapshots(results, cnbc_data)
    _reorder_bond_snapshots(results["commodities_rates"])

    logger.info(
        "Completed fetch cycle with %s populated categories",
        sum(1 for items in results.values() if items),
    )

    return results


def _empty_report_dataset() -> ReportDataset:
    return {
        "indices_domestic": [],
        "indices_overseas": [],
        "futures": [],
        "sectors_us": [],
        "sectors_kr": [],
        "volatility": [],
        "commodities_rates": [],
        "exchange": [],
        "risk": [],
        "macro_us": [],
        "disclosures_us": [],
        "crypto": [],
    }


def _merge_dataset(target: ReportDataset, source: ReportDataset) -> None:
    for category, items in source.items():
        target_items = target.setdefault(category, [])
        for item in items:
            if not _has_finite_price(item):
                logger.warning("Skipping invalid snapshot value for %s", item.name)
                continue
            target_items.append(item)


def _has_finite_price(item) -> bool:
    return item.price is not None and math.isfinite(float(item.price))


def _merge_provider_output(target: ReportDataset, output: ProviderOutput) -> None:
    _merge_dataset(target, output.dataset)
    for warning in output.warnings:
        logger.info("Provider skipped: %s", warning)


def _append_cnbc_market_snapshots(results: ReportDataset, cnbc_data) -> None:
    for symbol, category, value_format in (
        (".KSVKOSPI", "volatility", ValueFormat.STANDARD_2),
        ("JP10Y", "commodities_rates", ValueFormat.YIELD_3),
        ("KR10Y", "commodities_rates", ValueFormat.YIELD_3),
    ):
        quote = cnbc_data.get(symbol)
        if quote is None:
            continue

        item = coerce_cnbc_quote(quote)
        results[category].append(
            build_snapshot(
                item.name,
                item.price,
                item.change,
                item.change_pct,
                value_format=value_format,
            )
        )


def _reorder_bond_snapshots(commodities_rates) -> None:
    us_10y_index = next(
        (
            index
            for index, item in enumerate(commodities_rates)
            if item.name == "US 10Y Treasury"
        ),
        None,
    )
    korea_10y_index = next(
        (
            index
            for index, item in enumerate(commodities_rates)
            if item.name == "Korea 10Y Treasury"
        ),
        None,
    )

    if us_10y_index is None or korea_10y_index is None:
        return

    us_10y_snapshot = commodities_rates.pop(us_10y_index)
    korea_10y_index = next(
        (
            index
            for index, item in enumerate(commodities_rates)
            if item.name == "Korea 10Y Treasury"
        ),
        None,
    )
    if korea_10y_index is None:
        commodities_rates.append(us_10y_snapshot)
        return

    commodities_rates.insert(korea_10y_index + 1, us_10y_snapshot)
