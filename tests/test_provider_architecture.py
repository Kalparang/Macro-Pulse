import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from macro_pulse.data.cache import TtlCache
from macro_pulse.data.providers.krx import fetch_krx_data
from macro_pulse.domain.models import MarketSnapshot


class ProviderArchitectureTests(unittest.TestCase):
    def test_ttl_cache_returns_value_before_expiry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = TtlCache(Path(temp_dir))

            cache.set_text("provider:key", "payload")

            self.assertEqual(cache.get_text("provider:key", ttl_seconds=60), "payload")

    def test_ttl_cache_skips_expired_value(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = TtlCache(Path(temp_dir))

            cache.set_text("provider:key", "payload")
            time.sleep(0.01)

            self.assertIsNone(cache.get_text("provider:key", ttl_seconds=0))

    def test_market_snapshot_converts_to_asset_snapshot(self):
        snapshot = MarketSnapshot(
            category="indices_overseas",
            name="S&P 500",
            price=7400.0,
            change=10.0,
            change_pct=0.14,
            ticker="^GSPC",
        )

        asset = snapshot.to_asset_snapshot()

        self.assertEqual(asset.name, "S&P 500")
        self.assertEqual(asset.price, 7400.0)
        self.assertEqual(asset.ticker, "^GSPC")

    def test_keyed_provider_gracefully_skips_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            output = fetch_krx_data()

        self.assertEqual(output.dataset, {})
        self.assertIn("KRX_API_KEY missing", output.warnings)


if __name__ == "__main__":
    unittest.main()
