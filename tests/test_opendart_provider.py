import os
import sys
import unittest


sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from macro_pulse.data.providers.opendart import parse_opendart_total_count


class OpenDartProviderTests(unittest.TestCase):
    def test_parse_opendart_total_count_prefers_total_count(self):
        self.assertEqual(parse_opendart_total_count({"total_count": "1,234"}), 1234)

    def test_parse_opendart_total_count_falls_back_to_list_length(self):
        self.assertEqual(parse_opendart_total_count({"list": [{}, {}]}), 2)


if __name__ == "__main__":
    unittest.main()
