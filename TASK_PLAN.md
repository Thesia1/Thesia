# Task Plan: Live Agentic Forex Trading Bot

## Execution Rules

This task plan is ordered. Do not skip safety, testing, or paper-trading gates to reach live mode faster.

Every implementation task should produce one or more of:

- working code
- tests
- documentation
- fixtures
- verified runtime behavior

Every live-trading feature must be traceable through:

```text
strategy decision -> risk approval -> execution intent -> broker response -> reconciliation -> audit log
```

## Phase 0: Project Baseline

Goal: make the repository clean, runnable, and ready for serious implementation.

### 0.1 Repository Hygiene

Tasks:

- Confirm repository remote and default branch.
- Commit current planning docs.
- Keep `.DS_Store`, secrets, caches, and virtual environments ignored.
- Add a `README.md` with project purpose, warning, setup, and current status.
- Add a `Makefile` or simple command list for tests and common tasks.

Deliverables:

- `.gitignore`
- `README.md`
- clean working tree
- documented test command

Acceptance:

- Running the documented test command passes.
- No generated files are staged.

### 0.2 Python Package Setup

Tasks:

- Add `pyproject.toml`.
- Define package metadata.
- Add development dependencies once dependency management is chosen.
- Keep runtime dependencies minimal at first.
- Add type-check/lint placeholders, even if not enforced yet.

Deliverables:

- `pyproject.toml`
- package import works from project root

Acceptance:

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes.
- `python3 -c "import forex_bot"` succeeds.

## Phase 1: Core Domain and Configuration

Goal: create the stable internal language of the bot.

### 1.1 Configuration System

Tasks:

- Add `forex_bot/config.py`.
- Support local environment variables.
- Support a config file later, but do not require one for tests.
- Define modes:
  - `OFF`
  - `WATCH`
  - `ASSISTED`
  - `AUTONOMOUS_PAPER`
  - `AUTONOMOUS_LIVE`
- Define broker environment:
  - `practice`
  - `live`
- Require explicit opt-in for live mode.

Deliverables:

- `BotConfig`
- `BrokerConfig`
- `RiskConfig`
- config tests

Acceptance:

- Missing live credentials cannot accidentally enable live mode.
- Practice mode is the default.

### 1.2 Domain Models

Tasks:

- Expand `forex_bot/models.py`.
- Add `Candle`.
- Add `PriceSnapshot`.
- Add `SpreadSnapshot`.
- Add `Zone`.
- Add `SetupDetection`.
- Add `StrategyDecision`.
- Add `OrderIntent`.
- Add `BrokerOrder`.
- Add `Position`.
- Add `ExecutionAudit`.
- Add `ModeChange`.

Deliverables:

- typed domain models
- validation helpers where needed
- tests for critical invariants

Acceptance:

- Trade candidate cannot exist without symbol, direction, entry, stop, and decision id.
- Order intent cannot exist without risk approval id.

### 1.3 Logging and Audit Events

Tasks:

- Add structured logging helpers.
- Define audit event names.
- Ensure every risk decision can be serialized.
- Ensure every strategy decision can be serialized.

Deliverables:

- `forex_bot/audit.py`
- audit event models or helpers
- audit serialization tests

Acceptance:

- Audit records are JSON-serializable.
- Sensitive values are not logged.

## Phase 2: Persistence

Goal: persist everything needed to recover and audit trading behavior.

### 2.1 Persistence Interface

Tasks:

- Add `forex_bot/persistence.py`.
- Define repository methods for:
  - candles
  - strategy decisions
  - risk approvals
  - order intents
  - broker orders
  - positions
  - account snapshots
  - audit events
  - mode changes
- Start with an in-memory implementation for tests.

Deliverables:

- persistence interface
- in-memory store
- tests

Acceptance:

- A full mocked trade lifecycle can be stored and retrieved.

### 2.2 SQLite Store

Tasks:

- Add SQLite schema.
- Add migrations or schema initialization.
- Persist candles.
- Persist decisions.
- Persist risk approvals.
- Persist order lifecycle.
- Persist reconciliation snapshots.

Deliverables:

- SQLite store
- schema file or migration helper
- tests using temporary database

Acceptance:

- Bot can restart and reload last known account/order state from SQLite.

### 2.3 Postgres/TimescaleDB Plan

Tasks:

- Add schema notes for live deployment.
- Identify hypertable candidates:
  - candles
  - ticks
  - spreads
  - account snapshots
- Keep Postgres implementation deferred until local behavior is stable.

Deliverables:

- `docs/persistence.md`

Acceptance:

- Clear migration path exists from SQLite prototype to Postgres live store.

## Phase 3: Market Data

Goal: produce clean multi-timeframe price data for strategy evaluation.

### 3.1 Candle Utilities

Tasks:

- Add timeframe enum.
- Add candle sorting.
- Add candle continuity checks.
- Add resampling from lower timeframe to higher timeframe if needed.
- Normalize all timestamps to UTC.

Deliverables:

- `forex_bot/market_data.py`
- candle utility tests

Acceptance:

- Missing candles are detected.
- Out-of-order candles are rejected or corrected deterministically.

### 3.2 Indicator Primitives

Tasks:

- Implement true range.
- Implement ATR.
- Implement candle body size.
- Implement wick size.
- Implement body-to-range ratio.
- Implement bullish/bearish candle helpers.

Deliverables:

- `forex_bot/indicators.py`
- tests with hand-calculated fixtures

Acceptance:

- ATR and candle metrics match expected values on known data.

### 3.3 Swing Detection

Tasks:

- Implement swing high detection.
- Implement swing low detection.
- Add configurable lookback/lookforward window.
- Prevent lookahead usage in live mode.

Deliverables:

- swing detection functions
- tests for live-safe behavior

Acceptance:

- Historical mode may confirm swings with future bars.
- Live mode only confirms swings after enough candles have closed.

## Phase 4: Strategy Engine v1

Goal: turn the first Raja/PoB strategy slice into deterministic code.

### 4.1 Strategy Framework

Tasks:

- Add `forex_bot/strategy/__init__.py`.
- Define strategy interface.
- Define `StrategyContext`.
- Define `StrategyResult`.
- Define rule evidence objects.
- Support `NO_TRADE`, `WATCH`, `TRADE_CANDIDATE`.

Deliverables:

- strategy framework
- tests for strategy result serialization

Acceptance:

- Every strategy result includes rule evidence and explanation text.

### 4.2 Base and Departure Candles

Tasks:

- Encode base candle criteria:
  - max body-to-range ratio
  - max range relative to ATR
  - max consecutive base candles
- Encode departure candle criteria:
  - minimum body relative to base
  - minimum range relative to ATR
  - close beyond base range
- Make thresholds configurable.

Deliverables:

- base candle detector
- departure candle detector
- tests

Acceptance:

- Detectors correctly classify fixture candles.
- Ambiguous candles return explainable failures.

### 4.3 Supply and Demand Zones

Tasks:

- Build demand zones from base plus bullish departure.
- Build supply zones from base plus bearish departure.
- Store zone high, low, source candles, timeframe, and created timestamp.
- Mark zones as fresh, retested, or invalidated.

Deliverables:

- zone builder
- freshness/retest detector
- invalidation detector
- tests

Acceptance:

- Zone boundaries are deterministic.
- Retests and invalidations are reproducible.

### 4.4 Opposite-Zone Removal

Tasks:

- Define opposite zone removal by candle close beyond zone boundary.
- Add optional wick-based mode later, but default to candle close.
- Track which zone removed which opposite zone.
- Mark zones as strong or weak.

Deliverables:

- strong zone classifier
- tests

Acceptance:

- Strong zones require documented opposite-zone removal.

### 4.5 Curve Location

Tasks:

- Define high/low curve range anchors.
- Compute current price percentile inside range.
- Classify:
  - high curve
  - low curve
  - middle
- Apply no-trade rule in the middle unless explicitly overridden.

Deliverables:

- curve classifier
- tests

Acceptance:

- Buy candidates near high curve are rejected.
- Sell candidates near low curve are rejected.

### 4.6 Fresh Strong Zone Continuation

Tasks:

- Implement first v1 setup:
  - higher timeframe direction
  - fresh strong zone
  - curve alignment
  - return to zone
  - candle-close confirmation
  - stop beyond zone plus buffer
  - target nearest opposing zone
  - minimum reward-to-risk
- Produce `TradeCandidate` only when all required rules pass.

Deliverables:

- `forex_bot/strategy/fresh_strong_zone.py`
- strategy tests
- fixture data

Acceptance:

- Strategy returns `NO_TRADE` for weak/noisy setups.
- Strategy returns `WATCH` for valid context without entry.
- Strategy returns `TRADE_CANDIDATE` only with entry, stop, target, and evidence.

## Phase 5: Risk Gate Expansion

Goal: harden the existing risk gate for live safety.

### 5.1 Risk Profile System

Tasks:

- Add pair-specific risk settings.
- Add account-level defaults.
- Add session-specific spread limits.
- Add min/max stop distance.
- Add max units per pair.

Deliverables:

- risk profile model
- tests

Acceptance:

- EUR_USD and XAU_USD can have different constraints.

### 5.2 Exposure Controls

Tasks:

- Track open risk by trade.
- Track exposure by currency.
- Track correlated pair exposure.
- Reject trades that exceed exposure limits.

Deliverables:

- exposure calculator
- tests

Acceptance:

- Bot rejects overexposure even if single-trade risk looks valid.

### 5.3 Kill Switches

Tasks:

- Add daily loss kill switch.
- Add weekly loss kill switch.
- Add consecutive loss pause.
- Add broker uncertainty pause.
- Add missing stop-loss emergency rule.

Deliverables:

- kill switch module
- tests

Acceptance:

- Any kill switch can force `OFF` or `PAUSED` execution state.

## Phase 6: OANDA Read-Only Adapter

Goal: safely connect to broker data without any order-writing capability.

### 6.1 Broker Adapter Interface

Tasks:

- Define broker protocol/interface.
- Methods:
  - get account summary
  - get instruments
  - get candles
  - get current pricing
  - get open trades
  - get open positions

Deliverables:

- `forex_bot/brokers/base.py`
- tests with fake broker

Acceptance:

- Strategy and risk code depend on the interface, not OANDA directly.

### 6.2 OANDA Client

Tasks:

- Add OANDA HTTP client.
- Support practice URL by default.
- Load token from environment.
- Add request timeout.
- Add retry policy for safe read-only calls.
- Add response parsing.

Deliverables:

- `forex_bot/brokers/oanda.py`
- mocked tests

Acceptance:

- No live URL is used unless explicitly configured.
- Tests do not require real credentials.

### 6.3 OANDA Candle Sync

Tasks:

- Fetch historical candles.
- Normalize into `Candle`.
- Store in persistence.
- Handle pagination if needed.
- Track sync cursor.

Deliverables:

- candle sync service
- mocked tests

Acceptance:

- EUR_USD candles can be synced from mocked OANDA responses.

## Phase 7: Backtesting

Goal: prove the strategy behaves historically before practice trading.

### 7.1 Event-Based Backtest Loop

Tasks:

- Feed candles sequentially.
- Avoid lookahead.
- Run same strategy detector as live.
- Run same risk gate as live.
- Simulate fills.
- Simulate stops and targets.

Deliverables:

- `forex_bot/backtest.py`
- tests

Acceptance:

- A known fixture produces expected trades.

### 7.2 Cost Model

Tasks:

- Add spread simulation.
- Add slippage simulation.
- Add commission placeholder.
- Add session-specific spread widening.

Deliverables:

- cost model
- tests

Acceptance:

- Strategy profitability changes when costs increase.

### 7.3 Report Generator

Tasks:

- Compute expectancy.
- Compute win rate.
- Compute profit factor.
- Compute max drawdown.
- Compute average reward-to-risk.
- Compute trade distribution.
- Export JSON and Markdown reports.

Deliverables:

- backtest report module
- sample report

Acceptance:

- Report clearly states whether strategy passed gates.

## Phase 8: Paper Execution

Goal: execute in OANDA practice account with full safety.

### 8.1 Order Intent State Machine

Tasks:

- Implement order lifecycle states.
- Persist state transitions.
- Reject duplicate client order IDs.
- Attach risk approval id to every intent.

Deliverables:

- `forex_bot/execution.py`
- tests

Acceptance:

- Cannot submit an order without risk approval.

### 8.2 OANDA Practice Orders

Tasks:

- Add market order.
- Add limit order if needed.
- Attach stop loss.
- Attach take profit.
- Parse broker response.
- Persist broker order id and transaction id.

Deliverables:

- OANDA write adapter behind explicit practice-only config
- mocked tests

Acceptance:

- Write functions cannot run unless mode is `AUTONOMOUS_PAPER` or `ASSISTED` with approval.

### 8.3 Reconciliation Loop

Tasks:

- Pull open trades.
- Pull open positions.
- Compare broker state to local state.
- Detect unknown broker state.
- Verify stop loss exists.
- Pause execution on mismatch.

Deliverables:

- reconciliation module
- tests

Acceptance:

- Missing stop loss triggers emergency state.
- Position mismatch blocks new trades.

## Phase 9: Agent Orchestrator

Goal: let the agent operate the bot through controlled tools.

### 9.1 Tool Registry

Tasks:

- Add tool definitions:
  - scan markets
  - evaluate strategy
  - request risk approval
  - request execution
  - pause trading
  - resume trading
  - explain decision
  - generate report
- Enforce mode permissions.

Deliverables:

- `forex_bot/agent/tools.py`
- tests

Acceptance:

- Agent cannot call execution in `WATCH`.
- Agent can request execution in `AUTONOMOUS_PAPER` only after risk approval.

### 9.2 Agent Decision Policies

Tasks:

- Add policy rules for when to pause.
- Add policy rules for when to veto.
- Add policy rules for when to request execution.
- Add prompt/system instructions later if using an LLM API.

Deliverables:

- agent policy module
- scenario tests

Acceptance:

- High spread, news blackout, and broker mismatch all lead to no execution.

### 9.3 Reports

Tasks:

- Daily report.
- Weekly report.
- Trade explanation.
- Risk rejection explanation.

Deliverables:

- report templates
- tests

Acceptance:

- Every trade and rejection can be explained from stored evidence.

## Phase 10: Dashboard/API

Goal: give the user non-technical control over the bot.

### 10.1 Local API

Tasks:

- Add API server.
- Expose account status.
- Expose mode status.
- Expose strategy decisions.
- Expose risk decisions.
- Expose open positions.
- Expose approve/reject actions.
- Expose emergency stop.

Deliverables:

- API app
- API tests

Acceptance:

- Dashboard can operate without direct access to internals.

### 10.2 Dashboard

Tasks:

- Mode switch.
- Broker status.
- Account status.
- Daily loss meter.
- Watchlist.
- Trade candidates.
- Human approval controls.
- Open positions.
- Risk alerts.
- Agent explanations.
- Emergency stop.

Deliverables:

- dashboard app
- browser verification

Acceptance:

- User can run watch/assisted/paper mode from UI.

## Phase 11: Paper Trading Trial

Goal: prove behavior in live market conditions without live money.

Tasks:

- Run OANDA practice account for at least 30 trading days.
- Monitor duplicate orders.
- Monitor missing stops.
- Monitor broker mismatches.
- Track spread/slippage.
- Track strategy degradation.
- Generate daily reports.
- Generate final paper-trading report.

Deliverables:

- paper trading log
- daily reports
- final paper report

Acceptance:

- No safety-critical incidents.
- Positive or acceptable expectancy after realistic costs.
- Clear decision: continue, revise, or retire setup.

## Phase 12: Live-Assisted

Goal: introduce real capital with human approval and smallest practical risk.

Tasks:

- Enable live read-only first.
- Confirm live account reconciliation.
- Enable assisted live order intent.
- Require manual approval per trade.
- Use smallest practical position size.
- Enforce hard daily loss shutdown.
- Monitor every order.

Deliverables:

- live-assisted checklist
- live-assisted report

Acceptance:

- No unexpected broker state.
- No missing stop loss.
- No order without approval.
- No breach of daily or weekly loss rules.

## Phase 13: Limited Live Autonomous

Goal: enable autonomous live mode only after assisted mode is boring and stable.

Tasks:

- Limit to one pair.
- Limit to one open trade.
- Keep low risk per trade.
- Disable trading around high-impact news.
- Enable automatic daily shutdown.
- Enable weekly performance review.
- Require explicit switch to `AUTONOMOUS_LIVE`.

Deliverables:

- autonomous live checklist
- weekly live reports

Acceptance:

- Bot can operate unattended within strict limits.
- Any uncertainty causes pause, not improvisation.

## Phase 14: Strategy Expansion

Goal: add more setups only after the first setup is stable.

Order:

1. CP
2. PCP
3. Arrival zone
4. Realignment
5. Wow trade
6. RBR
7. DBD
8. RBD
9. DBR
10. SNRC1
11. SNRC2
12. SNRC3
13. Hybrid 1
14. Hybrid 2
15. QML
16. QMC
17. QMM
18. Blindspot 1
19. Blindspot 2
20. CLAB
21. CK1
22. CK2
23. CK3

Each setup requires:

- deterministic spec
- detector
- unit tests
- backtest
- paper trial
- live-assisted trial
- explicit promotion approval

## First Sprint Backlog

Sprint goal: produce a working local strategy decision pipeline without broker orders.

Tasks:

1. Add `README.md`.
2. Add `pyproject.toml`.
3. Add `forex_bot/config.py`.
4. Expand domain models.
5. Add `forex_bot/market_data.py`.
6. Add `forex_bot/indicators.py`.
7. Add ATR tests.
8. Add candle metric tests.
9. Add swing detection.
10. Add swing detection tests.
11. Add strategy framework.
12. Add base candle detector.
13. Add departure candle detector.
14. Add supply/demand zone model.
15. Add first fixture candle set.
16. Wire strategy candidate into the existing risk gate.
17. Add CLI stub: `python3 -m forex_bot scan --pair EUR_USD`.

Definition of done:

- All tests pass.
- CLI returns a structured `NO_TRADE`, `WATCH`, or `TRADE_CANDIDATE` result using fixture data.
- Risk gate is called for any candidate.
- No real broker order capability exists yet.

