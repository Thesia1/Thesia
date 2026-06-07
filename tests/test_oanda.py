from decimal import Decimal
from io import BytesIO
import unittest
from unittest.mock import patch

from urllib.error import HTTPError, URLError

from forex_bot.brokers.oanda import OandaClient, OandaConfigError, OandaConnectionError, instrument_spec_for, to_oanda_instrument
from forex_bot.config import BrokerConfig
from forex_bot.models import BrokerEnvironment, Timeframe


class OandaClientTest(unittest.TestCase):
    def test_requires_account_and_token(self):
        client = OandaClient(BrokerConfig())

        with self.assertRaises(OandaConfigError):
            client.get_market_snapshot("EUR_USD")

    def test_to_oanda_instrument_normalizes_pair(self):
        self.assertEqual(to_oanda_instrument("EUR/USD"), "EUR_USD")
        self.assertEqual(to_oanda_instrument("GBPUSD"), "GBP_USD")
        self.assertEqual(to_oanda_instrument("EURUSD"), "EUR_USD")
        self.assertEqual(to_oanda_instrument("USDJPY"), "USD_JPY")
        self.assertEqual(to_oanda_instrument("XAUUSD"), "XAU_USD")
        self.assertEqual(to_oanda_instrument("GBPJPY"), "GBP_JPY")

    def test_instrument_spec_uses_jpy_pip_size(self):
        self.assertEqual(instrument_spec_for("USD_JPY").pip_size, Decimal("0.01"))
        self.assertEqual(instrument_spec_for("GBPJPY").pip_size, Decimal("0.01"))
        self.assertEqual(instrument_spec_for("XAUUSD").pip_size, Decimal("0.01"))
        self.assertEqual(instrument_spec_for("XAUUSD").max_spread_pips, Decimal("50"))

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

    def test_diagnose_read_access_checks_auth_account_candles_and_pricing(self):
        client = OandaClient(
            BrokerConfig(
                environment=BrokerEnvironment.PRACTICE,
                account_id="101-001-1234567-001",
                token="token",
            )
        )

        def fake_get_json(path):
            if path == "/v3/accounts":
                return {"accounts": [{"id": "101-001-1234567-001"}]}
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
            if path.startswith("/v3/accounts/101-001-1234567-001/pricing"):
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
            diagnostics = client.diagnose_read_access("EUR_USD")

        self.assertTrue(diagnostics.auth_ok)
        self.assertTrue(diagnostics.account_visible)
        self.assertTrue(diagnostics.candles_ok)
        self.assertTrue(diagnostics.pricing_ok)
        self.assertEqual(diagnostics.configured_account_id, "101-...-001")
        self.assertEqual(diagnostics.visible_account_ids, ("101-...-001",))

    def test_diagnose_read_access_reports_auth_failure_without_secrets(self):
        client = OandaClient(
            BrokerConfig(
                environment=BrokerEnvironment.PRACTICE,
                account_id="101-001-1234567-001",
                token="Bearer token",
            )
        )

        with patch.object(client, "_get_json", side_effect=OandaConnectionError("OANDA API request failed with HTTP 401")):
            diagnostics = client.diagnose_read_access("EUR_USD")

        self.assertFalse(diagnostics.auth_ok)
        self.assertFalse(diagnostics.account_visible)
        self.assertFalse(diagnostics.candles_ok)
        self.assertFalse(diagnostics.pricing_ok)
        self.assertTrue(diagnostics.token_has_bearer_prefix)
        self.assertEqual(diagnostics.configured_account_id, "101-...-001")
        self.assertNotIn("token", diagnostics.error.lower())

    def test_network_error_is_wrapped(self):
        client = OandaClient(
            BrokerConfig(
                environment=BrokerEnvironment.PRACTICE,
                account_id="account",
                token="token",
            )
        )

        with patch("forex_bot.brokers.oanda.urlopen", side_effect=URLError("dns failed")):
            with self.assertRaises(OandaConnectionError) as context:
                client.get_candles("EUR_USD")

        self.assertIn("OANDA API request failed", str(context.exception))

    def test_ssl_error_message_is_actionable(self):
        client = OandaClient(
            BrokerConfig(
                environment=BrokerEnvironment.PRACTICE,
                account_id="account",
                token="token",
            )
        )

        error = URLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
        with patch("forex_bot.brokers.oanda.urlopen", side_effect=error):
            with self.assertRaises(OandaConnectionError) as context:
                client.get_candles("EUR_USD")

        self.assertIn("THESIA_CA_BUNDLE", str(context.exception))

    def test_dns_error_message_is_actionable(self):
        client = OandaClient(
            BrokerConfig(
                environment=BrokerEnvironment.PRACTICE,
                account_id="account",
                token="token",
            )
        )

        error = URLError("[Errno 8] nodename nor servname provided, or not known")
        with patch("forex_bot.brokers.oanda.urlopen", side_effect=error):
            with self.assertRaises(OandaConnectionError) as context:
                client.get_candles("EUR_USD")

        self.assertIn("DNS/network lookup failed", str(context.exception))

    def test_unauthorized_error_is_actionable(self):
        client = OandaClient(
            BrokerConfig(
                environment=BrokerEnvironment.PRACTICE,
                account_id="account",
                token="token",
            )
        )
        error = HTTPError(
            url="https://api-fxpractice.oanda.com",
            code=401,
            msg="unauthorized",
            hdrs=None,
            fp=BytesIO(b""),
        )

        with patch("forex_bot.brokers.oanda.urlopen", side_effect=error):
            with self.assertRaises(OandaConnectionError) as context:
                client.get_candles("EUR_USD")

        self.assertIn("bearer token was rejected", str(context.exception))

    def test_forbidden_error_is_actionable(self):
        client = OandaClient(
            BrokerConfig(
                environment=BrokerEnvironment.PRACTICE,
                account_id="account",
                token="token",
            )
        )
        error = HTTPError(
            url="https://api-fxpractice.oanda.com",
            code=403,
            msg="forbidden",
            hdrs=None,
            fp=BytesIO(b""),
        )

        with patch("forex_bot.brokers.oanda.urlopen", side_effect=error):
            with self.assertRaises(OandaConnectionError) as context:
                client.get_candles("EUR_USD")

        self.assertIn("not allowed", str(context.exception))


if __name__ == "__main__":
    unittest.main()
