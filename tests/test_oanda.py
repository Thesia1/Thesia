from decimal import Decimal
import unittest
from unittest.mock import patch

from forex_bot.brokers.oanda import OandaClient, OandaConfigError, instrument_spec_for, to_oanda_instrument
from forex_bot.config import BrokerConfig
from forex_bot.models import BrokerEnvironment, Timeframe


class OandaClientTest(unittest.TestCase):
    def test_requires_account_and_token(self):
        client = OandaClient(BrokerConfig())

        with self.assertRaises(OandaConfigError):
            client.get_market_snapshot("EUR_USD")

    def test_to_oanda_instrument_normalizes_pair(self):
        self.assertEqual(to_oanda_instrument("EUR/USD"), "EUR_USD")

    def test_instrument_spec_uses_jpy_pip_size(self):
        self.assertEqual(instrument_spec_for("USD_JPY").pip_size, Decimal("0.01"))

    def test_get_market_snapshot_parses_candles_and_spread(self):
        client = OandaClient(
            BrokerConfig(
                environment=BrokerEnvironment.PRACTICE,
                account_id="account",
                token="token",
            )
        )

        def fake_get_json(path):
            if path.startswith("/v3/instruments/EUR_USD/candles"):
                return {
                    "candles": [
                        {
                            "complete": True,
                            "time": "2026-05-25T15:00:00.000000000Z",
                            "volume": 10,
                            "mid": {"o": "1.1000", "h": "1.1010", "l": "1.0990", "c": "1.1005"},
                        }
                    ]
                }
            if path.startswith("/v3/accounts/account/pricing"):
                return {
                    "prices": [
                        {
                            "bids": [{"price": "1.1000"}],
                            "asks": [{"price": "1.1002"}],
                        }
                    ]
                }
            raise AssertionError(f"unexpected path {path}")

        with patch.object(client, "_get_json", side_effect=fake_get_json):
            snapshot = client.get_market_snapshot("EUR_USD", granularity=Timeframe.H1, count=1)

        self.assertEqual(len(snapshot.candles), 1)
        self.assertEqual(snapshot.candles[0].close, Decimal("1.1005"))
        self.assertEqual(snapshot.spread_pips, Decimal("2"))


if __name__ == "__main__":
    unittest.main()

