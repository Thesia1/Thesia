# Supply In Sequence Visual Rules

Purpose:

Translate the supply-in-sequence chart examples into deterministic bot rules and a future computer-vision labeling format.

## Valid Sell Sequence

A valid supply-in-sequence sell requires all of the following:

- Market direction is bearish.
- Price forms lower highs and lower lows.
- A descending trendline is drawn through or near major lower highs.
- A fresh supply zone is created by a base or small consolidation before a strong bearish impulse.
- The supply zone is close to the descending trendline at the pullback/confluence area.
- Price moves away from the supply zone with strong bearish momentum.
- Price later pulls back toward the same fresh supply zone.
- The pullback approaches the descending trendline.
- Entry triggers when live price touches or nearly touches the supply zone and trendline area together.
- The best entry is the first touch of the fresh supply zone.

## Rejection Rules

Reject the setup when any of these are true:

- Supply zone is far from the descending trendline at the pullback.
- Trendline does not connect clear lower highs.
- Lower highs and lower lows are not present.
- Supply zone has already been tested multiple times.
- Market is ranging or bullish.
- Price breaks strongly above the trendline before touching supply.
- Price breaks through the supply zone with strong bullish candles.
- Supply zone is created by weak or choppy price action.
- No strong bearish impulse leaves the base.
- Stop-loss or take-profit geometry is unclear or reward-to-risk is poor.

## Entry, Stop, And Target

- Instant market entry: sell immediately when live price touches the valid supply-zone/trendline confluence.
- Optional future entry type: sell limit inside the fresh supply zone before return.
- Stop loss: above the supply zone or above the most recent swing high.
- Take profit: next swing low, next demand zone, previous support area, or minimum 1:2 reward-to-risk target.

## Visual Labeling Output

Use this schema when labeling chart screenshots for future computer-vision training:

```text
Pair/Timeframe:
Trend: Bearish / Bullish / Ranging
Lower Highs Found: Yes/No
Lower Lows Found: Yes/No
Descending Trendline Found: Yes/No
Fresh Supply Zone Found: Yes/No
Supply Close to Descending Trendline: Yes/No
Price Touching Supply Zone: Yes/No
Entry Trigger: Sell on touch / Sell limit waiting / No trade
Trade Action: Sell / Wait / Reject
Entry Price:
Stop Loss: Above supply zone
Take Profit: Next swing low / demand zone / support
Setup Quality: Strong / Medium / Weak / Invalid
Confidence Score: 0-100
Reason:
```

## Confidence Guide

- 90-100: clear downtrend, lower highs/lows, clean descending trendline, fresh supply zone close to the trendline, strong bearish departure, first touch.
- 75-89: strong setup with one minor imperfection, such as a slightly messy pullback.
- 60-74: possible but not clean.
- 40-59: weak and should not be automated.
- 0-39: invalid setup.

## Current Bot Translation

The first deterministic implementation is `trendline_zone_sequence`.

For supply-in-sequence, it now checks:

- Lower highs and lower lows before the supply-zone return.
- Descending trendline from the latest major lower highs before the zone.
- Fresh supply zone from a base plus strong bearish impulse.
- Current pullback touches the supply zone.
- Current pullback is close to the descending trendline.
- The zone is first-touch/untested before the current return.
- Stop above supply zone and latest swing high buffer.
- Initial target uses fixed minimum reward-to-risk until opposing-zone target selection is added to this strategy.

