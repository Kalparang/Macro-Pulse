from __future__ import annotations

import os
import tempfile
from math import isclose

import yfinance as yf

from ...core.logging import get_logger
from ...domain.models import ReportDataset, TickerDefinition, ValueFormat
from ..snapshots import build_snapshot


logger = get_logger(__name__)

YF_HISTORY_PERIODS = ("1mo", "3mo", "1y")
YF_INTRADAY_PERIOD = "5d"
YF_INTRADAY_INTERVAL = "1m"


YF_TICKERS = {
    "indices_domestic": (
        TickerDefinition("KOSPI", "^KS11"),
        TickerDefinition("KOSDAQ", "^KQ11"),
        TickerDefinition("KOSPI200", "^KS200"),
    ),
    "indices_overseas": (
        TickerDefinition("S&P 500", "^GSPC"),
        TickerDefinition("Nasdaq 100", "^NDX"),
        TickerDefinition("Nasdaq", "^IXIC"),
        TickerDefinition("Dow", "^DJI"),
        TickerDefinition("Russell 2000", "^RUT"),
        TickerDefinition("Euro Stoxx 50", "^STOXX50E"),
        TickerDefinition("Nikkei 225", "^N225"),
        TickerDefinition("Hang Seng", "^HSI"),
        TickerDefinition("Shanghai Composite", "000001.SS"),
    ),
    "futures": (
        TickerDefinition("S&P 500 Futures", "ES=F"),
        TickerDefinition("Nasdaq 100 Futures", "NQ=F"),
        TickerDefinition("Dow Futures", "YM=F"),
        TickerDefinition("Russell 2000 Futures", "RTY=F"),
    ),
    "sectors_us": (
        TickerDefinition("US Semiconductors", "SMH"),
        TickerDefinition("US Big Tech", "QQQ"),
        TickerDefinition("US Financials", "XLF"),
    ),
    "sectors_kr": (
        TickerDefinition("Korea Semiconductors", "091160.KS"),
        TickerDefinition("Korea Battery", "305720.KS"),
        TickerDefinition("Korea Bio", "244580.KS"),
        TickerDefinition("Korea Auto", "091180.KS"),
        TickerDefinition("Korea Financials", "091170.KS"),
    ),
    "commodities_rates": (
        TickerDefinition("WTI Crude Oil", "CL=F"),
        TickerDefinition("Brent Crude Oil", "BZ=F"),
        TickerDefinition("Gold", "GC=F"),
        TickerDefinition("Silver", "SI=F"),
        TickerDefinition("Copper", "HG=F"),
        TickerDefinition("US 10Y Treasury", "^TNX", value_format=ValueFormat.YIELD_3),
    ),
    "exchange": (
        TickerDefinition("DXY", "DX-Y.NYB"),
    ),
    "crypto": (
        TickerDefinition("Bitcoin", "BTC-USD"),
        TickerDefinition("Ethereum", "ETH-USD"),
    ),
    "volatility": (
        TickerDefinition("VIX", "^VIX"),
        TickerDefinition("MOVE", "^MOVE"),
    ),
}

YF_RATES_HISTORY = {
    "USD/KRW": "KRW=X",
    "JPY/KRW": "JPYKRW=X",
    "EUR/KRW": "EURKRW=X",
}


def configure_yfinance_cache() -> None:
    cache_dir = os.environ.get(
        "YFINANCE_CACHE_DIR",
        os.path.join(tempfile.gettempdir(), "macro-pulse-yfinance"),
    )
    os.makedirs(cache_dir, exist_ok=True)
    if hasattr(yf, "set_tz_cache_location"):
        yf.set_tz_cache_location(cache_dir)


def fetch_yahoo_rate_histories():
    histories = {}
    logger.info("Fetching YF rates history...")
    for name, ticker in YF_RATES_HISTORY.items():
        try:
            history = yf.Ticker(ticker).history(period="1mo")
            if not history.empty:
                histories[name] = history
        except Exception as exc:
            logger.error("Error fetching YF history for %s: %s", name, exc)
    return histories


def fetch_yahoo_snapshots(
    ticker_groups: dict[str, tuple[TickerDefinition, ...]] | None = None,
) -> ReportDataset:
    logger.info("Fetching Yahoo Finance data...")
    results: ReportDataset = {}

    for category, definitions in (ticker_groups or YF_TICKERS).items():
        items = []
        for definition in definitions:
            snapshot = fetch_yahoo_snapshot(definition)
            if snapshot is not None:
                items.append(snapshot)
        results[category] = items

    return results


def fetch_yahoo_snapshot(definition: TickerDefinition):
    try:
        data = fetch_yahoo_history(definition.symbol)
        if data is None:
            return None

        close_prices = data["Close"].dropna()
        intraday_latest = fetch_yahoo_intraday_latest(definition.symbol)
        last_price, previous_price = resolve_latest_and_previous_close(
            close_prices,
            intraday_latest,
        )
        change = last_price - previous_price if previous_price is not None else 0.0
        change_pct = (change / previous_price) * 100 if previous_price else 0.0

        return build_snapshot(
            definition.name,
            last_price,
            change,
            change_pct,
            history=build_snapshot_history(close_prices, last_price),
            ticker=definition.symbol,
            dates=[date.strftime("%m-%d") for date in close_prices.tail(7).index],
            value_format=definition.value_format,
        )
    except Exception as exc:
        logger.error("Error fetching YF %s: %s", definition.name, exc)
        return None


def fetch_yahoo_history(symbol: str):
    ticker = yf.Ticker(symbol)
    for period in YF_HISTORY_PERIODS:
        data = ticker.history(period=period)
        if data.empty:
            logger.warning(
                "Yahoo Finance returned no history for %s over %s",
                symbol,
                period,
            )
            continue

        if "Close" not in data:
            logger.warning("Yahoo Finance history for %s has no Close column", symbol)
            continue

        if data["Close"].dropna().empty:
            logger.warning(
                "Yahoo Finance returned no valid close prices for %s over %s",
                symbol,
                period,
            )
            continue

        return data

    logger.error("Yahoo Finance returned no usable close prices for %s", symbol)
    return None


def fetch_yahoo_intraday_latest(symbol: str) -> tuple[object, float] | None:
    try:
        data = yf.Ticker(symbol).history(
            period=YF_INTRADAY_PERIOD,
            interval=YF_INTRADAY_INTERVAL,
        )
    except Exception as exc:
        logger.warning("Yahoo Finance intraday fetch failed for %s: %s", symbol, exc)
        return None

    if data.empty or "Close" not in data:
        return None

    close_prices = data["Close"].dropna()
    if close_prices.empty:
        return None

    return close_prices.index[-1], float(close_prices.iloc[-1])


def resolve_latest_and_previous_close(close_prices, intraday_latest):
    daily_latest_timestamp = close_prices.index[-1]
    daily_latest_price = float(close_prices.iloc[-1])

    if intraday_latest is not None:
        intraday_timestamp, intraday_price = intraday_latest
        if _market_date(intraday_timestamp) >= _market_date(daily_latest_timestamp):
            previous_price = daily_latest_price
            if (
                _market_date(intraday_timestamp) == _market_date(daily_latest_timestamp)
                and isclose(intraday_price, daily_latest_price, rel_tol=1e-9)
                and len(close_prices) > 1
            ):
                previous_price = float(close_prices.iloc[-2])
            return intraday_price, previous_price

    if len(close_prices) > 1:
        return daily_latest_price, float(close_prices.iloc[-2])
    return daily_latest_price, None


def build_snapshot_history(close_prices, latest_price: float) -> list[float]:
    history = close_prices.tail(7).tolist()
    if not history:
        return [latest_price]
    if not isclose(float(history[-1]), latest_price, rel_tol=1e-9):
        history = [*history[-6:], latest_price]
    return history


def _market_date(timestamp) -> object:
    return timestamp.date() if hasattr(timestamp, "date") else timestamp
