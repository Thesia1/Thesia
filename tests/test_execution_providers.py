import unittest
from decimal import Decimal
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import Mock, patch

from forex_bot.config import ExecutionConfig
from forex_bot.execution.base import OrderSubmissionRequest
from forex_bot.execution.factory import create_execution_client
from forex_bot.execution.ledger import FileOrderLedger
from forex_bot.execution.mt5 import Mt5ExecutionClient
from forex_bot.models import BrokerEnvironment, Direction, ExecutionProvider


class ExecutionProviderTest(unittest.TestCase):
    def test_creates_mt5_execution_client(self):
        client = create_execution_client(ExecutionConfig(provider=ExecutionProvider.MT5))

        self.assertIsInstance(client, Mt5ExecutionClient)

    def test_mt5_diagnostics_report_missing_credentials(self):
        client = create_execution_client(ExecutionConfig(provider=ExecutionProvider.MT5))

        diagnostics = client.diagnose()

        self.assertEqual(diagnostics.provider, "mt5")
        self.assertFalse(diagnostics.configured)
        self.assertFalse(diagnostics.can_place_orders)
        self.assertIn("MT5_LOGIN", diagnostics.reason)

    def test_mt5_diagnostics_report_configured_but_execution_disabled(self):
        client = create_execution_client(
            ExecutionConfig(
                provider=ExecutionProvider.MT5,
                environment=BrokerEnvironment.PRACTICE,
                mt5_login="12345",
                mt5_password="secret",
                mt5_server="Deriv-Demo",
            )
        )

        diagnostics = client.diagnose()

        self.assertEqual(diagnostics.provider, "mt5")
        self.assertTrue(diagnostics.configured)
        self.assertFalse(diagnostics.can_place_orders)
        self.assertTrue(diagnostics.login_present)
        self.assertTrue(diagnostics.password_present)
        self.assertEqual(diagnostics.server, "Der...emo")
        self.assertIn("run the terminal probe", diagnostics.reason)

    def test_mt5_live_read_only_probe_reports_missing_package(self):
        client = create_execution_client(
            ExecutionConfig(
                provider=ExecutionProvider.MT5,
                environment=BrokerEnvironment.LIVE,
                mt5_login="12345",
                mt5_password="secret",
                mt5_server="Deriv-Live",
            )
        )

        with patch.dict("sys.modules", {"MetaTrader5": None}):
            diagnostics = client.diagnose(probe_terminal=True, symbols=("EUR_USD",))

        self.assertEqual(diagnostics.environment, "live")
        self.assertFalse(diagnostics.can_place_orders)
        self.assertFalse(diagnostics.read_only_probe_ok)
        self.assertIn("MetaTrader5 Python package is not available", diagnostics.probe_error)
        self.assertIn("Windows", diagnostics.probe_error)
        self.assertIn("recommended_next_step", diagnostics.probe_details)

    def test_mt5_live_read_only_probe_can_verify_account_positions_and_ticks(self):
        client = create_execution_client(
            ExecutionConfig(
                provider=ExecutionProvider.MT5,
                environment=BrokerEnvironment.LIVE,
                mt5_login="12345",
                mt5_password="secret",
                mt5_server="Deriv-Live",
            )
        )
        mt5 = Mock()
        mt5.initialize.return_value = True
        mt5.account_info.return_value = _named(
            login=12345,
            company="Deriv",
            server="Deriv-Live",
            currency="USD",
            balance=1000,
            equity=1000,
            margin_free=900,
        )
        mt5.positions_get.return_value = []
        mt5.orders_get.return_value = []
        mt5.symbol_select.return_value = True
        mt5.symbol_info_tick.return_value = _named(bid=1.1, ask=1.2)
        mt5.symbol_info.return_value = _named(trade_mode=1)

        with patch.dict("sys.modules", {"MetaTrader5": mt5}):
            diagnostics = client.diagnose(probe_terminal=True, symbols=("EUR_USD",))

        self.assertEqual(diagnostics.environment, "live")
        self.assertTrue(diagnostics.terminal_connected)
        self.assertTrue(diagnostics.account_info_visible)
        self.assertTrue(diagnostics.positions_visible)
        self.assertTrue(diagnostics.orders_visible)
        self.assertTrue(diagnostics.ticks_visible)
        self.assertTrue(diagnostics.symbol_info_visible)
        self.assertTrue(diagnostics.read_only_probe_ok)
        self.assertTrue(diagnostics.reconciliation_ok)
        self.assertTrue(diagnostics.account_equity_visible)
        self.assertTrue(diagnostics.margin_visible)
        self.assertTrue(diagnostics.duplicate_order_check_ok)
        self.assertEqual(diagnostics.account_login, "12...45")
        self.assertEqual(diagnostics.symbols_checked, ("EURUSD",))
        self.assertFalse(diagnostics.can_place_orders)
        mt5.shutdown.assert_called_once()

    def test_mt5_probe_explains_ipc_timeout_recovery(self):
        client = create_execution_client(
            ExecutionConfig(
                provider=ExecutionProvider.MT5,
                environment=BrokerEnvironment.LIVE,
                mt5_login="12345",
                mt5_password="secret",
                mt5_server="Deriv-Live",
                mt5_path=r"C:\Program Files\Deriv MT5\terminal64.exe",
                mt5_timeout_ms=60000,
            )
        )
        mt5 = Mock()
        mt5.initialize.return_value = False
        mt5.last_error.return_value = (-10005, "IPC timeout")

        with patch.dict("sys.modules", {"MetaTrader5": mt5}):
            diagnostics = client.diagnose(probe_terminal=True, symbols=("EUR_USD",))

        self.assertFalse(diagnostics.reconciliation_ok)
        self.assertFalse(diagnostics.can_place_orders)
        self.assertIn("IPC timeout", diagnostics.probe_error)
        self.assertEqual(diagnostics.probe_details["timeout_ms"], 60000)
        self.assertTrue(diagnostics.probe_details["mt5_path_present"])
        self.assertFalse(diagnostics.probe_details["mt5_path_exists"])
        self.assertIn("recommended_actions", diagnostics.probe_details)
        self.assertTrue(any("same Windows user" in action for action in diagnostics.probe_details["recommended_actions"]))

    def test_mt5_probe_can_enable_order_placement_when_switch_is_enabled(self):
        client = create_execution_client(
            ExecutionConfig(
                provider=ExecutionProvider.MT5,
                environment=BrokerEnvironment.LIVE,
                mt5_login="12345",
                mt5_password="secret",
                mt5_server="Deriv-Live",
                order_placement_enabled=True,
            )
        )
        mt5 = _ready_mt5_mock()

        with patch.dict("sys.modules", {"MetaTrader5": mt5}):
            diagnostics = client.diagnose(probe_terminal=True, symbols=("EUR_USD",))

        self.assertTrue(diagnostics.reconciliation_ok)
        self.assertTrue(diagnostics.can_place_orders)
        self.assertIn("order placement is enabled", diagnostics.reason)

    def test_mt5_submit_order_uses_ledger_and_order_send(self):
        with TemporaryDirectory() as temp_dir:
            ledger = FileOrderLedger(Path(temp_dir) / "orders.jsonl")
            client = create_execution_client(
                ExecutionConfig(
                    provider=ExecutionProvider.MT5,
                    environment=BrokerEnvironment.LIVE,
                    mt5_login="12345",
                    mt5_password="secret",
                    mt5_server="Deriv-Live",
                    order_placement_enabled=True,
                )
            )
            mt5 = _ready_mt5_mock()
            mt5.order_send.return_value = _named(retcode=10009, order=987, deal=654, comment="filled")

            with patch.dict("sys.modules", {"MetaTrader5": mt5}):
                result = client.submit_order(
                    OrderSubmissionRequest(
                        symbol="EUR_USD",
                        direction=Direction.BUY,
                        units=Decimal("1000"),
                        entry_price=Decimal("1.1000"),
                        stop_loss=Decimal("1.0950"),
                        take_profit=Decimal("1.1100"),
                        strategy_decision_id="decision-1",
                        idempotency_key="decision-1:EUR_USD",
                    ),
                    ledger=ledger,
                )

            self.assertEqual(result.state, "ACCEPTED")
            self.assertEqual(result.broker_order_id, "987")
            self.assertEqual(len(ledger.records()), 1)
            order_request = mt5.order_send.call_args.args[0]
            self.assertEqual(order_request["symbol"], "EURUSD")
            self.assertEqual(order_request["volume"], 0.01)

    def test_mt5_submit_order_blocks_duplicate_ledger_key(self):
        with TemporaryDirectory() as temp_dir:
            ledger = FileOrderLedger(Path(temp_dir) / "orders.jsonl")
            request = OrderSubmissionRequest(
                symbol="EUR_USD",
                direction=Direction.BUY,
                units=Decimal("1000"),
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
                strategy_decision_id="decision-1",
                idempotency_key="decision-1:EUR_USD",
            )
            ledger.record_submission(
                idempotency_key=request.idempotency_key,
                strategy_decision_id=request.strategy_decision_id,
                symbol=request.symbol,
                result=_named_result("ACCEPTED", request.idempotency_key),
            )
            client = create_execution_client(
                ExecutionConfig(
                    provider=ExecutionProvider.MT5,
                    environment=BrokerEnvironment.LIVE,
                    mt5_login="12345",
                    mt5_password="secret",
                    mt5_server="Deriv-Live",
                    order_placement_enabled=True,
                )
            )

            result = client.submit_order(request, ledger=ledger)

        self.assertEqual(result.state, "DUPLICATE_BLOCKED")


if __name__ == "__main__":
    unittest.main()


def _named(**kwargs):
    return type("Named", (), kwargs)()


def _ready_mt5_mock():
    mt5 = Mock()
    mt5.initialize.return_value = True
    mt5.account_info.return_value = _named(
        login=12345,
        company="Deriv",
        server="Deriv-Live",
        currency="USD",
        balance=1000,
        equity=1000,
        margin_free=900,
    )
    mt5.positions_get.return_value = []
    mt5.orders_get.return_value = []
    mt5.symbol_select.return_value = True
    mt5.symbol_info_tick.return_value = _named(bid=1.1, ask=1.2)
    mt5.symbol_info.return_value = _named(
        trade_mode=1,
        trade_contract_size=100000,
        volume_step=0.01,
        volume_min=0.01,
        volume_max=100,
    )
    mt5.ORDER_TYPE_BUY = 0
    mt5.ORDER_TYPE_SELL = 1
    mt5.TRADE_ACTION_DEAL = 1
    mt5.ORDER_TIME_GTC = 0
    mt5.ORDER_FILLING_FOK = 0
    mt5.TRADE_RETCODE_DONE = 10009
    mt5.TRADE_RETCODE_PLACED = 10008
    return mt5


def _named_result(state, idempotency_key):
    from forex_bot.execution.base import OrderSubmissionResult

    return OrderSubmissionResult(state=state, idempotency_key=idempotency_key, broker_order_id="old")
