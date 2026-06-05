# Strategy Coverage Review

## Current Answer

The bot is using a narrow executable slice of the Raja/Echo supply-and-demand strategy.

It is not yet using the full Echo, Raja, or PoB documentation as executable trading logic.

## Documentation Sources

Current source documents:

- `Echo Trading Bot.docx`
- `Raja Complete Course Notes(1).pdf`
- `PoB English.pdf`
- `STRATEGY_SPEC_TEMPLATE.md`
- `IMPLEMENTATION_PLAN.md`
- `TASK_PLAN.md`

## Implemented In Code

Implemented strategy file:

- `forex_bot/strategy/fresh_strong_zone.py`

Implemented concepts:

- Base candle detection
- Bullish departure candle detection
- Bearish departure candle detection
- Simple demand zone construction
- Simple supply zone construction
- Active opposing supply-zone object removal
- Active opposing demand-zone object removal
- Return to demand zone
- Return to supply zone
- Bullish candle-close confirmation
- Bearish candle-close confirmation
- Optional single higher-timeframe directional confirmation
- Monthly, weekly, and daily directional alignment gate when broker context is supplied
- Zone freshness tracking before the current return
- Retest count rejection for previously touched zones
- Zone invalidation rejection
- High-curve / low-curve location filter using the documented 0-25% higher-timeframe extremes when higher-timeframe context is supplied
- Nearest opposing zone target selection when it preserves minimum reward
- Scheduled economic-calendar news blackout enforcement
- Deriv MT5 reconciliation diagnostics
- Entry, stop loss, and target construction
- Rule evidence output
- Strategy decision states:
  - `NO_TRADE`
  - `WATCH`
  - `TRADE_CANDIDATE`
- Risk-gate integration in tests

Current executable setup:

```text
fresh_strong_zone_continuation
```

Current direction:

```text
BUY and SELL
```

Current data sources:

```text
configured broker provider read-only market data by default
OANDA read-only adapter implemented first
FOREX.com adapter scaffolded, not fully implemented yet
local fixture candles only when --source fixture is passed
```

Current broker status:

```text
OANDA read-only market data implemented
FOREX.com scaffolded only
Deriv MT5 reconciliation probe implemented
Deriv MT5 guarded order submission implemented
file-backed idempotency ledger implemented
```

## Partially Implemented

These are represented in code, but simplified:

- Strong zone:
  - Current implementation requires a bullish departure to close above an active prior supply-zone object, or a bearish departure to close below an active prior demand-zone object.
  - If no active opposing zone object exists in the lookback, the setup fails closed.

- Fresh zone:
  - Current implementation creates a fresh demand or supply zone.
  - It now rejects zones that were retested or invalidated before the current return.

- Candle-close confirmation:
  - Current implementation requires the latest bullish candle to close above a demand zone or the latest bearish candle to close below a supply zone.
  - It does not yet support PoB engulfing/body-candle confirmation variants.

- Stop loss:
  - Current implementation places stop below the demand zone plus a fixed buffer.
  - It does not yet support danger-zone invalidation from PoB.

- Take profit:
  - Current implementation uses the nearest opposing zone target when it still preserves minimum reward.
  - If no usable opposing zone is found, it falls back to the fixed reward-to-risk target.

- High/low curve:
  - Current implementation follows the Echo strategy_docs rule that the 0-25% area near the low curve is mainly for buyers, and the 0-25% area near the high curve is mainly for sellers.
  - Monthly, weekly, and daily direction are now first-class strategy inputs for broker scans.
  - The full nested monthly/weekly/daily curve hierarchy remains a future refinement.

- News blackout:
  - Current implementation blocks trades around configured scheduled economic-calendar events that match either currency in the pair and meet the configured impact threshold.
  - The gate is deterministic and file-backed until a full calendar API adapter is wired.

- Deriv MT5 reconciliation:
  - Current implementation verifies MT5 account info, positions, open orders, equity, margin, symbol metadata, and ticks through the terminal probe.
  - Order submission is available only after deterministic strategy, risk, reconciliation, explicit live mode, order-placement switch, and idempotency checks pass.

## Documented But Not Yet Implemented

From Echo/Raja:

- CP levels
- PCP levels
- Arrival zones
- Inheritance zones
- Flip zones
- Overlap areas
- Trendline break confirmation
- Two opposite-zone removal for direction change
- Full nested high/low curve range model across the monthly/weekly/daily sequence
- Middle-of-curve no-trade filter
- Realignment
- Wow trade
- Impulsive vs corrective move classification
- Momentum and location alignment
- Retested-zone confirmation rules
- Set-and-forget rules
- Stop adjustment with new fresh zones

From PoB:

- RBR
- DBD
- RBD
- DBR
- SNRC1
- SNRC2
- SNRC3
- Hybrid 1
- Hybrid 2
- QML
- QMC
- QM2P
- QMM
- Blindspot 1
- Blindspot 2
- Manipulation
- CLAB
- CK1
- CK2
- CK3
- Engulfing confirmation
- Body candle confirmation
- Danger zone invalidation
- Strong support/resistance confirmation
- Trendline/confluence confirmation

## Why The Bot Is Not Yet Using The Full Docs

The source documents are teaching material. The bot needs deterministic rules before a concept can trade.

For each concept, we still need:

- exact candle rules
- exact timeframe relationship
- exact zone boundaries
- exact confirmation rule
- exact invalidation rule
- exact entry rule
- exact stop rule
- exact target or management rule
- tests
- backtest report
- paper-trading report

## Next Strategy Translation Tasks

Priority order:

1. Add PoB engulfing/body confirmation.
2. Add danger-zone invalidation.
3. Add trendline break confirmation.
4. Add CP and PCP.
5. Add arrival zones.
6. Add realignment and wow trade.
7. Add PoB setup families.
8. Add persistent paper-trading ledger.
9. Add full backtesting reports.
10. Add live daemon / dashboard button loop.

## Current Verification

Current tests confirm:

- Config live-mode guardrails.
- Model invariants.
- Market data continuity.
- ATR and candle metrics.
- Swing detection.
- `fresh_strong_zone_continuation` fixture creates a trade candidate.
- Generated trade candidate can pass the risk gate.
- Opposing zone object removal.
- Monthly/weekly/daily alignment.
- Scheduled economic-calendar blackout.
- Deriv MT5 reconciliation diagnostics.
- Deriv MT5 guarded order-submission path.
- Duplicate-order idempotency ledger.

The current strategy pipeline is real but early.
