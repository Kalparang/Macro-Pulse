import math
import os
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd


if "yfinance" not in sys.modules:
    fake_yfinance = types.SimpleNamespace(Ticker=None)
    sys.modules["yfinance"] = fake_yfinance

sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from macro_pulse.data.providers import yahoo
from macro_pulse.domain.models import TickerDefinition


class FakeTicker:
    def __init__(self, frames):
        self.frames = list(frames)
        self.calls = 0

    def history(self, period):
        frame = self.frames[min(self.calls, len(self.frames) - 1)]
        self.calls += 1
        return frame


class YahooProviderTests(unittest.TestCase):
    def test_fetch_yahoo_snapshot_uses_last_valid_close(self):
        frame = pd.DataFrame(
            {"Close": [100.0, 105.0, math.nan]},
            index=pd.date_range("2026-06-01", periods=3),
        )

        with patch.object(yahoo.yf, "Ticker", return_value=FakeTicker([frame])):
            snapshot = yahoo.fetch_yahoo_snapshot(TickerDefinition("KOSPI", "^KS11"))

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.price, 105.0)
        self.assertEqual(snapshot.change, 5.0)
        self.assertEqual(snapshot.change_pct, 5.0)
        self.assertEqual(snapshot.history, [100.0, 105.0])

    def test_fetch_yahoo_snapshot_retries_longer_periods(self):
        empty_close_frame = pd.DataFrame(
            {"Close": [math.nan]},
            index=pd.date_range("2026-06-01", periods=1),
        )
        valid_frame = pd.DataFrame(
            {"Close": [3000.0, 3010.0]},
            index=pd.date_range("2026-05-30", periods=2),
        )

        with patch.object(
            yahoo.yf,
            "Ticker",
            return_value=FakeTicker([empty_close_frame, valid_frame]),
        ):
            snapshot = yahoo.fetch_yahoo_snapshot(
                TickerDefinition("Shanghai Composite", "000001.SS")
            )

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.price, 3010.0)
        self.assertEqual(snapshot.change, 10.0)


if __name__ == "__main__":
    unittest.main()
