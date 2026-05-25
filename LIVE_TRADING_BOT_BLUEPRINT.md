# Live Forex Trading Bot Blueprint

## Goal

Build a useful live forex trading bot that can analyze supply/demand setups, manage risk, place broker orders, reconcile positions, and explain its decisions without allowing the LLM agent to improvise trades.

The live bot must be useful before it is fully autonomous. The safest path is:

1. Research mode
2. Backtest mode
3. Paper trading mode
4. Live-assisted mode
5. Limited live-autonomous mode

## Broker Path

Default broker target: OANDA v20 API.

Why:

- Supports practice and live environments.
- Has REST endpoints for accounts, pricing, orders, trades, and positions.
- Allows a single broker adapter to be tested in practice before live mode.

References:

- OANDA REST v20 introduction: https://developer.oanda.com/rest-live-v20/introduction/
- OANDA development guide: https://developer.oanda.com/rest-live-v20/development-guide/
- OANDA order schema: https://developer.oanda.com/rest-live-v20/order-df/

## Core Principle

The agent can advise, classify, explain, and veto.

The agent cannot:

- Create orders directly.
- Override risk limits.
- Increase position size.
- Trade without deterministic strategy confirmation.
- Trade when broker state is uncertain.

## Live System Modules

### 1. Data Layer

Responsibilities:

- Fetch bid/ask candles and current pricing.
- Store raw candles and normalized candles.
- Track spread history.
- Detect stale feeds and missing candles.
- Normalize all timestamps to UTC.
- Block weekend gap and market-open noise unless explicitly allowed.

Minimum live checks:

- Reject signals if candle data is incomplete.
- Reject signals if spread exceeds pair-specific maximum.
- Reject signals if last price update is stale.
- Reject signals if broker price and local candle state disagree materially.

### 2. Strategy Engine

Responsibilities:

- Detect strategy setups from deterministic rules.
- Produce a structured trade candidate.
- Explain which rules passed or failed.
- Never use free-form LLM output as a signal.

Inputs:

- Pair
- Timeframes
- Candles
- Current bid/ask
- Existing broker positions
- Strategy configuration

Outputs:

- `NO_TRADE`
- `WATCH`
- `TRADE_CANDIDATE`

Trade candidate must include:

- Pair
- Direction
- Setup family
- Entry type
- Entry price or market intent
- Stop loss
- Take profit or management rule
- Invalidation reason
- Timeframe alignment
- Confidence score from deterministic evidence
- Required risk approval result

### 3. Risk Gate

The risk gate is mandatory and final.

It must approve every candidate before execution.

Checks:

- Max risk per trade
- Max daily loss
- Max weekly loss
- Max open trades
- Max correlated exposure
- Max pair exposure
- Min reward-to-risk
- Max spread
- Max slippage
- Required stop loss
- Required broker state reconciliation
- News blackout window
- Session filter
- Account leverage and margin availability

Sizing:

Use percentage-risk sizing, not fixed lot-size rules.

Formula:

```text
risk_amount = account_equity * risk_percent
units = risk_amount / (stop_distance_pips * pip_value_per_unit)
```

Then clamp units by:

- broker minimum/maximum size
- margin availability
- strategy maximum size
- account-level kill switch

### 4. Execution Engine

Responsibilities:

- Place orders only after risk approval.
- Attach stop loss at order creation whenever broker supports it.
- Prevent duplicate orders.
- Track order lifecycle.
- Reconcile open trades and positions with the broker.
- Retry safely on transient failures.
- Stop trading on unknown broker state.

Live execution requirements:

- Every order has a client order id.
- Every order has a stop loss.
- Every order has a recorded strategy decision id.
- Failed or rejected orders are logged and not blindly retried.
- On restart, broker state is reconciled before new signals are allowed.

### 5. Agent Orchestrator

Allowed uses:

- Summarize market context.
- Classify market regime.
- Review rule evidence.
- Explain why a setup passed or failed.
- Detect news or abnormal conditions.
- Produce daily and weekly reports.
- Recommend pausing, never force continuing.

Not allowed:

- Direct broker API access.
- Direct order creation.
- Direct lot-size selection.
- Direct override of risk gate.

### 6. Observability

Must track:

- Account equity
- Realized and unrealized P/L
- Daily loss usage
- Open risk
- Spread at entry
- Slippage
- Rejected signals
- Risk-gate rejections
- Broker API errors
- Data freshness
- Agent vetoes

Alerts:

- Max daily loss reached
- Broker reconciliation failed
- Data feed stale
- Unexpected open position
- Repeated order rejection
- Spread spike
- Strategy drawdown threshold reached

## Live Readiness Gates

### Gate 1: Strategy Spec Complete

No setup can be traded until its rules are deterministic.

Required:

- Setup definition
- Entry rule
- Stop rule
- Target or management rule
- Invalidation rule
- No-trade filters
- Backtest metrics

### Gate 2: Backtest Acceptance

Minimum required before paper trading:

- At least 2 years of historical candles where available.
- Spread and slippage simulation.
- Separate in-sample and out-of-sample windows.
- Per-pair and per-setup reporting.
- Max drawdown within configured limit.
- No single trade dominates profitability.

### Gate 3: Paper Trading Acceptance

Minimum required before live-assisted trading:

- 30 trading days minimum.
- Positive or acceptable expectancy after spread and slippage.
- Broker reconciliation works.
- No duplicate orders.
- No missing stop loss events.
- Daily loss kill switch tested.
- Restart recovery tested.

### Gate 4: Live-Assisted Mode

The bot may propose trades, but a human must approve.

Requirements:

- Smallest practical position size.
- Hard daily loss cap.
- Hard weekly loss cap.
- Human approval for each order.
- Automatic stop on reconciliation error.

### Gate 5: Limited Live-Autonomous Mode

The bot may place trades without human approval only after live-assisted mode is stable.

Requirements:

- One or two major pairs only.
- Low risk per trade.
- No high-impact news windows.
- Max one open trade at first.
- Automatic daily shutdown after win/loss threshold.

## First Useful Live Version

The first useful version should not try to trade every setup from the notes.

Start with one narrow setup:

```text
Higher-timeframe supply/demand alignment
+ fresh strong zone
+ candle-close confirmation
+ low/high curve location
+ fixed risk gate
+ OANDA practice execution
```

Only after that works should the bot add SNRC, Hybrid, QML/QMC/QMM, Blindspot, CLAB, and CK confirmations.

