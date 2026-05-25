import unittest

from forex_bot.__main__ import scan_pair
from forex_bot.models import SignalState


class CliTest(unittest.TestCase):
    def test_fixture_source_is_explicit(self):
        decision = scan_pair("EUR_USD", source="fixture")

        self.assertEqual(decision.state, SignalState.TRADE_CANDIDATE)

    def test_pair_slash_is_normalized(self):
        decision = scan_pair("EUR/USD", source="fixture")

        self.assertEqual(decision.symbol, "EUR_USD")


if __name__ == "__main__":
    unittest.main()
