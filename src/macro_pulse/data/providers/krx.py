from __future__ import annotations

from ...core.logging import get_logger
from .base import ProviderOutput, empty_provider_output, get_env_token


logger = get_logger(__name__)


def fetch_krx_data() -> ProviderOutput:
    token = get_env_token("KRX_API_KEY")
    if token is None:
        logger.info("KRX_API_KEY is not configured. Skipping KRX data.")
        return empty_provider_output("KRX_API_KEY missing")
    return ProviderOutput()
