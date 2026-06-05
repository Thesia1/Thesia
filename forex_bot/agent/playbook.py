from dataclasses import dataclass

from forex_bot.agent.base import AgentMessage
from forex_bot.models import RuleEvidence, StrategyDecision
from forex_bot.playbook.coverage import current_playbook_coverage


PLAYBOOK_SYSTEM_PROMPT = """You are the Thesia trading agent.

Operational playbook:
- OANDA is the market-data provider for candles, pricing, spread, and scan evidence.
- Deriv MT5 is the execution venue; order submission is allowed only through the guarded MT5 submitter and idempotency ledger.
- The agent cannot create raw orders, override risk limits, increase position size, or trade when broker state is uncertain.
- Deriv MT5 broker state must reconcile account info, open positions, open orders, margin, symbol metadata, and ticks before live execution can be considered.
- The idempotency ledger must block duplicate submissions for the same strategy decision.
- A trade can only be discussed as executable when deterministic strategy state is TRADE_CANDIDATE and the risk gate approves it.
- The current executable strategy is fresh_strong_zone_continuation.
- BUY logic: base candle, bullish departure, departure close above an active opposing supply zone, return to demand zone, bullish close above demand zone.
- SELL logic: base candle, bearish departure, departure close below an active opposing demand zone, return to supply zone, bearish close below supply zone.
- Fresh-zone logic: reject zones invalidated or already retested before the current return.
- Curve logic: buys require the 0-25% low-curve area; sells require the 0-25% high-curve area when higher-timeframe context is supplied.
- Target logic: use nearest opposing zone when it preserves minimum reward; otherwise use the minimum fixed reward target.
- Optional higher-timeframe confirmation can reject otherwise valid setups.
- If any required rule fails, the correct answer is no trade.
- Agent output is explanation and review only; deterministic code owns signals, risk, sizing, and execution.

Documented visual concepts from strategy_docs sessions:
- Zone anatomy: supply and demand zones have proximal entry lines and distal stop lines.
- Base quality: documented bases can use 1-6 candles; 50% candles, hammers, doji, and marubozu patterns are discussed, but doji bases are dangerous.
- Fresh and original zones can be limit-order candidates; retested zones require extra confirmation and become dangerous after repeated touches.
- Stairs zones are poor-quality zones and should not be treated like clean fresh/original zones.
- CP levels are lower-timeframe continuation levels; use at most 3 CP levels because a fourth CP level is documented as weak.
- PCP levels form after an opposing zone is removed.
- Gaps are clues; the documented trade location is the zone before the gap.
- Monthly, weekly, and daily are the main supply/demand decision timeframes; lower timeframes are for entries and confirmation.
- Confirmation rules from the session docs: monthly zones need lower-timeframe confirmation around the third touch; weekly/daily zones need confirmation around the second touch; daily is marked risky.
- Inheritance and flip zones are documented context zones; flip zones act like retracement/support-resistance areas where CP entries may form.
- Trendline rules: draw trendlines from the last two swing highs or lows; trend change needs trendline break plus opposing zone removal.
- High/low curve rules: market moves between monthly supply and demand; 0-25% near monthly supply is seller area, 0-25% near monthly demand is buyer area, and the middle 50% is not a clean edge.
- These visual concepts are playbook context only until deterministic detectors and tests exist.
"""


@dataclass(frozen=True)
class PlaybookAlignmentReport:
    grounded: bool
    missing_topics: tuple[str, ...]
    prompt_preview: str


def build_playbook_messages(decision: StrategyDecision | None = None) -> list[AgentMessage]:
    messages = [AgentMessage(role="system", content=f"{PLAYBOOK_SYSTEM_PROMPT}\n{_coverage_summary()}")]
    if decision is not None:
        messages.append(
            AgentMessage(
                role="user",
                content=_decision_summary(decision),
            )
        )
    return messages


def assess_playbook_grounding(messages: list[AgentMessage]) -> PlaybookAlignmentReport:
    content = "\n".join(message.content for message in messages).lower()
    required = {
        "oanda_market_data": ("oanda", "market-data"),
        "deriv_mt5_execution": ("deriv mt5", "execution"),
        "no_raw_orders": ("cannot create raw orders",),
        "risk_gate": ("risk gate",),
        "fresh_strong_zone": ("fresh_strong_zone_continuation",),
        "buy_rules": ("bullish departure", "opposing supply zone", "demand zone"),
        "sell_rules": ("bearish departure", "opposing demand zone", "supply zone"),
        "no_trade_on_failed_rules": ("no trade",),
        "visual_docs": ("stairs zones", "cp levels", "trendline", "seller area", "buyer area"),
    }
    missing = tuple(
        topic
        for topic, needles in required.items()
        if not all(needle in content for needle in needles)
    )
    preview = messages[0].content[:3200] if messages else ""
    return PlaybookAlignmentReport(
        grounded=not missing,
        missing_topics=missing,
        prompt_preview=preview,
    )


def _coverage_summary() -> str:
    coverage = current_playbook_coverage()
    blockers = ", ".join(coverage.required_blockers) if coverage.required_blockers else "none"
    return (
        "Machine-readable playbook coverage:\n"
        f"- automation_ready: {str(coverage.automation_ready).lower()}\n"
        f"- implemented_concepts: {coverage.implemented_count}\n"
        f"- partial_concepts: {coverage.partial_count}\n"
        f"- missing_concepts: {coverage.missing_count}\n"
        f"- automation_blockers: {blockers}\n"
        "- If automation_ready is false, the agent must not describe the system as autonomous-trade-ready.\n"
    )


def _decision_summary(decision: StrategyDecision) -> str:
    evidence = "\n".join(_evidence_line(item) for item in decision.evidence)
    candidate = "none"
    if decision.candidate is not None:
        candidate = (
            f"{decision.candidate.direction.value} entry={decision.candidate.entry_price} "
            f"stop={decision.candidate.stop_loss} target={decision.candidate.take_profit}"
        )
    return (
        f"Review strategy decision {decision.id} for {decision.symbol}.\n"
        f"State: {decision.state.value}\n"
        f"Setup: {decision.setup_name}\n"
        f"Candidate: {candidate}\n"
        f"Evidence:\n{evidence}"
    )


def _evidence_line(evidence: RuleEvidence) -> str:
    status = "PASS" if evidence.passed else "FAIL"
    return f"- {status} {evidence.rule}: {evidence.detail}"
