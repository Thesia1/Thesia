from dataclasses import dataclass
from decimal import Decimal

from forex_bot.models import (
    AccountState,
    InstrumentSpec,
    RiskApproval,
    RiskDecision,
    RiskLimits,
    StrategyDecision,
)
from forex_bot.risk_gate import evaluate_risk


@dataclass(frozen=True)
class PaperTradePreview:
    state: str
    reason: str
    risk_approval: RiskApproval | None
    simulated_entry_price: Decimal | None = None
    simulated_stop_loss: Decimal | None = None
    simulated_take_profit: Decimal | None = None
    simulated_units: Decimal = Decimal("0")


def preview_paper_trade(
    decision: StrategyDecision,
    account: AccountState,
    instrument: InstrumentSpec,
    limits: RiskLimits,
) -> PaperTradePreview:
    if decision.candidate is None:
        return PaperTradePreview(
            state="NO_PAPER_TRADE",
            reason="no_trade_candidate",
            risk_approval=None,
        )

    approval = evaluate_risk(
        account=account,
        instrument=instrument,
        candidate=decision.candidate,
        limits=limits,
    )
    if approval.decision != RiskDecision.APPROVED:
        return PaperTradePreview(
            state="PAPER_REJECTED",
            reason="risk_rejected",
            risk_approval=approval,
        )

    return PaperTradePreview(
        state="PAPER_READY",
        reason="risk_approved_no_broker_order_created",
        risk_approval=approval,
        simulated_entry_price=decision.candidate.entry_price,
        simulated_stop_loss=decision.candidate.stop_loss,
        simulated_take_profit=decision.candidate.take_profit,
        simulated_units=approval.units,
    )
