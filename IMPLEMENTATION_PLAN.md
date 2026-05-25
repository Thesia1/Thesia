# Implementation Plan: Live Agentic Forex Trading Bot

## Mission

Build a live-useful forex trading bot that can scan markets, identify deterministic supply/demand setups, pass trades through strict risk controls, execute through a broker, reconcile account state, and explain what it did.

The goal is top-tier process quality, not profit promises. The bot must be hard to fool, easy to audit, and conservative with live capital.

## Current Foundation

Already present:

- Live architecture blueprint: `LIVE_TRADING_BOT_BLUEPRINT.md`
- Strategy spec template: `STRATEGY_SPEC_TEMPLATE.md`
- Risk models: `forex_bot/models.py`
- Initial risk gate: `forex_bot/risk_gate.py`
- Risk gate tests: `tests/test_risk_gate.py`
- Strategy source material:
  - `Echo Trading Bot.docx`
  - `Raja Complete Course Notes(1).pdf`
  - `PoB English.pdf`

## Current External Research Snapshot

### Broker and Execution

Primary broker path: OANDA v20 REST API.

Rationale:

- Official practice and live account support.
- Official REST endpoints for accounts, orders, trades, positions, and pricing.
- Pricing stream available for live updates.
- Official API comparison lists v20 REST polling rate limit as 30 requests per second.

References:

- OANDA v20 introduction: https://developer.oanda.com/rest-live-v20/introduction/
- OANDA pricing stream: https://developer.oanda.com/rest-live-v20/pricing-ep/
- OANDA API comparison/rate limits: https://developer.oanda.com/rest-live-v20/api-comparison/
- OANDA order definitions: https://developer.oanda.com/rest-live-v20/order-df/

Secondary broker paths:

- MetaTrader 5 later if the user wants broker flexibility.
- Interactive Brokers later if multi-asset support becomes important.

References:

- MetaTrader 5 trading operations: https://www.metatrader5.com/en/terminal/help/trading
- MetaTrader 5 algorithmic trading/Python notes: https://www.metatrader5.com/en/terminal/help/algotrading/trade_robots_indicators
- IBKR TWS API docs: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/

### Storage and Messaging

For v1, do not use Redis as a required component.

Use:

- SQLite for the first local prototype if speed matters.
- Postgres/TimescaleDB for live persistence.
- NATS JetStream later only if we split into services and need durable event streaming.

References:

- NATS JetStream persistence and replay: https://docs.nats.io/nats-concepts/jetstream
- Redpanda Kafka-compatible streaming: https://www.redpanda.com/what-is-redpanda
- TimescaleDB docs via PostgreSQL ecosystem: https://access.crunchydata.com/documentation/timescaledb/latest/

### Economic Calendar and News Blackouts

Use official or licensed calendar APIs. Do not depend on scraping Forex Factory for live trading.

Candidate providers:

- Trading Economics API for economic calendar and live calendar stream.
- Econoday API for economic event delivery.

References:

- Trading Economics API docs: https://docs.tradingeconomics.com/
- Trading Economics calendar streaming: https://docs.tradingeconomics.com/economic_calendar/streaming/
- Econoday REST API docs: https://api.econoday.com/api/api.html

### Strategy Research

The bot should start with the Raja/PoB supply-demand method because that is the project identity. We can add quant baselines to challenge it:

- Time-series momentum / trend following
- Breakout with volatility filters
- Mean reversion only in confirmed range regimes
- Carry/macro only as a slow context filter, not first live execution

References:

- Two centuries of trend following research: https://arxiv.org/abs/1404.3274
- QuantConnect LEAN open-source backtesting/live engine docs: https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/algorithm-engine
- Backtrader framework docs: https://www.backtrader.com/
- VectorBT docs: https://vectorbt.dev/

### Risk and Compliance Reality Check

The CFTC warns that no automated trading technology can consistently predict the future and warns against AI/bot marketing that promises guaranteed or outsized returns. Our build must stay auditable, conservative, and clear that it is a tool, not a money machine.

References:

- CFTC forex fraud advisory: https://www.cftc.gov/LearnAndProtect/forexfrauds
- CFTC AI trading bot advisory: https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/AITradingBots.html

## Product Modes

The dashboard must expose five explicit modes:

1. `OFF`
   - No scans.
   - No broker actions.

2. `WATCH`
   - Scan markets.
   - Explain possible setups.
   - No orders.

3. `ASSISTED`
   - Scan markets.
   - Produce trade candidates.
   - Human approves or rejects each trade.

4. `AUTONOMOUS_PAPER`
   - Trade OANDA practice account without per-trade approval.
   - Full risk, strategy, execution, and reconciliation checks active.

5. `AUTONOMOUS_LIVE`
   - Trade live account without per-trade approval.
   - Only allowed after all readiness gates pass.

## Architecture

### V1 Shape

Start as a modular monolith.

Reason:

- Easier to test.
- Easier to audit.
- Fewer moving parts.
- Better for a first live bot than distributed services.

Initial process layout:

```text
bot runtime
├── config
├── broker adapter
├── market data service
├── strategy engine
├── risk gate
├── execution engine
├── reconciliation loop
├── agent orchestrator
├── persistence
└── dashboard/API
```

### Later Service Split

Only split into services after the modular monolith proves stable:

```text
data-ingestor
strategy-service
risk-service
executor-service
agent-service
dashboard
```

Use NATS JetStream or Redpanda only when service split requires durable event replay.

## Core Data Models

Add or expand:

- `Candle`
- `Tick`
- `Instrument`
- `SpreadSnapshot`
- `Zone`
- `SetupDetection`
- `StrategyDecision`
- `TradeCandidate`
- `RiskApproval`
- `OrderIntent`
- `BrokerOrder`
- `Trade`
- `Position`
- `AccountSnapshot`
- `ModeChange`
- `AgentDecision`
- `NewsEvent`
- `ExecutionAudit`

Everything that can affect a live trade must be persisted.

## Broker Implementation Plan

### OANDA Adapter

Implement:

- Account summary
- Instruments
- Historical candles
- Current pricing
- Pricing stream
- Create market order
- Create limit order
- Attach stop loss on fill
- Attach take profit on fill
- Close trade
- List open trades
- List positions
- Transaction stream

Safety rules:

- Use practice environment by default.
- Require explicit config for live URL/account.
- Never infer live mode from environment accidentally.
- Every order must include a client order ID.
- Every order must be linked to a strategy decision ID.

### Broker State Reconciliation

Before any execution:

- Pull open trades.
- Pull open positions.
- Pull pending orders.
- Compare against local state.
- Block trading if local state and broker state disagree.

After any execution:

- Confirm broker transaction.
- Persist order response.
- Refresh open positions.
- Verify stop loss exists.

## Strategy Implementation Plan

### Strategy Layer Principle

The LLM/agent does not generate signals directly.

The deterministic strategy engine produces:

- `NO_TRADE`
- `WATCH`
- `TRADE_CANDIDATE`

The agent can:

- request evaluation
- explain evidence
- veto abnormal conditions
- request execution for approved candidates in autonomous mode

The agent cannot:

- create raw broker orders
- size positions
- bypass the risk gate
- skip broker reconciliation

### Phase 1 Strategy: Fresh Strong Zone Continuation

This is the first tradable setup because it is closest to Raja's core method and easiest to constrain.

Requirements:

- Higher timeframe direction determined.
- Fresh supply/demand zone detected.
- Zone removed an opposite zone.
- Buy setups prefer low curve.
- Sell setups prefer high curve.
- Candle-close confirmation required for v1.
- Stop beyond zone boundary plus buffer.
- Target nearest opposing higher-timeframe zone.
- Minimum reward-to-risk.
- News blackout respected.

### Machine Definitions Needed

Implement in this order:

1. Candle normalization
2. ATR and volatility measures
3. Swing high/low detection
4. Base candle detection
5. Departure candle detection
6. Supply/demand zone construction
7. Zone freshness/retest detection
8. Opposite-zone removal
9. Curve position
10. Candle-close confirmation
11. Entry/stop/target construction
12. Strategy decision explanation

### Phase 2 Strategy Expansion

After Phase 1 proves stable:

- CP
- PCP
- Arrival zones
- Realignment
- Wow trade

After those:

- RBR
- DBD
- RBD
- DBR
- SNRC1/2/3
- Hybrid 1/2
- QML/QMC/QMM
- Blindspot 1/2
- CLAB
- CK1/CK2/CK3

Each setup needs its own spec, detector, tests, backtest report, and paper-trading report.

## Research Pipeline

### Strategy Experiment Rules

No strategy goes live because it sounds good.

Required path:

```text
idea
-> deterministic spec
-> unit tests
-> historical backtest
-> walk-forward test
-> stress test
-> paper trading
-> live-assisted
-> limited autonomous live
```

### Backtest Requirements

Must include:

- Bid/ask spread
- Slippage
- Session filters
- Weekend gap rules
- News blackout rules
- No lookahead bias
- Same strategy code path as live where possible
- Per-pair metrics
- Per-setup metrics
- Trade distribution analysis
- Drawdown analysis
- Monte Carlo trade-order reshuffling
- Parameter sensitivity

### Acceptance Metrics

Do not require unrealistic perfection.

Minimum gate candidates:

- At least 100 historical trades before trusting per-setup metrics, when possible.
- Positive expectancy after spread/slippage.
- Profit factor above configured threshold.
- Max drawdown below configured threshold.
- No single trade or week explains most profit.
- Performance survives walk-forward validation.
- Performance does not collapse under reasonable slippage increase.

### Live Research Agent

The research agent may:

- collect strategy ideas
- summarize market regime notes
- compare performance reports
- propose parameter experiments
- identify degraded strategies

The research agent may not:

- promote a strategy to live automatically
- loosen risk limits
- change live parameters without approval

## Risk System Roadmap

Current:

- Basic percentage-risk sizing
- Max spread
- Daily loss block
- Weekly loss block
- Open trade count block
- Reward-to-risk block
- Margin check

Add:

- Pair-specific risk profiles
- Currency exposure aggregation
- Correlation exposure limits
- Session-specific spread limits
- Volatility-adjusted max stop distance
- Min stop distance
- Max slippage
- Consecutive-loss pause
- Strategy-level drawdown pause
- Account-level kill switch
- Broker uncertainty kill switch
- News blackout kill switch

Initial live risk profile:

```text
risk_per_trade: 0.25%
max_daily_loss: 1.0% to 2.0%
max_weekly_loss: 3.0% to 5.0%
max_open_trades: 1
allowed_pairs: EUR_USD only at first
live_mode: assisted first
```

## Execution Engine Roadmap

Implement order lifecycle state machine:

```text
CREATED
-> RISK_APPROVED
-> SUBMITTED
-> ACCEPTED
-> FILLED
-> STOP_ATTACHED
-> MANAGED
-> CLOSED
```

Failure states:

```text
REJECTED
CANCELLED
PARTIAL_FILL
UNKNOWN_BROKER_STATE
RECONCILIATION_FAILED
```

Rules:

- Unknown broker state stops execution.
- Missing stop loss triggers emergency close or alert.
- Duplicate client order ID is rejected.
- Broker retry is idempotent.
- Partial fills are reconciled before any new trade.

## Agent Roadmap

### Agent Tools

Expose controlled tools:

- `scan_markets`
- `evaluate_strategy`
- `request_risk_approval`
- `request_execution`
- `pause_trading`
- `resume_trading`
- `summarize_account`
- `explain_decision`
- `generate_daily_report`

### Agent Memory

Persist:

- decisions
- vetoes
- explanations
- market regime notes
- mode changes
- operator approvals

Do not rely on chat memory for trading state.

### Agent Evaluation

Test the agent with scenarios:

- high spread
- conflicting timeframe signals
- broker disconnect
- news event approaching
- daily loss limit reached
- strategy candidate missing stop loss
- local state differs from broker state

The correct agent behavior is to pause or reject, not improvise.

## Dashboard Roadmap

Views:

- Mode switch
- Broker connection status
- Account equity and daily loss usage
- Open trades
- Watchlist
- Strategy decisions
- Risk rejections
- Agent explanations
- Economic calendar blackout window
- Backtest reports
- Paper/live performance
- Emergency stop

Controls:

- Set mode
- Pause trading
- Resume trading
- Approve assisted trade
- Reject assisted trade
- Flatten all positions
- Run backtest
- Export audit log

## Infrastructure Roadmap

### Local Development

Use:

- Python package structure
- `unittest` or pytest once dependencies are pinned
- `.env` for secrets, never committed
- SQLite initially if Postgres is not configured
- Docker Compose when adding Postgres/TimescaleDB

### Production

Use:

- VPS or cloud VM near broker endpoint
- Process supervisor
- Encrypted secrets
- Daily database backup
- Log retention
- Alerting to email/SMS/Telegram/Discord
- Health checks
- Restart recovery

## Milestones

### Milestone 0: Repo Hygiene

Status: in progress.

Deliverables:

- Git remote configured.
- `.gitignore` present.
- Basic package structure present.
- Initial risk gate tested.

### Milestone 1: Project Skeleton

Deliverables:

- Config loader
- Logging setup
- CLI entrypoint
- Persistence interface
- SQLite local store
- Domain models expanded
- Test runner documented

### Milestone 2: OANDA Read-Only Adapter

Deliverables:

- Practice account config
- Account summary fetch
- Instrument fetch
- Candle fetch
- Current pricing fetch
- Read-only integration tests with mocked responses

Exit gate:

- No live credentials required.
- No order code yet.

### Milestone 3: Market Data Store

Deliverables:

- Candle schema
- Tick/spread schema
- Historical candle sync
- Data freshness checks
- UTC normalization
- Missing candle detection

Exit gate:

- Can build clean multi-timeframe candle sets for EUR_USD.

### Milestone 4: Strategy Detector v1

Deliverables:

- ATR
- Swings
- Base/departure candles
- Supply/demand zones
- Strong zone detection
- Fresh/retested detection
- Curve location
- Trade candidate builder
- Rule-by-rule explanation

Exit gate:

- Strategy returns `NO_TRADE`, `WATCH`, or `TRADE_CANDIDATE`.

### Milestone 5: Backtester

Deliverables:

- Event-based backtest loop
- Same strategy code path as live
- Spread/slippage model
- Risk gate integration
- Trade ledger
- Performance report
- Walk-forward runner

Exit gate:

- Backtest report generated for EUR_USD.

### Milestone 6: Paper Execution

Deliverables:

- OANDA practice order placement
- Client order IDs
- Stop-loss attachment
- Take-profit attachment
- Order lifecycle persistence
- Broker reconciliation
- Emergency pause

Exit gate:

- Practice order can be placed, verified, and closed safely.

### Milestone 7: Agent Orchestrator

Deliverables:

- Tool registry
- Mode-aware permissions
- Agent explanation flow
- Agent veto flow
- Daily report
- Scenario tests

Exit gate:

- Agent can operate in `WATCH`, `ASSISTED`, and `AUTONOMOUS_PAPER`.

### Milestone 8: Dashboard

Deliverables:

- Mode switch
- Account status
- Watchlist
- Trade candidates
- Approval controls
- Open positions
- Risk alerts
- Emergency stop

Exit gate:

- User can run the bot without touching the terminal.

### Milestone 9: Paper Trading Trial

Requirements:

- At least 30 trading days.
- No duplicate orders.
- No missing stop losses.
- No unexplained broker state.
- All rejections logged.
- Daily report generated.

Exit gate:

- Decide whether to continue, revise, or retire the strategy.

### Milestone 10: Live-Assisted

Requirements:

- Smallest practical size.
- One pair only.
- Human approval for each trade.
- Hard daily loss shutdown.
- Full audit log.

Exit gate:

- Stable operation with no process, reconciliation, or safety failures.

### Milestone 11: Limited Live-Autonomous

Requirements:

- One pair at first.
- One open trade max.
- Low risk per trade.
- No high-impact news trading.
- Daily auto-shutdown after limit.
- Weekly review.

Exit gate:

- Only expand after stability, not after excitement.

## Immediate Next Sprint

Sprint goal:

Create a working local bot core that can load config, fetch mocked market data, detect the initial setup shape, pass it to the risk gate, and produce a structured decision.

Tasks:

1. Add config module.
2. Add logging/audit module.
3. Expand domain models.
4. Add candle model and timeframe utilities.
5. Implement ATR.
6. Implement swing high/low detection.
7. Implement base/departure candle detection.
8. Implement zone construction.
9. Implement `fresh_strong_zone_continuation` detector.
10. Add unit tests for all detector pieces.
11. Add a simple CLI: `python -m forex_bot scan --pair EUR_USD`.
12. Add mock OANDA response fixtures.

Definition of done:

- Tests pass locally.
- Bot produces a structured strategy decision.
- Risk gate approves or rejects the candidate.
- No broker order code is active yet.

