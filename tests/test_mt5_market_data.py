from decimal import Decimal
import unittest
from unittest.mock import Mock, patch

from forex_bot.brokers.mt5 import Mt5MarketDataClient, Mt5MarketDataError
from forex_bot.config import ExecutionConfig
from forex_bot.models import Timeframe
from forex_bot.symbols import mt5_symbol_candidates


class Mt5MarketDataTest(unittest.TestCase):
    def test_deriv_synthetic_aliases_resolve_to_mt5_names(self):
        self.assertIn("Volatility 50 (1s) Index", mt5_symbol_candidates("V50_1S"))
        self.assertIn("Step Index", mt5_symbol_candidates("step_index"))
        self.assertIn("Volatility 75 Index", mt5_symbol_candidates("V75"))
        self.assertIn("Volatility 75 (1s) Index", mt5_symbol_candidates("Volatility 75 (1s) Index"))

    def test_get_market_snapshot_reads_mt5_candles_ticks_and_symbol_spec(self):
        client = Mt5MarketDataClient(
            ExecutionConfig(
                mt5_login="12345",
                mt5_password="secret",
                mt5_server="Deriv-Live",
                mt5_timeout_ms=60000,
            )
        )
        mt5 = _ready_mt5_mock()

        with patch.dict("sys.modules", {"MetaTrader5": mt5}):
            snapshot = client.get_market_snapshot("V75_1S", granularity=Timeframe.M1, count=2)

        self.assertEqual(snapshot.provider, "mt5")
        self.assertEqual(snapshot.instrument.symbol, "Volatility 75 (1s) Index")
        self.assertEqual(snapshot.instrument.pip_size, Decimal("0.01"))
        self.assertEqual(snapshot.instrument.pip_value_per_unit, Decimal("1"))
        self.assertEqual(snapshot.instrument.min_units, Decimal("0.005"))
        self.assertEqual(snapshot.instrument.unit_step, Decimal("0.005"))
        self.assertEqual(snapshot.spread_pips, Decimal("5"))
        self.assertEqual(len(snapshot.candles), 2)
        self.assertEqual(snapshot.candles[-1].close, Decimal("1001.5"))
        self.assertEqual(mt5.symbol_select.call_args.args[0], "Volatility 75 (1s) Index")
        mt5.shutdown.assert_called_once()

    def test_market_data_can_attach_to_already_logged_in_terminal_after_auth_failure(self):
        client = Mt5MarketDataClient(
            ExecutionConfig(
                mt5_login="12345",
                mt5_password="secret",
                mt5_server="Deriv-Live",
                mt5_path=r"C:\Program Files\Deriv MT5\terminal64.exe",
                mt5_timeout_ms=60000,
            )
        )
        mt5 = _ready_mt5_mock()
        mt5.initialize.side_effect = [False, True]
        mt5.last_error.return_value = (-6, "Terminal: Authorization failed")

        with patch.dict("sys.modules", {"MetaTrader5": mt5}):
            snapshot = client.get_market_snapshot("V75", granularity=Timeframe.M1, count=2)

        self.assertEqual(snapshot.instrument.symbol, "Volatility 75 Index")
        self.assertEqual(mt5.initialize.call_count, 2)
        self.assertEqual(mt5.initialize.call_args_list[1].kwargs, {"timeout": 60000})

    def test_market_data_rejects_attached_terminal_with_wrong_account(self):
        client = Mt5MarketDataClient(
            ExecutionConfig(
                mt5_login="12345",
                mt5_password="secret",
                mt5_server="Deriv-Live",
                mt5_path=r"C:\Program Files\Deriv MT5\terminal64.exe",
                mt5_timeout_ms=60000,
            )
        )
        mt5 = _ready_mt5_mock()
        mt5.initialize.side_effect = [False, True]
        mt5.last_error.return_value = (-6, "Terminal: Authorization failed")
        mt5.account_info.return_value = _named(login=77777)

        with patch.dict("sys.modules", {"MetaTrader5": mt5}):
            with self.assertRaises(Mt5MarketDataError) as context:
                client.get_market_snapshot("V75", granularity=Timeframe.M1, count=2)

        self.assertIn("different account", str(context.exception))

    def test_missing_mt5_package_fails_closed(self):
        client = Mt5MarketDataClient(
            ExecutionConfig(mt5_login="12345", mt5_password="secret", mt5_server="Deriv-Live")
        )

        with patch.dict("sys.modules", {"MetaTrader5": None}):
            with self.assertRaises(Mt5MarketDataError) as context:
                client.get_market_snapshot("V75")

        self.assertIn("Synthetic-index market data", str(context.exception))


def _ready_mt5_mock():
    mt5 = Mock()
    mt5.initialize.return_value = True
    mt5.account_info.return_value = _named(login=12345)
    mt5.symbol_select.return_value = True
    mt5.symbol_info_tick.return_value = _named(bid=1000, ask=1000.05)
    mt5.symbol_info.return_value = _named(
        trade_contract_size=1,
        volume_step=0.005,
        volume_min=0.005,
        volume_max=50,
        trade_tick_size=0.01,
        trade_tick_value=1,
        margin_initial=100,
    )
    mt5.copy_rates_from_pos.return_value = [
        {"time": 1780718400, "open": 1000, "high": 1002, "low": 999, "close": 1001, "tick_volume": 10},
        {"time": 1780718460, "open": 1001, "high": 1003, "low": 1000, "close": 1001.5, "tick_volume": 11},
        {"time": 1780718520, "open": 1001.5, "high": 1004, "low": 1001, "close": 1003, "tick_volume": 12},
    ]
    mt5.TIMEFRAME_M1 = 1
    mt5.TIMEFRAME_M5 = 5
    mt5.TIMEFRAME_M15 = 15
    mt5.TIMEFRAME_M30 = 30
    mt5.TIMEFRAME_H1 = 60
    mt5.TIMEFRAME_H4 = 240
    mt5.TIMEFRAME_D1 = 1440
    mt5.TIMEFRAME_W1 = 10080
    mt5.TIMEFRAME_MN1 = 43200
    return mt5


def _named(**kwargs):
    return type("Named", (), kwargs)()


if __name__ == "__main__":
    unittest.main()
