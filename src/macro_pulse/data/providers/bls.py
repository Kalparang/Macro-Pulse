from __future__ import annotations

from ...core.logging import get_logger
from .base import ProviderOutput


logger = get_logger(__name__)


def fetch_bls_data() -> ProviderOutput:
    # BLS supports limited public API access without a key. Series mapping is
    # intentionally left explicit so the report does not fetch unused data.
    logger.info("BLS provider is not configured with series yet. Skipping.")
    return ProviderOutput()
