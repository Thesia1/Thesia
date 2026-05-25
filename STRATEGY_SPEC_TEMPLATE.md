# Strategy Spec Template

This file converts the course notes into machine-executable rules.

Each setup must be specified here before it can be traded by the bot.

## Global Rules

### Timeframe Hierarchy

Primary analysis starts from higher timeframe to lower timeframe:

1. Monthly
2. Weekly
3. Daily
4. H4
5. H1
6. Lower entry timeframe, if enabled

Lower timeframes are used for entries only after higher timeframe context is clear.

### Signal States

Every strategy evaluation returns one of:

- `NO_TRADE`
- `WATCH`
- `TRADE_CANDIDATE`

### Trade Directions

- `BUY`
- `SELL`
- `NONE`

### Risk Rule

Fixed lot-size notes are educational only.

The bot uses account-risk sizing:

```text
risk_amount = account_equity * risk_percent
units = risk_amount / (stop_distance_pips * pip_value_per_unit)
```

Default starting risk:

```text
risk_percent = 0.25%
```

The risk gate may reduce size or reject the trade.

## Shared Concepts To Define

These concepts must be encoded before any setup can use them:

### Base Candle

Machine definition needed:

- Max body-to-range ratio
- Max candle range relative to ATR
- Number of consecutive base candles allowed
- Wick handling

### Departure Candle

Machine definition needed:

- Minimum body size relative to base candle
- Minimum candle range relative to ATR
- Required close beyond base range
- Direction-specific rules

### Supply Zone

Machine definition needed:

- Zone high
- Zone low
- Candle source
- Fresh/retested status
- Invalidation condition

### Demand Zone

Machine definition needed:

- Zone high
- Zone low
- Candle source
- Fresh/retested status
- Invalidation condition

### Strong Zone

Machine definition needed:

- What qualifies as removing an opposite zone
- Whether wick break is enough or candle close is required
- Minimum distance beyond opposite zone
- Timeframe relationship

### Weak Zone

Machine definition needed:

- Zone does not remove opposite zone
- Poor location
- Inheritance classification
- Required confirmation

### Trendline Break

Machine definition needed:

- Swing points used to draw trendline
- Minimum number of touches
- Candle close requirement
- Break threshold

### High Curve / Low Curve

Machine definition needed:

- Range anchor method
- 0-25% high-curve sell area
- 0-25% low-curve buy area
- Middle-range no-trade rules

### Danger Zone

Machine definition needed:

- Price level that invalidates a setup
- Whether wick touch invalidates or close invalidates
- How danger zone maps to stop loss

### Confirmation

Machine definition needed:

- Engulfing body rule
- Body candle rule
- Higher-timeframe confirmation rule
- Candle-close requirement
- Trendline/confluence rule

## Setup Spec Format

Use this section for every tradable setup.

```yaml
name:
family:
direction:
market_type:
timeframes:
  context:
  setup:
  entry:
preconditions:
entry_pattern:
confirmation:
invalidation:
stop_loss:
take_profit:
management:
no_trade_filters:
risk_constraints:
backtest_requirements:
paper_trade_requirements:
live_allowed:
```

## Initial Setup: Fresh Strong Zone Continuation

```yaml
name: fresh_strong_zone_continuation
family: supply_demand
direction: BUY_OR_SELL
market_type: continuation
timeframes:
  context: [monthly, weekly, daily]
  setup: [daily, h4]
  entry: [h4, h1]
preconditions:
  - Higher timeframe direction is clear.
  - Price is not in the middle of the curve.
  - Buy setups prefer low curve.
  - Sell setups prefer high curve.
  - Zone is fresh.
  - Zone removed an opposite zone.
entry_pattern:
  - Price returns to the fresh strong zone.
  - Candle-close confirmation is present unless set-and-forget is explicitly enabled.
confirmation:
  - Opposite zone removal confirmed by candle close.
  - Spread is under max spread.
  - No high-impact news blackout.
invalidation:
  - Zone is violated according to configured close-or-wick rule.
  - Price touches danger zone before entry.
stop_loss:
  - Beyond the zone boundary plus buffer.
take_profit:
  - Nearest opposing higher-timeframe zone.
management:
  - Optional stop adjustment only after a new fresh zone forms.
no_trade_filters:
  - Higher timeframe conflict.
  - Middle of curve.
  - Retested zone without confirmation.
  - Spread too high.
  - Stop distance too small or too large.
  - Reward-to-risk below minimum.
risk_constraints:
  - Must pass risk gate.
  - Must use percentage-risk sizing.
backtest_requirements:
  - Minimum 2 years where data is available.
  - Spread and slippage included.
paper_trade_requirements:
  - Minimum 30 trading days.
  - No duplicate orders.
  - No missing stop loss.
live_allowed: false
```

## Setup Backlog

The following setups are not live-eligible until specified and backtested:

- RBR
- DBD
- RBD
- DBR
- CP
- PCP
- Arrival zone
- Inheritance zone
- Flip zone
- Overlap area
- Realignment
- Wow trade
- Hybrid 1
- Hybrid 2
- SNRC1
- SNRC2
- SNRC3
- QML
- QMC
- QMM
- Blindspot 1
- Blindspot 2
- CLAB
- CK1
- CK2
- CK3

