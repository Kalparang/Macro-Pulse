from __future__ import annotations

from ...core.logging import get_logger
from .base import ProviderOutput, empty_provider_output, get_env_token


logger = get_logger(__name__)


def fetch_bea_data() -> ProviderOutput:
    token = get_env_token("BEA_API_KEY")
    if token is None:
        logger.info("BEA_API_KEY is not configured. Skipping BEA data.")
        return empty_provider_output("BEA_API_KEY missing")
    return ProviderOutput()
