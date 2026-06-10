# Demand In Sequence Visual Rules

Purpose:

Translate the demand-in-sequence chart examples into deterministic bot rules and a future computer-vision labeling format.

## Valid Buy Sequence

A valid demand-in-sequence buy requires all of the following:

- Market direction is bullish.
- Price forms higher highs and higher lows.
- An ascending trendline is drawn through or near major higher lows.
- A fresh demand zone is created by a base or small consolidation before a strong bullish impulse.
- The demand zone is close to the ascending trendline at the pullback/confluence area.
- Price moves away from the demand zone with strength.
- Price later pulls back toward the same fresh demand zone.
- The pullback approaches the ascending trendline.
- Entry triggers when live price touches or nearly touches the demand zone and trendline area together.
- The best entry is the first touch of the fresh demand zone.

## Rejection Rules

Reject the setup when any of these are true:

- Demand zone is far from the ascending trendline at the pullback.
- Trendline does not connect clear higher lows.
- Higher highs and higher lows are not present.
- Demand zone has already been tested multiple times.
- Market is ranging or bearish.
- Price breaks strongly below the trendline and demand zone before entry.
- Demand zone is created by weak or choppy price action.
- No strong bullish impulse leaves the base.

## Entry, Stop, And Target

- Entry: buy immediately when price touches the valid demand-zone/trendline confluence.
- Optional future entry type: buy limit inside the demand zone before return.
- Stop loss: below the demand zone.
- Take profit: next swing high, next supply zone, or previous resistance area.

## Visual Labeling Output

Use this schema when labeling chart screenshots for future computer-vision training:

```text
Pair/Timeframe:
Trend: Bullish / Bearish / Ranging
Demand Zone Found: Yes/No
Ascending Trendline Found: Yes/No
Demand Close to Trendline: Yes/No
Fresh Zone: Yes/No
Entry Area:
Stop Loss:
Take Profit:
Setup Quality: Strong / Medium / Weak
Valid Trade: Yes/No
Confidence Score:
Reason: Trade Entry Rule
```

Execution-focused output:

```text
Valid Demand-in-Sequence Setup: Yes/No
Demand Zone Close to Ascending Trendline: Yes/No
Entry Trigger: Price touched demand zone
Trade Action: Buy immediately
Entry Price:
Stop Loss: Below demand zone
Take Profit: Next swing high / supply zone
```

## Current Bot Translation

The first deterministic implementation is `trendline_zone_sequence`.

For demand-in-sequence, it now checks:

- Higher lows and higher highs before the return.
- Ascending trendline from the latest major higher lows before the demand zone.
- Fresh demand zone from a base plus strong bullish impulse.
- Current pullback touches the demand zone.
- Current pullback is close to the ascending trendline.
- The zone is first-touch/untested before the current return.
- Stop below demand zone and latest swing low buffer.
- Initial target uses fixed minimum reward-to-risk until opposing-zone target selection is added to this strategy.
