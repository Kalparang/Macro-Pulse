import os
import sys
import unittest


sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from macro_pulse.data.providers.fred import FredSeriesDefinition, parse_fred_snapshot
from macro_pulse.domain.models import ValueFormat


SAMPLE_FRED_CSV = """observation_date,DGS2
2026-06-01,3.81
2026-06-02,.
2026-06-03,3.83
2026-06-04,3.79
"""

SAMPLE_LEGACY_FRED_CSV = """DATE,DGS2
2026-06-03,3.83
2026-06-04,3.79
"""


class FredProviderTests(unittest.TestCase):
    def test_parse_fred_snapshot_uses_latest_numeric_points(self):
        snapshot = parse_fred_snapshot(
            FredSeriesDefinition(
                "US 2Y Treasury",
                "DGS2",
                value_format=ValueFormat.YIELD_3,
            ),
            SAMPLE_FRED_CSV,
        )

        self.assertEqual(snapshot.name, "US 2Y Treasury")
        self.assertEqual(snapshot.history, [3.81, 3.83, 3.79])
        self.assertEqual(snapshot.dates, ["06-01", "06-03", "06-04"])
        self.assertAlmostEqual(snapshot.price, 3.79)
        self.assertAlmostEqual(snapshot.change, -0.04)
        self.assertIsNone(snapshot.change_pct)
        self.assertEqual(snapshot.value_format, ValueFormat.YIELD_3)

    def test_parse_fred_snapshot_accepts_legacy_date_header(self):
        snapshot = parse_fred_snapshot(
            FredSeriesDefinition("US 2Y Treasury", "DGS2"),
            SAMPLE_LEGACY_FRED_CSV,
        )

        self.assertEqual(snapshot.dates, ["06-03", "06-04"])
        self.assertAlmostEqual(snapshot.price, 3.79)


if __name__ == "__main__":
    unittest.main()
