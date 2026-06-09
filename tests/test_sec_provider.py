import os
import sys
import unittest
from datetime import date


sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from macro_pulse.data.providers.sec import parse_recent_filings


class SecProviderTests(unittest.TestCase):
    def test_parse_recent_filings_filters_by_date(self):
        filings = parse_recent_filings(
            {
                "filings": {
                    "recent": {
                        "form": ["8-K", "10-Q", "4"],
                        "filingDate": ["2026-06-08", "2026-06-01", "2026-06-09"],
                        "accessionNumber": ["a", "b", "c"],
                    }
                }
            },
            since=date(2026, 6, 7),
        )

        self.assertEqual(
            filings,
            [
                {"form": "8-K", "filing_date": "2026-06-08", "accession": "a"},
                {"form": "4", "filing_date": "2026-06-09", "accession": "c"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
