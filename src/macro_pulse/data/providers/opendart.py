from __future__ import annotations

from ...core.logging import get_logger
from .base import ProviderOutput, empty_provider_output, get_env_token


logger = get_logger(__name__)


def fetch_opendart_data() -> ProviderOutput:
    token = get_env_token("OPENDART_API_KEY")
    if token is None:
        logger.info("OPENDART_API_KEY is not configured. Skipping OpenDART data.")
        return empty_provider_output("OPENDART_API_KEY missing")
    return ProviderOutput()
