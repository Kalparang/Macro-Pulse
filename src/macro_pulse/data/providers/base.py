from __future__ import annotations

import os
from dataclasses import dataclass, field

from ...domain.models import (
    DisclosureItem,
    EventItem,
    FlowSnapshot,
    MacroSeries,
    ReportDataset,
)


@dataclass(slots=True)
class ProviderOutput:
    dataset: ReportDataset = field(default_factory=dict)
    macro_series: list[MacroSeries] = field(default_factory=list)
    events: list[EventItem] = field(default_factory=list)
    disclosures: list[DisclosureItem] = field(default_factory=list)
    flows: list[FlowSnapshot] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def get_env_token(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def empty_provider_output(message: str = "") -> ProviderOutput:
    output = ProviderOutput()
    if message:
        output.warnings.append(message)
    return output
