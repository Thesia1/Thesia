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
- Simple demand zone construction
- Opposite structure high removal
- Return to demand zone
- Bullish candle-close confirmation
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
BUY only
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
no broker connection
no live data
no order execution
```

## Partially Implemented

These are represented in code, but simplified:

- Strong zone:
  - Current implementation treats a bullish departure closing above prior structure high as opposite-zone removal.
  - It does not yet model prior supply zones as full objects.

- Fresh zone:
  - Current implementation creates a fresh demand zone.
  - It does not yet scan later candles for full retest counts or invalidation history.

- Candle-close confirmation:
  - Current implementation requires the latest bullish candle to close above the demand zone.
  - It does not yet support PoB engulfing/body-candle confirmation variants.

- Stop loss:
  - Current implementation places stop below the demand zone plus a fixed buffer.
  - It does not yet support danger-zone invalidation from PoB.

- Take profit:
  - Current implementation uses a fixed reward-to-risk target.
  - It does not yet target nearest opposing higher-timeframe zone.

## Documented But Not Yet Implemented

From Echo/Raja:

- Monthly, weekly, daily higher-timeframe sequence
- Multi-timeframe direction alignment
- Supply zones
- Sell-side fresh strong zone continuation
- CP levels
- PCP levels
- Arrival zones
- Inheritance zones
- Flip zones
- Overlap areas
- Trendline break confirmation
- Two opposite-zone removal for direction change
- High curve and low curve range rules
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

1. Add sell-side supply-zone continuation.
2. Add explicit zone freshness, retest, and invalidation tracking.
3. Add high-curve / low-curve classifier.
4. Add higher-timeframe context model.
5. Add nearest opposing zone target selection.
6. Add PoB engulfing/body confirmation.
7. Add danger-zone invalidation.
8. Add trendline break confirmation.
9. Add CP and PCP.
10. Add arrival zones.
11. Add realignment and wow trade.
12. Add PoB setup families.

## Current Verification

Current tests confirm:

- Config live-mode guardrails.
- Model invariants.
- Market data continuity.
- ATR and candle metrics.
- Swing detection.
- `fresh_strong_zone_continuation` fixture creates a trade candidate.
- Generated trade candidate can pass the risk gate.

The current strategy pipeline is real but early.
