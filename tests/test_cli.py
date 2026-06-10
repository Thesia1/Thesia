from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from forex_bot.__main__ import autotrade_cycle_response, execute_live_response, persist_scan_result, scan_pair, scan_pair_response, scan_pairs_response, to_primitive
from forex_bot.brokers.base import MarketSnapshot
from forex_bot.config import BrokerConfig, BotConfig, ExecutionConfig, NewsConfig
from forex_bot.execution.base import ExecutionDiagnostics, OrderPreflightResult, OrderSubmissionResult
from forex_bot.fixtures import load_fixture_candles
from forex_bot.models import BotMode, BrokerEnvironment, BrokerProvider, Candle, Direction, ExecutionProvider, InstrumentSpec, RiskDecision, SignalState, StrategyDecision, Timeframe, TradeCandidate
from forex_bot.notifications import NotificationResult


class CliTest(unittest.TestCase):
    def test_fixture_source_is_explicit(self):
        decision = scan_pair("EUR_USD", source="fixture")

        self.assertEqual(decision.state, SignalState.TRADE_CANDIDATE)

    def test_pair_slash_is_normalized(self):
        decision = scan_pair("EUR/USD", source="fixture")

        self.assertEqual(decision.symbol, "EUR_USD")

    def test_fixture_source_ignores_broker_override(self):
        decision = scan_pair("EUR_USD", source="fixture", broker_provider=BrokerProvider.FOREX_COM)

        self.assertEqual(decision.state, SignalState.TRADE_CANDIDATE)

    def test_scan_response_marks_fixture_data(self):
        response = scan_pair_response("EUR_USD", source="fixture")

        self.assertEqual(response.market_data.source, "fixture")
        self.assertEqual(response.market_data.provider, "local_fixture")
        self.assertEqual(response.market_data.broker_environment, "none")
        self.assertIn("Fixture data", response.market_data.warning)
        self.assertGreater(response.market_data.complete_candle_count, 0)

    def test_scan_response_marks_broker_data(self):
        candles = [
            Candle(
                symbol="EUR_USD",
                timeframe=Timeframe.H1,
                timestamp=__import__("datetime").datetime.fromisoformat("2026-06-04T21:00:00+00:00"),
                open=Decimal("1.1600"),
                high=Decimal("1.1620"),
                low=Decimal("1.1590"),
                close=Decimal("1.1610"),
            )
        ] * 6
        snapshot = MarketSnapshot(
            candles=candles,
            instrument=_eur_usd(),
            spread_pips=Decimal("0.8"),
            provider="oanda",
        )

        class FakeBrokerClient:
            def get_market_snapshot(self, symbol, granularity=Timeframe.H1, count=200):
                return snapshot

        with patch(
            "forex_bot.__main__.load_config_from_env",
            return_value=BotConfig(
                broker=BrokerConfig(provider=BrokerProvider.OANDA, environment=BrokerEnvironment.PRACTICE),
                execution=ExecutionConfig(
                    provider=ExecutionProvider.MT5,
                    mt5_login="12345",
                    mt5_password="secret",
                    mt5_server="Deriv-Demo",
                ),
            ),
        ), patch("forex_bot.__main__.create_broker_client", return_value=FakeBrokerClient()):
            response = scan_pair_response("EUR_USD", source="broker")

        self.assertEqual(response.market_data.source, "broker")
        self.assertEqual(response.market_data.provider, "oanda")
        self.assertEqual(response.market_data.broker_environment, "practice")
        self.assertEqual(response.market_data.latest_complete_candle.close, Decimal("1.1610"))
        self.assertEqual(response.market_data.warning, "")
        self.assertEqual(response.execution.provider, "mt5")
        self.assertTrue(response.execution.configured)
        self.assertFalse(response.execution.can_place_orders)

    def test_multi_pair_scan_returns_batch_summary(self):
        response = scan_pairs_response(("EUR_USD", "EUR_USD"), source="fixture", paper_preview=True)

        self.assertEqual(response.scanned_count, 2)
        self.assertEqual(response.candidate_count, 2)
        self.assertEqual(response.tradeable_paper_count, 2)
        self.assertEqual(len(response.scans), 2)

    def test_scan_response_can_show_all_strategy_decisions(self):
        response = scan_pair_response("EUR_USD", source="fixture", show_all_strategies=True)

        self.assertIsNotNone(response.all_strategy_decisions)
        self.assertEqual(
            [decision.setup_name for decision in response.all_strategy_decisions],
            ["fresh_strong_zone_continuation", "trendline_zone_sequence"],
        )
        self.assertIsNotNone(response.market_bias)
        self.assertEqual(response.market_bias.pair_asset, "EUR_USD")

    def test_scan_response_hides_all_strategy_decisions_by_default(self):
        response = scan_pair_response("EUR_USD", source="fixture")

        primitive = to_primitive(response)

        self.assertNotIn("all_strategy_decisions", primitive)

    def test_scan_response_can_probe_execution(self):
        fake_execution = FakeExecutionClient()
        with patch(
            "forex_bot.__main__.load_config_from_env",
            return_value=_live_ready_config(),
        ), patch("forex_bot.__main__.create_broker_client", return_value=FakeBrokerClient()), patch(
            "forex_bot.__main__.create_execution_client",
            return_value=fake_execution,
        ):
            response = scan_pair_response("EUR_USD", source="broker", probe_execution=True)

        self.assertTrue(response.execution.can_place_orders)
        self.assertTrue(response.execution.reconciliation_ok)
        self.assertEqual(fake_execution.diagnose_calls, [(True, ("EUR_USD",))])

    def test_scan_market_bias_gate_rejects_conflicting_candidate(self):
        candidate = TradeCandidate(
            symbol="EUR_USD",
            direction=Direction.BUY,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0900"),
            take_profit=Decimal("1.1200"),
            spread_pips=Decimal("0.8"),
            setup_name="trendline_zone_sequence",
            strategy_decision_id="buy-candidate",
        )
        decision = StrategyDecision(
            id="buy-candidate",
            symbol="EUR_USD",
            state=SignalState.TRADE_CANDIDATE,
            setup_name="trendline_zone_sequence",
            created_at=__import__("datetime").datetime.fromisoformat("2026-06-04T21:00:00+00:00"),
            evidence=(),
            candidate=candidate,
        )
        with patch(
            "forex_bot.__main__.load_config_from_env",
            return_value=BotConfig(
                broker=BrokerConfig(provider=BrokerProvider.OANDA, environment=BrokerEnvironment.PRACTICE),
                execution=ExecutionConfig(provider=ExecutionProvider.MT5),
            ),
        ), patch("forex_bot.__main__.create_broker_client", return_value=BearishContextBrokerClient()), patch(
            "forex_bot.__main__._evaluate_all_strategies",
            return_value=(decision,),
        ):
            response = scan_pair_response("EUR_USD", source="broker", higher_timeframe=Timeframe.H4)

        self.assertEqual(response.market_bias.trade_classification, "Long-Term Sell")
        self.assertTrue(response.market_bias.candidate_conflict)
        self.assertEqual(response.decision.state, SignalState.NO_TRADE)
        self.assertIsNone(response.decision.candidate)
        self.assertEqual(response.decision.evidence[-1].rule, "top_down_market_bias")

    def test_paper_preview_rejects_no_trade_candidate(self):
        candles = [
            Candle(
                symbol="EUR_USD",
                timeframe=Timeframe.H1,
                timestamp=__import__("datetime").datetime.fromisoformat("2026-06-04T21:00:00+00:00"),
                open=Decimal("1.1600"),
                high=Decimal("1.1620"),
                low=Decimal("1.1590"),
                close=Decimal("1.1610"),
            )
        ] * 3
        snapshot = MarketSnapshot(
            candles=candles,
            instrument=_eur_usd(),
            spread_pips=Decimal("0.8"),
            provider="oanda",
        )

        class FakeBrokerClient:
            def get_market_snapshot(self, symbol, granularity=Timeframe.H1, count=200):
                return snapshot

        with patch(
            "forex_bot.__main__.load_config_from_env",
            return_value=BotConfig(broker=BrokerConfig(provider=BrokerProvider.OANDA, environment=BrokerEnvironment.PRACTICE)),
        ), patch("forex_bot.__main__.create_broker_client", return_value=FakeBrokerClient()):
            response = scan_pair_response("EUR_USD", source="broker", paper_preview=True)

        self.assertEqual(response.paper_preview.state, "NO_PAPER_TRADE")
        self.assertEqual(response.paper_preview.reason, "no_trade_candidate")

    def test_scan_blocks_candidate_during_news_blackout(self):
        class FakeBrokerClient:
            def get_market_snapshot(self, symbol, granularity=Timeframe.H1, count=200):
                candles = load_fixture_candles("eur_usd_fresh_strong_zone.json")
                if granularity != Timeframe.H1:
                    candles = [
                        Candle(symbol=symbol, timeframe=granularity, timestamp=__import__("datetime").datetime.fromisoformat("2026-06-01T00:00:00+00:00"), open=Decimal("1.0000"), high=Decimal("1.0200"), low=Decimal("0.9900"), close=Decimal("1.0100")),
                        Candle(symbol=symbol, timeframe=granularity, timestamp=__import__("datetime").datetime.fromisoformat("2026-06-02T00:00:00+00:00"), open=Decimal("1.0100"), high=Decimal("1.0300"), low=Decimal("1.0000"), close=Decimal("1.0200")),
                    ]
                return MarketSnapshot(
                    candles=candles,
                    instrument=_eur_usd(),
                    spread_pips=Decimal("0.8"),
                    provider="oanda",
                )

        with TemporaryDirectory() as temp_dir:
            calendar = Path(temp_dir) / "calendar.json"
            calendar.write_text(
                json.dumps(
                    [
                        {
                            "title": "US Nonfarm Payrolls",
                            "currency": "USD",
                            "impact": "high",
                            "starts_at": "2026-05-25T15:00:00Z",
                        }
                    ]
                )
            )
            with patch(
                "forex_bot.__main__.load_config_from_env",
                return_value=BotConfig(
                    broker=BrokerConfig(provider=BrokerProvider.OANDA, environment=BrokerEnvironment.PRACTICE),
                    news=NewsConfig(blackout_events_file=str(calendar)),
                ),
            ), patch("forex_bot.__main__.create_broker_client", return_value=FakeBrokerClient()):
                response = scan_pair_response("EUR_USD", source="broker")

        self.assertEqual(response.decision.state, SignalState.NO_TRADE)
        self.assertIsNone(response.decision.candidate)
        self.assertTrue(response.news_blackout.blocked)
        blackout = [item for item in response.decision.evidence if item.rule == "news_blackout"][0]
        self.assertFalse(blackout.passed)

    def test_scan_log_persists_jsonl_rows(self):
        response = scan_pair_response("EUR_USD", source="fixture", paper_preview=True)

        with TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "scan-log.jsonl"
            persist_scan_result(response, str(log_path))

            rows = log_path.read_text().splitlines()

        self.assertEqual(len(rows), 1)
        self.assertIn('"market_data"', rows[0])
        self.assertIn('"paper_preview"', rows[0])

    def test_execute_live_response_can_be_ready_without_submitting(self):
        fake_execution = FakeExecutionClient()
        with patch(
            "forex_bot.__main__.load_config_from_env",
            return_value=_live_ready_config(),
        ), patch("forex_bot.__main__.create_broker_client", return_value=FakeBrokerClient()), patch(
            "forex_bot.__main__.create_execution_client",
            return_value=fake_execution,
        ):
            response = execute_live_response("EUR_USD", submit_live_order=False)

        self.assertTrue(response.policy.allowed)
        self.assertFalse(response.submitted)
        self.assertEqual(response.reason, "ready_but_not_submitted_without_submit_live_order")
        self.assertTrue(response.idempotency_key)
        self.assertEqual(response.scan.execution, response.execution)
        self.assertTrue(response.scan.execution.reconciliation_ok)
        self.assertEqual(fake_execution.submitted_requests, [])

    def test_execute_live_response_submits_when_requested_and_all_gates_pass(self):
        fake_execution = FakeExecutionClient()
        with patch(
            "forex_bot.__main__.load_config_from_env",
            return_value=_live_ready_config(),
        ), patch("forex_bot.__main__.create_broker_client", return_value=FakeBrokerClient()), patch(
            "forex_bot.__main__.create_execution_client",
            return_value=fake_execution,
        ):
            response = execute_live_response("EUR_USD", submit_live_order=True)

        self.assertTrue(response.policy.allowed)
        self.assertTrue(response.submitted)
        self.assertEqual(response.submission.state, "ACCEPTED")
        self.assertEqual(len(fake_execution.submitted_requests), 1)

    def test_autotrade_cycle_can_be_ready_without_submitting(self):
        fake_execution = FakeExecutionClient()
        with patch(
            "forex_bot.__main__.load_config_from_env",
            return_value=_live_ready_config(),
        ), patch("forex_bot.__main__.create_broker_client", return_value=FakeBrokerClient()), patch(
            "forex_bot.__main__.create_execution_client",
            return_value=fake_execution,
        ):
            response = autotrade_cycle_response(("EUR_USD",), submit_live_orders=False)

        self.assertEqual(response.scanned_count, 1)
        self.assertEqual(response.candidate_count, 1)
        self.assertEqual(response.allowed_count, 1)
        self.assertEqual(response.submitted_count, 0)
        self.assertEqual(response.results[0].reason, "ready_but_not_submitted_without_submit_live_orders")
        self.assertEqual(fake_execution.submitted_requests, [])

    def test_autotrade_cycle_submits_when_requested_and_all_gates_pass(self):
        fake_execution = FakeExecutionClient()
        with patch(
            "forex_bot.__main__.load_config_from_env",
            return_value=_live_ready_config(),
        ), patch("forex_bot.__main__.create_broker_client", return_value=FakeBrokerClient()), patch(
            "forex_bot.__main__.create_execution_client",
            return_value=fake_execution,
        ):
            response = autotrade_cycle_response(("EUR_USD",), submit_live_orders=True)

        self.assertEqual(response.scanned_count, 1)
        self.assertEqual(response.candidate_count, 1)
        self.assertEqual(response.allowed_count, 1)
        self.assertEqual(response.submitted_count, 1)
        self.assertTrue(response.results[0].submitted)
        self.assertEqual(response.results[0].submission.state, "ACCEPTED")
        self.assertEqual(len(fake_execution.submitted_requests), 1)

    def test_autotrade_cycle_blocks_when_execution_preflight_rejects_size(self):
        fake_execution = FakeExecutionClient(
            preflight=OrderPreflightResult(
                allowed=False,
                reason="Calculated MT5 volume 0.00 is below symbol minimum 0.01.",
                symbol="EURUSD",
                requested_units=Decimal("38"),
                volume_min=Decimal("0.01"),
            )
        )
        with patch(
            "forex_bot.__main__.load_config_from_env",
            return_value=_live_ready_config(),
        ), patch("forex_bot.__main__.create_broker_client", return_value=FakeBrokerClient()), patch(
            "forex_bot.__main__.create_execution_client",
            return_value=fake_execution,
        ):
            response = autotrade_cycle_response(("EUR_USD",), submit_live_orders=True)

        self.assertEqual(response.candidate_count, 1)
        self.assertEqual(response.allowed_count, 0)
        self.assertEqual(response.submitted_count, 0)
        self.assertFalse(response.results[0].policy.allowed)
        self.assertEqual(response.results[0].risk_approval.decision, RiskDecision.REJECTED)
        self.assertIn("execution_preflight_failed", response.results[0].risk_approval.reasons[0])
        self.assertEqual(fake_execution.submitted_requests, [])

    def test_autotrade_cycle_notifies_when_setup_candidate_appears(self):
        fake_execution = FakeExecutionClient()
        fake_notifier = FakeNotifier()
        with patch(
            "forex_bot.__main__.load_config_from_env",
            return_value=_live_ready_config(),
        ), patch("forex_bot.__main__.create_broker_client", return_value=FakeBrokerClient()), patch(
            "forex_bot.__main__.create_execution_client",
            return_value=fake_execution,
        ):
            response = autotrade_cycle_response(("EUR_USD",), notify_setups=True, notifier=fake_notifier)

        self.assertEqual(len(fake_notifier.calls), 1)
        self.assertEqual(fake_notifier.calls[0][0].symbol, "EUR_USD")
        self.assertEqual(response.results[0].notification_results[0].state, "SENT")


class FakeBrokerClient:
    def get_market_snapshot(self, symbol, granularity=Timeframe.H1, count=200):
        candles = load_fixture_candles("eur_usd_fresh_strong_zone.json")
        if granularity != Timeframe.H1:
            candles = [
                Candle(symbol=symbol, timeframe=granularity, timestamp=__import__("datetime").datetime.fromisoformat("2026-06-01T00:00:00+00:00"), open=Decimal("1.0000"), high=Decimal("1.0200"), low=Decimal("0.9900"), close=Decimal("1.0100")),
                Candle(symbol=symbol, timeframe=granularity, timestamp=__import__("datetime").datetime.fromisoformat("2026-06-02T00:00:00+00:00"), open=Decimal("1.0100"), high=Decimal("1.0300"), low=Decimal("1.0000"), close=Decimal("1.0200")),
            ]
        return MarketSnapshot(
            candles=candles,
            instrument=_eur_usd(),
            spread_pips=Decimal("0.8"),
            provider="oanda",
        )


class BearishContextBrokerClient:
    def get_market_snapshot(self, symbol, granularity=Timeframe.H1, count=200):
        closes = ("1.2000", "1.1800", "1.1600", "1.1400")
        if granularity == Timeframe.H1:
            closes = ("1.1500", "1.1400", "1.1300", "1.1200")
        return MarketSnapshot(
            candles=_series(symbol, granularity, closes),
            instrument=_eur_usd(),
            spread_pips=Decimal("0.8"),
            provider="oanda",
        )


class FakeExecutionClient:
    provider_name = "mt5"

    def __init__(self, preflight=None):
        self.diagnose_calls = []
        self.submitted_requests = []
        self.preflight = preflight or OrderPreflightResult(allowed=True, reason="ok")

    def diagnose(self, probe_terminal=False, symbols=()):
        self.diagnose_calls.append((probe_terminal, symbols))
        return ExecutionDiagnostics(
            provider="mt5",
            environment="live",
            configured=True,
            can_place_orders=True,
            reason="ready",
            read_only_probe_ok=True,
            reconciliation_ok=True,
            duplicate_order_check_ok=True,
        )

    def submit_order(self, request, ledger=None):
        self.submitted_requests.append(request)
        return OrderSubmissionResult(
            state="ACCEPTED",
            idempotency_key=request.idempotency_key,
            broker_order_id="order-1",
            broker_deal_id="deal-1",
            message="accepted",
        )

    def preflight_order(self, request):
        return self.preflight


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send_setup_alert(self, decision, risk_approval, policy):
        self.calls.append((decision, risk_approval, policy))
        return (NotificationResult("SENT", "fake", "sent"),)


def _live_ready_config() -> BotConfig:
    return BotConfig(
        mode=BotMode.AUTONOMOUS_LIVE,
        broker=BrokerConfig(provider=BrokerProvider.OANDA, environment=BrokerEnvironment.LIVE),
        execution=ExecutionConfig(
            provider=ExecutionProvider.MT5,
            environment=BrokerEnvironment.LIVE,
            mt5_login="12345",
            mt5_password="secret",
            mt5_server="Deriv-Live",
            order_placement_enabled=True,
        ),
        explicit_live_enabled=True,
    )

def _eur_usd() -> InstrumentSpec:
    return InstrumentSpec(
        symbol="EUR_USD",
        pip_size=Decimal("0.0001"),
        pip_value_per_unit=Decimal("0.0001"),
        min_units=Decimal("1"),
        max_units=Decimal("100000"),
        unit_step=Decimal("1"),
        margin_rate=Decimal("0.0333"),
        max_spread_pips=Decimal("2"),
    )


def _series(symbol: str, timeframe: Timeframe, closes: tuple[str, ...]) -> list[Candle]:
    start = __import__("datetime").datetime.fromisoformat("2026-06-01T00:00:00+00:00")
    candles = []
    previous = Decimal(closes[0])
    for index, close_text in enumerate(closes):
        close = Decimal(close_text)
        open_price = previous
        candles.append(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=start + __import__("datetime").timedelta(hours=index),
                open=open_price,
                high=max(open_price, close) + Decimal("0.0010"),
                low=min(open_price, close) - Decimal("0.0010"),
                close=close,
            )
        )
        previous = close
    return candles


if __name__ == "__main__":
    unittest.main()
