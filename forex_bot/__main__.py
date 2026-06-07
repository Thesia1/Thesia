import argparse
import json
from dataclasses import asdict, dataclass, is_dataclass
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from sys import stderr, exit

from forex_bot.agent.playbook import assess_playbook_grounding, build_playbook_messages
from forex_bot.agent.policy import AgentAutonomyDecision, evaluate_agent_autonomy
from forex_bot.brokers.base import BrokerConfigError
from forex_bot.brokers.factory import create_broker_client
from forex_bot.brokers.oanda import OandaClient
from forex_bot.brokers.oanda import instrument_spec_for, to_oanda_instrument
from forex_bot.config import BotConfig, load_config_from_env
from forex_bot.execution.base import ExecutionDiagnostics, ExecutionProviderError, OrderSubmissionRequest, OrderSubmissionResult
from forex_bot.execution.factory import create_execution_client
from forex_bot.execution.ledger import FileOrderLedger
from forex_bot.fixtures import load_fixture_candles
from forex_bot.models import AccountState, BotMode, BrokerEnvironment, BrokerProvider, Candle, InstrumentSpec, RiskApproval, RiskLimits, RuleEvidence, SignalState, StrategyDecision, Timeframe
from forex_bot.news.blackout import NewsBlackoutDecision, blackout_from_config
from forex_bot.paper import PaperTradePreview, preview_paper_trade
from forex_bot.playbook.coverage import current_playbook_coverage
from forex_bot.strategy import StrategyContext
from forex_bot.strategy.fresh_strong_zone import FreshStrongZoneContinuation
from forex_bot.strategy.trendline_zone_sequence import TrendlineZoneSequence


@dataclass(frozen=True)
class CandleSummary:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class MarketDataProvenance:
    source: str
    provider: str
    broker_environment: str
    symbol: str
    granularity: Timeframe
    requested_count: int
    complete_candle_count: int
    spread_pips: Decimal
    first_complete_candle: CandleSummary | None
    latest_complete_candle: CandleSummary | None
    warning: str = ""


@dataclass(frozen=True)
class ScanResponse:
    decision: StrategyDecision
    market_data: MarketDataProvenance
    execution: ExecutionDiagnostics | None = None
    paper_preview: PaperTradePreview | None = None
    news_blackout: NewsBlackoutDecision | None = None
    all_strategy_decisions: tuple[StrategyDecision, ...] | None = None


@dataclass(frozen=True)
class BatchScanResponse:
    scans: tuple[ScanResponse, ...]
    scanned_count: int
    candidate_count: int
    tradeable_paper_count: int


@dataclass(frozen=True)
class LiveExecutionResponse:
    scan: ScanResponse
    risk_approval: RiskApproval | None
    execution: ExecutionDiagnostics
    policy: AgentAutonomyDecision
    idempotency_key: str = ""
    submitted: bool = False
    submission: OrderSubmissionResult | None = None
    reason: str = ""


@dataclass(frozen=True)
class AutoTradePairResult:
    scan: ScanResponse
    risk_approval: RiskApproval | None
    execution: ExecutionDiagnostics
    policy: AgentAutonomyDecision
    idempotency_key: str = ""
    submitted: bool = False
    submission: OrderSubmissionResult | None = None
    reason: str = ""


@dataclass(frozen=True)
class AutoTradeCycleResponse:
    results: tuple[AutoTradePairResult, ...]
    scanned_count: int
    candidate_count: int
    allowed_count: int
    submitted_count: int
    max_orders: int
    submit_live_orders: bool
    reason: str


def main() -> None:
    parser = argparse.ArgumentParser(prog="forex_bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan")
    scan.add_argument("--pair", default="EUR_USD")
    scan.add_argument("--pairs", default="")
    scan.add_argument("--source", choices=["broker", "fixture"], default="broker")
    scan.add_argument("--broker-provider", choices=[provider.value for provider in BrokerProvider], default=None)
    scan.add_argument("--market-data-provider", choices=[provider.value for provider in BrokerProvider], default=None)
    scan.add_argument("--granularity", choices=[timeframe.value for timeframe in Timeframe], default=Timeframe.H1.value)
    scan.add_argument("--higher-timeframe", choices=[timeframe.value for timeframe in Timeframe], default=None)
    scan.add_argument("--count", type=int, default=200)
    scan.add_argument("--higher-timeframe-count", type=int, default=80)
    scan.add_argument("--paper-preview", action="store_true")
    scan.add_argument("--paper-equity", default="10000")
    scan.add_argument("--paper-margin-available", default="10000")
    scan.add_argument("--probe-execution", action="store_true")
    scan.add_argument("--show-all-strategies", action="store_true")
    scan.add_argument("--log-path", default="")

    execute = subparsers.add_parser("execute")
    execute.add_argument("--pair", default="EUR_USD")
    execute.add_argument("--granularity", choices=[timeframe.value for timeframe in Timeframe], default=Timeframe.H1.value)
    execute.add_argument("--count", type=int, default=200)
    execute.add_argument("--paper-equity", default="10000")
    execute.add_argument("--paper-margin-available", default="10000")
    execute.add_argument("--submit-live-order", action="store_true")

    autotrade = subparsers.add_parser("autotrade")
    autotrade.add_argument("--pairs", required=True)
    autotrade.add_argument("--granularity", choices=[timeframe.value for timeframe in Timeframe], default=Timeframe.H1.value)
    autotrade.add_argument("--higher-timeframe", choices=[timeframe.value for timeframe in Timeframe], default=None)
    autotrade.add_argument("--count", type=int, default=200)
    autotrade.add_argument("--higher-timeframe-count", type=int, default=80)
    autotrade.add_argument("--paper-equity", default="10000")
    autotrade.add_argument("--paper-margin-available", default="10000")
    autotrade.add_argument("--max-orders", type=int, default=1)
    autotrade.add_argument("--submit-live-orders", action="store_true")
    autotrade.add_argument("--show-all-strategies", action="store_true")

    doctor = subparsers.add_parser("doctor")
    doctor_subparsers = doctor.add_subparsers(dest="doctor_target", required=True)
    oanda = doctor_subparsers.add_parser("oanda")
    oanda.add_argument("--pair", default="EUR_USD")
    oanda.add_argument("--granularity", choices=[timeframe.value for timeframe in Timeframe], default=Timeframe.H1.value)
    mt5 = doctor_subparsers.add_parser("mt5")
    mt5.add_argument("--environment", choices=[environment.value for environment in BrokerEnvironment], default=None)
    mt5.add_argument("--probe", action="store_true")
    mt5.add_argument("--symbols", default="")
    doctor_subparsers.add_parser("agent-playbook")
    doctor_subparsers.add_parser("automation-readiness")
    args = parser.parse_args()

    if args.command == "scan":
        try:
            pairs = _parse_pairs(args.pairs) or (args.pair,)
            response = scan_pairs_response(
                pairs=pairs,
                source=args.source,
                broker_provider=_scan_provider_override(args.market_data_provider, args.broker_provider),
                granularity=Timeframe(args.granularity),
                count=args.count,
                higher_timeframe=Timeframe(args.higher_timeframe) if args.higher_timeframe else None,
                higher_timeframe_count=args.higher_timeframe_count,
                paper_preview=args.paper_preview,
                paper_equity=Decimal(args.paper_equity),
                paper_margin_available=Decimal(args.paper_margin_available),
                probe_execution=args.probe_execution,
                show_all_strategies=args.show_all_strategies,
            )
            if args.log_path:
                persist_scan_result(response, args.log_path)
        except BrokerConfigError as error:
            print(json.dumps({"error": str(error), "source": args.source}, indent=2), file=stderr)
            exit(2)
        print(json.dumps(to_primitive(response), indent=2, sort_keys=True))
    elif args.command == "execute":
        try:
            response = execute_live_response(
                pair=args.pair,
                granularity=Timeframe(args.granularity),
                count=args.count,
                paper_equity=Decimal(args.paper_equity),
                paper_margin_available=Decimal(args.paper_margin_available),
                submit_live_order=args.submit_live_order,
            )
        except (BrokerConfigError, ExecutionProviderError, ValueError) as error:
            print(json.dumps({"error": str(error), "source": "execute"}, indent=2), file=stderr)
            exit(2)
        print(json.dumps(to_primitive(response), indent=2, sort_keys=True))
    elif args.command == "autotrade":
        try:
            response = autotrade_cycle_response(
                pairs=_parse_pairs(args.pairs),
                granularity=Timeframe(args.granularity),
                count=args.count,
                higher_timeframe=Timeframe(args.higher_timeframe) if args.higher_timeframe else None,
                higher_timeframe_count=args.higher_timeframe_count,
                paper_equity=Decimal(args.paper_equity),
                paper_margin_available=Decimal(args.paper_margin_available),
                max_orders=args.max_orders,
                submit_live_orders=args.submit_live_orders,
                show_all_strategies=args.show_all_strategies,
            )
        except (BrokerConfigError, ExecutionProviderError, ValueError) as error:
            print(json.dumps({"error": str(error), "source": "autotrade"}, indent=2), file=stderr)
            exit(2)
        print(json.dumps(to_primitive(response), indent=2, sort_keys=True))
    elif args.command == "doctor" and args.doctor_target == "oanda":
        diagnostics = diagnose_oanda(pair=args.pair, granularity=Timeframe(args.granularity))
        print(json.dumps(to_primitive(diagnostics), indent=2, sort_keys=True))
    elif args.command == "doctor" and args.doctor_target == "mt5":
        diagnostics = diagnose_mt5(
            environment=BrokerEnvironment(args.environment) if args.environment else None,
            probe_terminal=args.probe,
            symbols=_parse_pairs(args.symbols),
        )
        print(json.dumps(to_primitive(diagnostics), indent=2, sort_keys=True))
    elif args.command == "doctor" and args.doctor_target == "agent-playbook":
        report = assess_playbook_grounding(build_playbook_messages())
        print(json.dumps(to_primitive(report), indent=2, sort_keys=True))
    elif args.command == "doctor" and args.doctor_target == "automation-readiness":
        report = diagnose_automation_readiness()
        print(json.dumps(to_primitive(report), indent=2, sort_keys=True))


def scan_pair(
    pair: str,
    source: str = "broker",
    broker_provider: BrokerProvider | None = None,
    granularity: Timeframe = Timeframe.H1,
    count: int = 200,
):
    return scan_pair_response(
        pair=pair,
        source=source,
        broker_provider=broker_provider,
        granularity=granularity,
        count=count,
    ).decision


def scan_pairs_response(
    pairs: tuple[str, ...],
    source: str = "broker",
    broker_provider: BrokerProvider | None = None,
    granularity: Timeframe = Timeframe.H1,
    count: int = 200,
    higher_timeframe: Timeframe | None = None,
    higher_timeframe_count: int = 80,
    paper_preview: bool = False,
    paper_equity: Decimal = Decimal("10000"),
    paper_margin_available: Decimal = Decimal("10000"),
    probe_execution: bool = False,
    show_all_strategies: bool = False,
):
    scans = tuple(
        scan_pair_response(
            pair=pair,
            source=source,
            broker_provider=broker_provider,
            granularity=granularity,
            count=count,
            higher_timeframe=higher_timeframe,
            higher_timeframe_count=higher_timeframe_count,
            paper_preview=paper_preview,
            paper_equity=paper_equity,
            paper_margin_available=paper_margin_available,
            probe_execution=probe_execution,
            show_all_strategies=show_all_strategies,
        )
        for pair in pairs
    )
    if len(scans) == 1:
        return scans[0]
    return BatchScanResponse(
        scans=scans,
        scanned_count=len(scans),
        candidate_count=sum(1 for scan in scans if scan.decision.candidate is not None),
        tradeable_paper_count=sum(1 for scan in scans if scan.paper_preview is not None and scan.paper_preview.state == "PAPER_READY"),
    )


def scan_pair_response(
    pair: str,
    source: str = "broker",
    broker_provider: BrokerProvider | None = None,
    granularity: Timeframe = Timeframe.H1,
    count: int = 200,
    higher_timeframe: Timeframe | None = None,
    higher_timeframe_count: int = 80,
    paper_preview: bool = False,
    paper_equity: Decimal = Decimal("10000"),
    paper_margin_available: Decimal = Decimal("10000"),
    probe_execution: bool = False,
    show_all_strategies: bool = False,
) -> ScanResponse:
    normalized_pair = to_oanda_instrument(pair)
    provider = "local_fixture"
    broker_environment = ""
    higher_timeframe_candles: list[Candle] | None = None
    monthly_candles: list[Candle] | None = None
    weekly_candles: list[Candle] | None = None
    daily_candles: list[Candle] | None = None
    config: BotConfig | None = None
    if source == "fixture":
        candles = [candle for candle in load_fixture_candles("eur_usd_fresh_strong_zone.json") if candle.symbol == normalized_pair]
        candles = sorted(candles, key=lambda candle: candle.timestamp)[-count:]
        instrument = instrument_spec_for(normalized_pair)
        spread_pips = Decimal("0.8")
        broker_environment = "none"
    else:
        config = load_config_from_env()
        if broker_provider is not None:
            config = config.__class__(
                mode=config.mode,
                broker=config.broker.__class__(
                    provider=broker_provider,
                    environment=config.broker.environment,
                    account_id=config.broker.account_id,
                    token=config.broker.token,
                    username=config.broker.username,
                    password=config.broker.password,
                    app_key=config.broker.app_key,
                    practice_url=config.broker.practice_url,
                    live_url=config.broker.live_url,
                    forex_com_demo_url=config.broker.forex_com_demo_url,
                    forex_com_live_url=config.broker.forex_com_live_url,
                ),
                risk=config.risk,
                execution=config.execution,
                news=config.news,
                agent=config.agent,
                explicit_live_enabled=config.explicit_live_enabled,
            )
        broker_client = create_broker_client(config.broker, config.execution)
        snapshot = broker_client.get_market_snapshot(
            symbol=normalized_pair,
            granularity=granularity,
            count=count,
        )
        candles = snapshot.candles
        instrument = snapshot.instrument
        normalized_pair = instrument.symbol
        spread_pips = snapshot.spread_pips
        provider = snapshot.provider
        broker_environment = config.broker.environment.value
        if higher_timeframe is not None:
            higher_snapshot = broker_client.get_market_snapshot(
                symbol=normalized_pair,
                granularity=higher_timeframe,
                count=higher_timeframe_count,
            )
            higher_timeframe_candles = higher_snapshot.candles
        monthly_candles = broker_client.get_market_snapshot(
            symbol=normalized_pair,
            granularity=Timeframe.M,
            count=12,
        ).candles
        weekly_candles = broker_client.get_market_snapshot(
            symbol=normalized_pair,
            granularity=Timeframe.W,
            count=12,
        ).candles
        daily_candles = broker_client.get_market_snapshot(
            symbol=normalized_pair,
            granularity=Timeframe.D,
            count=20,
        ).candles

    strategy_context = StrategyContext(
        symbol=normalized_pair,
        candles=candles,
        instrument=instrument,
        spread_pips=spread_pips,
        higher_timeframe_candles=higher_timeframe_candles,
        monthly_candles=monthly_candles,
        weekly_candles=weekly_candles,
        daily_candles=daily_candles,
    )
    strategy_decisions = _evaluate_all_strategies(strategy_context)
    decision = _select_strategy_decision(strategy_decisions)
    news_blackout = blackout_from_config(normalized_pair, decision.created_at, config.news) if config is not None else None
    if news_blackout is not None:
        decision = _apply_news_blackout(decision, news_blackout)
        if show_all_strategies:
            strategy_decisions = tuple(_apply_news_blackout(item, news_blackout) for item in strategy_decisions)
    paper = None
    if paper_preview:
        paper = _paper_preview(
            decision=decision,
            instrument=instrument,
            config=config,
            paper_equity=paper_equity,
            paper_margin_available=paper_margin_available,
        )
    return ScanResponse(
        decision=decision,
        market_data=_market_data_provenance(
            source=source,
            provider=provider,
            broker_environment=broker_environment,
            symbol=normalized_pair,
            granularity=granularity,
            requested_count=count,
            candles=candles,
            spread_pips=spread_pips,
        ),
        execution=(
            create_execution_client(config.execution).diagnose(
                probe_terminal=probe_execution,
                symbols=(normalized_pair,) if probe_execution else (),
            )
            if config is not None
            else None
        ),
        paper_preview=paper,
        news_blackout=news_blackout,
        all_strategy_decisions=strategy_decisions if show_all_strategies else None,
    )


def execute_live_response(
    pair: str,
    granularity: Timeframe = Timeframe.H1,
    count: int = 200,
    paper_equity: Decimal = Decimal("10000"),
    paper_margin_available: Decimal = Decimal("10000"),
    submit_live_order: bool = False,
) -> LiveExecutionResponse:
    config = load_config_from_env()
    scan = scan_pair_response(
        pair=pair,
        source="broker",
        granularity=granularity,
        count=count,
        paper_preview=True,
        paper_equity=paper_equity,
        paper_margin_available=paper_margin_available,
    )
    risk_approval = scan.paper_preview.risk_approval if scan.paper_preview is not None else None
    execution_client = create_execution_client(config.execution)
    execution = execution_client.diagnose(probe_terminal=True, symbols=(scan.decision.symbol,))
    scan = replace(scan, execution=execution)
    policy = evaluate_agent_autonomy(
        mode=config.mode,
        strategy_decision=scan.decision,
        risk_approval=risk_approval,
        execution=execution,
    )
    idempotency_key = _idempotency_key(scan.decision, risk_approval)
    if not policy.allowed:
        return LiveExecutionResponse(
            scan=scan,
            risk_approval=risk_approval,
            execution=execution,
            policy=policy,
            idempotency_key=idempotency_key,
            reason="execution_policy_blocked",
        )
    if not submit_live_order:
        return LiveExecutionResponse(
            scan=scan,
            risk_approval=risk_approval,
            execution=execution,
            policy=policy,
            idempotency_key=idempotency_key,
            reason="ready_but_not_submitted_without_submit_live_order",
        )
    if scan.decision.candidate is None or risk_approval is None:
        raise ExecutionProviderError("Cannot submit without a strategy candidate and risk approval.")
    submission = execution_client.submit_order(
        _order_submission_request(scan.decision, risk_approval, idempotency_key),
        ledger=FileOrderLedger(config.execution.idempotency_ledger_path),
    )
    return LiveExecutionResponse(
        scan=scan,
        risk_approval=risk_approval,
        execution=execution,
        policy=policy,
        idempotency_key=idempotency_key,
        submitted=submission.state == "ACCEPTED",
        submission=submission,
        reason="submitted" if submission.state == "ACCEPTED" else submission.state.lower(),
    )


def autotrade_cycle_response(
    pairs: tuple[str, ...],
    granularity: Timeframe = Timeframe.H1,
    count: int = 200,
    higher_timeframe: Timeframe | None = None,
    higher_timeframe_count: int = 80,
    paper_equity: Decimal = Decimal("10000"),
    paper_margin_available: Decimal = Decimal("10000"),
    max_orders: int = 1,
    submit_live_orders: bool = False,
    show_all_strategies: bool = False,
) -> AutoTradeCycleResponse:
    if not pairs:
        raise ValueError("autotrade requires at least one pair.")
    if max_orders < 1:
        raise ValueError("max_orders must be at least 1.")

    config = load_config_from_env()
    execution_client = create_execution_client(config.execution)
    ledger = FileOrderLedger(config.execution.idempotency_ledger_path)
    results: list[AutoTradePairResult] = []
    submitted_count = 0

    for pair in pairs:
        scan = scan_pair_response(
            pair=pair,
            source="broker",
            granularity=granularity,
            count=count,
            higher_timeframe=higher_timeframe,
            higher_timeframe_count=higher_timeframe_count,
            paper_preview=True,
            paper_equity=paper_equity,
            paper_margin_available=paper_margin_available,
            show_all_strategies=show_all_strategies,
        )
        risk_approval = scan.paper_preview.risk_approval if scan.paper_preview is not None else None
        execution = execution_client.diagnose(probe_terminal=True, symbols=(scan.decision.symbol,))
        scan = replace(scan, execution=execution)
        policy = evaluate_agent_autonomy(
            mode=config.mode,
            strategy_decision=scan.decision,
            risk_approval=risk_approval,
            execution=execution,
        )
        idempotency_key = _idempotency_key(scan.decision, risk_approval)
        submission = None
        submitted = False
        reason = "execution_policy_blocked"

        if policy.allowed:
            if submitted_count >= max_orders:
                reason = "max_orders_reached"
            elif not submit_live_orders:
                reason = "ready_but_not_submitted_without_submit_live_orders"
            else:
                if scan.decision.candidate is None or risk_approval is None:
                    raise ExecutionProviderError("Cannot submit without a strategy candidate and risk approval.")
                submission = execution_client.submit_order(
                    _order_submission_request(scan.decision, risk_approval, idempotency_key),
                    ledger=ledger,
                )
                submitted = submission.state == "ACCEPTED"
                if submitted:
                    submitted_count += 1
                reason = "submitted" if submitted else submission.state.lower()

        results.append(
            AutoTradePairResult(
                scan=scan,
                risk_approval=risk_approval,
                execution=execution,
                policy=policy,
                idempotency_key=idempotency_key,
                submitted=submitted,
                submission=submission,
                reason=reason,
            )
        )

    return AutoTradeCycleResponse(
        results=tuple(results),
        scanned_count=len(results),
        candidate_count=sum(1 for result in results if result.scan.decision.candidate is not None),
        allowed_count=sum(1 for result in results if result.policy.allowed),
        submitted_count=submitted_count,
        max_orders=max_orders,
        submit_live_orders=submit_live_orders,
        reason="cycle_complete",
    )


def _evaluate_strategies(context: StrategyContext) -> StrategyDecision:
    return _select_strategy_decision(_evaluate_all_strategies(context))


def _evaluate_all_strategies(context: StrategyContext) -> tuple[StrategyDecision, ...]:
    return tuple(
        strategy.evaluate(context)
        for strategy in (
            FreshStrongZoneContinuation(),
            TrendlineZoneSequence(),
        )
    )


def _select_strategy_decision(decisions: tuple[StrategyDecision, ...]) -> StrategyDecision:
    for decision in decisions:
        if decision.state == SignalState.TRADE_CANDIDATE and decision.candidate is not None:
            return decision
    for decision in decisions:
        if decision.state == SignalState.WATCH:
            return decision
    return decisions[0]


def _order_submission_request(
    decision: StrategyDecision,
    risk_approval: RiskApproval,
    idempotency_key: str,
) -> OrderSubmissionRequest:
    if decision.candidate is None:
        raise ExecutionProviderError("Cannot build order submission without a trade candidate.")
    return OrderSubmissionRequest(
        symbol=decision.candidate.symbol,
        direction=decision.candidate.direction,
        units=risk_approval.units,
        entry_price=decision.candidate.entry_price,
        stop_loss=decision.candidate.stop_loss,
        take_profit=decision.candidate.take_profit,
        strategy_decision_id=decision.id,
        idempotency_key=idempotency_key,
    )


def _idempotency_key(decision: StrategyDecision, risk_approval: RiskApproval | None) -> str:
    if decision.candidate is None or risk_approval is None:
        return ""
    candidate = decision.candidate
    return ":".join(
        (
            decision.id,
            candidate.symbol,
            candidate.direction.value,
            str(candidate.entry_price),
            str(candidate.stop_loss),
            str(candidate.take_profit),
            str(risk_approval.units),
        )
    )


def _apply_news_blackout(decision: StrategyDecision, news_blackout: NewsBlackoutDecision) -> StrategyDecision:
    evidence = decision.evidence + (
        RuleEvidence(
            rule="news_blackout",
            passed=not news_blackout.blocked,
            detail=news_blackout.reason,
        ),
    )
    if not news_blackout.blocked:
        return replace(decision, evidence=evidence)
    return StrategyDecision(
        id=decision.id,
        symbol=decision.symbol,
        state=SignalState.NO_TRADE,
        setup_name=decision.setup_name,
        created_at=decision.created_at,
        evidence=evidence,
        candidate=None,
    )


def _paper_preview(
    decision: StrategyDecision,
    instrument: InstrumentSpec,
    config: BotConfig | None,
    paper_equity: Decimal,
    paper_margin_available: Decimal,
) -> PaperTradePreview:
    account = AccountState(
        equity=paper_equity,
        daily_realized_loss=Decimal("0"),
        weekly_realized_loss=Decimal("0"),
        open_trade_count=0,
        open_risk=Decimal("0"),
        margin_available=paper_margin_available,
    )
    limits = RiskLimits()
    if config is not None:
        limits = RiskLimits(
            risk_percent=config.risk.risk_percent,
            max_daily_loss_percent=config.risk.max_daily_loss_percent,
            max_weekly_loss_percent=config.risk.max_weekly_loss_percent,
        )
    return preview_paper_trade(decision, account, instrument, limits)


def persist_scan_result(response: ScanResponse | BatchScanResponse, log_path: str) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = response.scans if isinstance(response, BatchScanResponse) else (response,)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(to_primitive(row), sort_keys=True) + "\n")


def _parse_pairs(value: str) -> tuple[str, ...]:
    return tuple(pair.strip() for pair in value.split(",") if pair.strip())


def _scan_provider_override(market_data_provider: str | None, broker_provider: str | None) -> BrokerProvider | None:
    if market_data_provider:
        return BrokerProvider(market_data_provider)
    if broker_provider:
        return BrokerProvider(broker_provider)
    return None


def _market_data_provenance(
    source: str,
    provider: str,
    broker_environment: str,
    symbol: str,
    granularity: Timeframe,
    requested_count: int,
    candles: list[Candle],
    spread_pips: Decimal,
) -> MarketDataProvenance:
    ordered = sorted(candles, key=lambda candle: candle.timestamp)
    warning = ""
    if source == "fixture":
        warning = "Fixture data was requested explicitly; this is not live broker data."
    elif not ordered:
        warning = "Broker returned no complete candles for this request."

    return MarketDataProvenance(
        source=source,
        provider=provider,
        broker_environment=broker_environment,
        symbol=symbol,
        granularity=granularity,
        requested_count=requested_count,
        complete_candle_count=len(ordered),
        spread_pips=spread_pips,
        first_complete_candle=_candle_summary(ordered[0]) if ordered else None,
        latest_complete_candle=_candle_summary(ordered[-1]) if ordered else None,
        warning=warning,
    )


def _candle_summary(candle: Candle) -> CandleSummary:
    return CandleSummary(
        timestamp=candle.timestamp,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
    )


def diagnose_oanda(pair: str = "EUR_USD", granularity: Timeframe = Timeframe.H1):
    config = load_config_from_env()
    client = OandaClient(config.broker)
    return client.diagnose_read_access(symbol=to_oanda_instrument(pair), granularity=granularity)


def diagnose_mt5(
    environment: BrokerEnvironment | None = None,
    probe_terminal: bool = False,
    symbols: tuple[str, ...] = (),
):
    config = load_config_from_env()
    execution_config = config.execution
    if environment is not None:
        execution_config = replace(execution_config, environment=environment)
    return create_execution_client(execution_config).diagnose(probe_terminal=probe_terminal, symbols=symbols)


def diagnose_automation_readiness():
    config = load_config_from_env()
    playbook = current_playbook_coverage()
    execution = create_execution_client(config.execution).diagnose()
    placeholder_decision = StrategyDecision(
        id="automation-readiness",
        symbol="SYSTEM",
        state=SignalState.NO_TRADE,
        setup_name="system_readiness",
        created_at=datetime.now(timezone.utc),
        evidence=(),
        candidate=None,
    )
    policy = evaluate_agent_autonomy(
        mode=BotMode.AUTONOMOUS_LIVE,
        strategy_decision=placeholder_decision,
        risk_approval=None,
        execution=execution,
        playbook=playbook,
    )
    return {
        "goal": "autonomous_trading_without_manual_help",
        "ready": policy.allowed,
        "agent_policy": policy,
        "playbook_coverage": playbook,
        "execution": execution,
    }


def to_primitive(value):
    if is_dataclass(value):
        return to_primitive(asdict(value))
    if isinstance(value, dict):
        return {key: to_primitive(item) for key, item in value.items() if not (key == "all_strategy_decisions" and item is None)}
    if isinstance(value, list | tuple):
        return [to_primitive(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


if __name__ == "__main__":
    main()
