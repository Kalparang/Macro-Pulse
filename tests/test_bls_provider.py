import os
import sys
import unittest


sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from macro_pulse.data.providers.bls import BlsSeriesDefinition, parse_bls_snapshot
from macro_pulse.domain.models import ValueFormat


class BlsProviderTests(unittest.TestCase):
    def test_parse_bls_snapshot_orders_points_and_calculates_change(self):
        snapshot = parse_bls_snapshot(
            BlsSeriesDefinition(
                "US Unemployment Rate",
                "LNS14000000",
                value_format=ValueFormat.PERCENT_2,
            ),
            {
                "seriesID": "LNS14000000",
                "data": [
                    {
                        "year": "2026",
                        "period": "M02",
                        "periodName": "February",
                        "value": "4.2",
                    },
                    {
                        "year": "2026",
                        "period": "M01",
                        "periodName": "January",
                        "value": "4.0",
                    },
                ],
            },
        )

        self.assertEqual(snapshot.name, "US Unemployment Rate")
        self.assertEqual(snapshot.history, [4.0, 4.2])
        self.assertEqual(snapshot.dates, ["2026-Jan", "2026-Feb"])
        self.assertAlmostEqual(snapshot.price, 4.2)
        self.assertAlmostEqual(snapshot.change, 0.2)
        self.assertAlmostEqual(snapshot.change_pct, 5.0)
        self.assertEqual(snapshot.value_format, ValueFormat.PERCENT_2)


if __name__ == "__main__":
    unittest.main()
