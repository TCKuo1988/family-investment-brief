import copy
from datetime import date
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import push_line_verified as line
from market_sessions import expected_sessions
from update_us import resolve
from validate_report import load_report, validate_report


class MorningReportTests(unittest.TestCase):
    def setUp(self):
        self.report = load_report(line.REPORT.read_bytes())
        self.edition = date.fromisoformat(self.report["edition_date"])

    def test_session_calendars_are_independent(self):
        days = expected_sessions(date(2026, 11, 27))
        self.assertEqual(days["us"][0], date(2026, 11, 25))
        self.assertEqual(days["tw"][0], date(2026, 11, 26))
        self.assertEqual(expected_sessions(date(2026, 11, 30))["us"],
                         (date(2026, 11, 27), date(2026, 11, 25)))
        self.assertEqual(expected_sessions(date(2026, 9, 29))["tw"][0], date(2026, 9, 24))

    def test_report_and_preview_use_same_quote(self):
        validate_report(self.report, self.edition)
        message = line.render(self.report)
        voo = self.report["us_quotes"]["VOO"]
        expected = f"{voo['close']:,.2f}" if voo["close"] is not None else voo["note"]
        self.assertIn(f"VOO  {expected}", message)
        self.assertIn("\n🇺🇸", message)
        self.assertNotIn(r"\n", message)
        for text in ("台積電 ADR", "NVDA｜", "TSLA｜", "SPCX｜", "1～4", "3～12", line.SITE):
            self.assertIn(text, message)

    def test_missing_close_and_stale_edition(self):
        bad = copy.deepcopy(self.report)
        bad["us_quotes"]["VOO"] = {"close": None, "percent": None, "note": "預期交易日收盤價未核實"}
        validate_report(bad, self.edition)
        self.assertIn("VOO  預期交易日收盤價未核實", line.render(bad))
        bad["us_quotes"]["date"] = "2000-01-01"
        with self.assertRaises(ValueError):
            validate_report(bad, self.edition)
        with self.assertRaises(ValueError):
            validate_report(self.report, date(2000, 1, 1))

    def test_invalid_json_and_mismatched_price_sources(self):
        for invalid in ('{"foo": 1, "foo": 2}', '{"foo": NaN}'):
            with self.assertRaises(ValueError):
                load_report(invalid)
        with patch("update_us.nasdaq", return_value=((150, 145), "nasdaq")), \
             patch("update_us.stockanalysis", return_value=((145, 145), "stockanalysis")):
            self.assertIsNone(resolve("NVDA", (date(2026, 11, 17), date(2026, 11, 16)))["close"])

    def test_line_retry_key_and_duplicate_acceptance(self):
        duplicate = HTTPError("https://api.line.me", 409, "Conflict",
                              {"X-Line-Accepted-Request-Id": "mock-id"}, None)
        with patch.dict(line.os.environ, {"LINE_CHANNEL_ACCESS_TOKEN": "mock", "LINE_GROUP_ID": "mock"}), \
             patch.object(line, "urlopen", side_effect=duplicate) as request:
            line.send("第一行\n第二行", self.edition)
            line.send("變更過的晨報", self.edition)
        first, second = [call.args[0] for call in request.call_args_list]
        self.assertEqual(first.get_header("X-line-retry-key"), second.get_header("X-line-retry-key"))
        self.assertEqual(json.loads(first.data)["messages"][0]["text"], "第一行\n第二行")


if __name__ == "__main__":
    unittest.main()
