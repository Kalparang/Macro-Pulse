import os
import sys
import unittest
from unittest.mock import MagicMock, patch


sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from macro_pulse.data.providers.krx import (
    KRX_METRICS,
    KRX_SNAPSHOTS,
    extract_krx_metric,
    extract_krx_snapshot,
    fetch_krx_payload,
)


class KrxProviderTests(unittest.TestCase):
    def test_extract_krx_metric_reads_aliases_and_scales_values(self):
        payload = {
            "output": [
                {
                    "UP_CNT": "1,234",
                    "ACC_TRDVAL": "12,300,000,000,000",
                    "FRGN_NTBY": "120,000,000,000",
                }
            ]
        }

        advancers = KRX_METRICS[0]
        trading_value = KRX_METRICS[2]
        foreign_net_buy = KRX_METRICS[3]

        self.assertEqual(extract_krx_metric(payload, advancers), 1234)
        self.assertAlmostEqual(extract_krx_metric(payload, trading_value), 12.3)
        self.assertAlmostEqual(extract_krx_metric(payload, foreign_net_buy), 1200)

    def test_extract_krx_metric_calculates_market_breadth_from_stock_rows(self):
        payloads = [
            {
                "output": [
                    {"CMPPREVDD_PRC": "10", "ACC_TRDVAL": "1,000,000,000"},
                    {"CMPPREVDD_PRC": "-5", "ACC_TRDVAL": "2,000,000,000"},
                ]
            },
            {
                "output": [
                    {"CMPPREVDD_PRC": "0", "ACC_TRDVAL": "3,000,000,000"},
                    {"CMPPREVDD_PRC": "7", "ACC_TRDVAL": "4,000,000,000"},
                ]
            },
        ]

        self.assertEqual(extract_krx_metric(payloads, KRX_METRICS[0]), 2)
        self.assertEqual(extract_krx_metric(payloads, KRX_METRICS[1]), 1)
        self.assertAlmostEqual(extract_krx_metric(payloads, KRX_METRICS[2]), 0.01)

    def test_extract_krx_snapshot_reads_index_name_and_etf_code(self):
        index_payload = {
            "output": [
                {
                    "IDX_NM": "KOSPI 200",
                    "CLSPRC_IDX": "430.12",
                    "CMPPREVDD_IDX": "1.23",
                    "FLUC_RT": "0.29",
                }
            ]
        }
        etf_payload = {
            "output": [
                {
                    "ISU_CD": "091160",
                    "ISU_NM": "KODEX Semiconductors",
                    "TDD_CLSPRC": "42,500",
                    "CMPPREVDD_PRC": "300",
                    "FLUC_RT": "0.71",
                }
            ]
        }

        kospi200 = extract_krx_snapshot([index_payload], KRX_SNAPSHOTS[2])
        semiconductor = extract_krx_snapshot([etf_payload], KRX_SNAPSHOTS[3])

        self.assertIsNotNone(kospi200)
        self.assertEqual(kospi200.name, "KOSPI200")
        self.assertAlmostEqual(kospi200.price, 430.12)
        self.assertIsNotNone(semiconductor)
        self.assertEqual(semiconductor.name, "Korea Semiconductors")
        self.assertAlmostEqual(semiconductor.price, 42500)

    @patch("macro_pulse.data.providers.krx.TtlCache")
    @patch("macro_pulse.data.providers.krx.urlopen")
    def test_fetch_krx_payload_sends_auth_key_header(self, mock_urlopen, mock_cache_class):
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"output": []}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        payload = fetch_krx_payload("https://openapi.krx.co.kr/example", "secret")

        self.assertEqual(payload, {"output": []})
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Auth_key"), "secret")
        self.assertNotIn("auth_key=", request.full_url)


if __name__ == "__main__":
    unittest.main()
