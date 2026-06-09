from __future__ import annotations

from ...core.logging import get_logger
from .base import ProviderOutput


logger = get_logger(__name__)


def fetch_sec_data() -> ProviderOutput:
    # SEC EDGAR does not require a token, but future implementation must send
    # a descriptive User-Agent and respect fair-access request limits.
    logger.info("SEC provider is not configured with tracked issuers yet. Skipping.")
    return ProviderOutput()
