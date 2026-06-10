from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from forex_bot.analysis.market_bias import analyze_timeframe_bias, build_market_bias_report
from forex_bot.models import Candle, Direction, SignalState, StrategyDecision, Timeframe, TradeCandidate


class MarketBiasTest(unittest.TestCase):
    def test_bullish_higher_timeframes_classify_long_term_buy(self):
        decision = _candidate_decision(Direction.BUY)

        report = build_market_bias_report(
            symbol="EUR_USD",
            monthly_candles=_candles(Timeframe.M, "1.10", "1.12", "1.15", "1.18"),
            weekly_candles=_candles(Timeframe.W, "1.11", "1.13", "1.16", "1.19"),
            daily_candles=_candles(Timeframe.D, "1.12", "1.14", "1.17", "1.20"),
            h4_candles=_candles(Timeframe.H4, "1.15", "1.16", "1.18", "1.21"),
            entry_candles=_candles(Timeframe.H1, "1.18", "1.19", "1.20", "1.22"),
            strategy_decision=decision,
        )

        self.assertEqual(report.trade_classification, "Long-Term Buy")
        self.assertEqual(report.final_decision, "Buy")
        self.assertEqual(report.entry_type, "Market Entry")
        self.assertFalse(report.candidate_conflict)
        self.assertGreaterEqual(report.confidence_score, 90)

    def test_bearish_higher_timeframes_reject_buy_candidate(self):
        decision = _candidate_decision(Direction.BUY)

        report = build_market_bias_report(
            symbol="EUR_USD",
            monthly_candles=_candles(Timeframe.M, "1.22", "1.18", "1.15", "1.10"),
            weekly_candles=_candles(Timeframe.W, "1.21", "1.17", "1.14", "1.09"),
            daily_candles=_candles(Timeframe.D, "1.20", "1.16", "1.13", "1.08"),
            h4_candles=_candles(Timeframe.H4, "1.18", "1.15", "1.12", "1.07"),
            entry_candles=_candles(Timeframe.H1, "1.12", "1.10", "1.09", "1.06"),
            strategy_decision=decision,
        )

        self.assertEqual(report.trade_classification, "Long-Term Sell")
        self.assertEqual(report.final_decision, "Reject setup")
        self.assertTrue(report.candidate_conflict)
        self.assertIn("conflicts", report.reason)

    def test_mixed_monthly_weekly_daily_requires_wait(self):
        decision = _no_trade_decision()

        report = build_market_bias_report(
            symbol="GBP_USD",
            monthly_candles=_candles(Timeframe.M, "1.20", "1.22", "1.24", "1.26"),
            weekly_candles=_candles(Timeframe.W, "1.26", "1.23", "1.21", "1.18"),
            daily_candles=_candles(Timeframe.D, "1.18", "1.19", "1.21", "1.23"),
            h4_candles=_candles(Timeframe.H4, "1.20", "1.21", "1.22", "1.24"),
            entry_candles=_candles(Timeframe.H1, "1.21", "1.22", "1.23", "1.24"),
            strategy_decision=decision,
        )

        self.assertEqual(report.trade_classification, "No Trade / Wait")
        self.assertEqual(report.final_decision, "Wait")
        self.assertEqual(report.setup_quality, "Weak")

    def test_insufficient_candles_are_not_actionable(self):
        report = analyze_timeframe_bias(_candles(Timeframe.D, "1.10", "1.11"), Timeframe.D)

        self.assertEqual(report.bias, "INSUFFICIENT")
        self.assertEqual(report.confidence_score, 0)


def _candidate_decision(direction: Direction) -> StrategyDecision:
    candidate = TradeCandidate(
        symbol="EUR_USD",
        direction=direction,
        entry_price=Decimal("1.2000"),
        stop_loss=Decimal("1.1900") if direction == Direction.BUY else Decimal("1.2100"),
        take_profit=Decimal("1.2200") if direction == Direction.BUY else Decimal("1.1800"),
        spread_pips=Decimal("0.8"),
        setup_name="trendline_zone_sequence",
        strategy_decision_id="decision-1",
    )
    return StrategyDecision(
        id="decision-1",
        symbol="EUR_USD",
        state=SignalState.TRADE_CANDIDATE,
        setup_name="trendline_zone_sequence",
        created_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
        evidence=(),
        candidate=candidate,
    )


def _no_trade_decision() -> StrategyDecision:
    return StrategyDecision(
        id="decision-2",
        symbol="GBP_USD",
        state=SignalState.NO_TRADE,
        setup_name="fresh_strong_zone_continuation",
        created_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
        evidence=(),
        candidate=None,
    )


def _candles(timeframe: Timeframe, *closes: str) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    delta = timedelta(hours=1)
    if timeframe == Timeframe.H4:
        delta = timedelta(hours=4)
    elif timeframe == Timeframe.D:
        delta = timedelta(days=1)
    elif timeframe == Timeframe.W:
        delta = timedelta(weeks=1)
    elif timeframe == Timeframe.M:
        delta = timedelta(days=30)
    candles: list[Candle] = []
    previous = Decimal(closes[0])
    for index, close_text in enumerate(closes):
        close = Decimal(close_text)
        open_price = previous
        high = max(open_price, close) + Decimal("0.0020")
        low = min(open_price, close) - Decimal("0.0020")
        candles.append(
            Candle(
                symbol="EUR_USD",
                timeframe=timeframe,
                timestamp=start + (delta * index),
                open=open_price,
                high=high,
                low=low,
                close=close,
            )
        )
        previous = close
    return candles


if __name__ == "__main__":
    unittest.main()
