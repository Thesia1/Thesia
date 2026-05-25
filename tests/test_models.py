from datetime import datetime, timezone
from decimal import Decimal
import unittest

from forex_bot.models import Candle, Direction, OrderIntent, Timeframe, TradeCandidate


class ModelsTest(unittest.TestCase):
    def test_candle_rejects_invalid_high_low(self):
        with self.assertRaises(ValueError):
            Candle(
                symbol="EUR_USD",
                timeframe=Timeframe.H1,
                timestamp=datetime.now(timezone.utc),
                open=Decimal("1.10"),
                high=Decimal("1.09"),
                low=Decimal("1.08"),
                close=Decimal("1.10"),
            )

    def test_trade_candidate_requires_decision_id(self):
        with self.assertRaises(ValueError):
            TradeCandidate(
                symbol="EUR_USD",
                direction=Direction.BUY,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
                spread_pips=Decimal("0.8"),
                setup_name="test",
                strategy_decision_id="",
            )

    def test_order_intent_requires_risk_approval_id(self):
        candidate = TradeCandidate(
            symbol="EUR_USD",
            direction=Direction.BUY,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
            spread_pips=Decimal("0.8"),
            setup_name="test",
            strategy_decision_id="decision-1",
        )
        with self.assertRaises(ValueError):
            OrderIntent(
                id="intent-1",
                strategy_decision_id="decision-1",
                risk_approval_id="",
                candidate=candidate,
                units=Decimal("1000"),
            )


if __name__ == "__main__":
    unittest.main()

