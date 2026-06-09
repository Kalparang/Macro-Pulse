from __future__ import annotations

import math
from collections.abc import Sequence

from ..domain.models import AssetSnapshot, ValueFormat


def build_snapshot(
    name: str,
    price: float | int | None = None,
    change: float | int | None = None,
    change_pct: float | int | None = None,
    history: Sequence[float | int] | None = None,
    *,
    ticker: str | None = None,
    dates: Sequence[str] | None = None,
    value_format: ValueFormat = ValueFormat.STANDARD_2,
) -> AssetSnapshot:
    normalized_history = [
        normalized_value
        for value in (history or [])
        if (normalized_value := _finite_or_none(value)) is not None
    ]
    normalized_price = _finite_or_none(price)
    normalized_change = _finite_or_none(change)
    normalized_change_pct = _finite_or_none(change_pct)

    if not normalized_history and normalized_price is not None:
        normalized_history = [normalized_price]

    return AssetSnapshot(
        name=name,
        ticker=ticker,
        price=normalized_price,
        change=normalized_change,
        change_pct=normalized_change_pct,
        history=normalized_history,
        dates=[str(value) for value in (dates or [])],
        value_format=value_format,
    )


def _finite_or_none(value: float | int | None) -> float | None:
    if value is None:
        return None
    normalized_value = float(value)
    if not math.isfinite(normalized_value):
        return None
    return normalized_value
