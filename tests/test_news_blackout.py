from datetime import datetime, timezone
import json
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from forex_bot.config import NewsConfig
from forex_bot.news.blackout import EconomicCalendarEvent, blackout_from_config, evaluate_news_blackout


class NewsBlackoutTest(unittest.TestCase):
    def test_high_impact_event_blocks_matching_currency_pair_inside_window(self):
        decision = evaluate_news_blackout(
            symbol="EUR_USD",
            now=datetime(2026, 6, 4, 14, 30, tzinfo=timezone.utc),
            events=(
                EconomicCalendarEvent(
                    title="US Nonfarm Payrolls",
                    currency="USD",
                    impact="high",
                    starts_at=datetime(2026, 6, 4, 15, 0, tzinfo=timezone.utc),
                ),
            ),
        )

        self.assertTrue(decision.blocked)
        self.assertIn("US Nonfarm Payrolls", decision.reason)
        self.assertEqual(len(decision.matched_events), 1)

    def test_low_impact_event_does_not_block_high_impact_gate(self):
        decision = evaluate_news_blackout(
            symbol="EUR_USD",
            now=datetime(2026, 6, 4, 14, 30, tzinfo=timezone.utc),
            events=(
                EconomicCalendarEvent(
                    title="Minor survey",
                    currency="USD",
                    impact="low",
                    starts_at=datetime(2026, 6, 4, 15, 0, tzinfo=timezone.utc),
                ),
            ),
        )

        self.assertFalse(decision.blocked)
        self.assertEqual(decision.matched_events, ())

    def test_blackout_from_config_loads_local_calendar_file(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "calendar.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "title": "ECB Rate Decision",
                            "currency": "EUR",
                            "impact": "high",
                            "starts_at": "2026-06-04T15:00:00Z",
                            "source": "test",
                        }
                    ]
                )
            )
            decision = blackout_from_config(
                "EUR_USD",
                datetime(2026, 6, 4, 14, 30, tzinfo=timezone.utc),
                NewsConfig(blackout_events_file=str(path)),
            )

        self.assertTrue(decision.blocked)
        self.assertEqual(decision.checked_event_count, 1)


if __name__ == "__main__":
    unittest.main()
