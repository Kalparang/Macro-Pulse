import os
import sys
import unittest
from datetime import date
from unittest.mock import patch


sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from macro_pulse.data.providers.sec import parse_recent_filings
from macro_pulse.data.providers.sec import fetch_sec_data
from macro_pulse.domain.models import ValueFormat


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

    def test_fetch_sec_data_uses_count_format_for_summary_metrics(self):
        payload = {
            "filings": {
                "recent": {
                    "form": ["8-K", "10-Q"],
                    "filingDate": ["2026-06-08", "2026-06-09"],
                    "accessionNumber": ["a", "b"],
                }
            }
        }

        class Issuer:
            name = "Issuer"
            cik = "0000000000"

        def fake_fetch(_issuer, _user_agent):
            return payload

        class FixedDate(date):
            @classmethod
            def today(cls):
                return cls(2026, 6, 9)

        with (
            patch("macro_pulse.data.providers.sec.fetch_sec_submissions", fake_fetch),
            patch("macro_pulse.data.providers.sec.date", FixedDate),
        ):
            output = fetch_sec_data(issuers=(Issuer(),))

        metrics = output.dataset["disclosures_us"]
        self.assertEqual(metrics[0].price, 2)
        self.assertEqual(metrics[0].value_format, ValueFormat.COUNT_0)


if __name__ == "__main__":
    unittest.main()
