# Strategy Sessions 1-3 Review

## Sources Reviewed

- `strategy_docs/Session 1_Basics.pdf`
- `strategy_docs/Session 2.pdf`
- `strategy_docs/Session 3_ Trendline & High and Low Curve (1).pdf`

The PDFs contain both text notes and embedded chart images. Text was extracted with the bundled PDF runtime, and embedded images were extracted for visual review.

## Session 1: Basics

Key concepts:

- Supply and demand zones use proximal lines for entries and distal lines for stops.
- Higher timeframes create retracements, while lower timeframes show trending channels.
- The base should be drawn from the 50% candle or similar base candle area.
- Simple supply/demand examples are valley and peak structures.
- Advanced structures include CP and PCP levels.
- CP levels are visible on smaller timeframes.
- Use a maximum of 3 CP levels; a fourth CP level is documented as weak.
- PCP levels form after the opposing zone has been removed.
- Gaps are clues; the documented trade location is the zone before the gap.
- Base quality matters: 1-6 candles are acceptable for the base, with 50% candles, hammer candles, doji, and marubozu mentioned. Doji is marked dangerous.
- Stairs zones are bad zones.
- Fresh and original zones can support limit orders.
- Retested zones need more confirmation and become dangerous after repeated touches.
- Original zones are similar to fresh zones but have no prior zones causing the impulse.

Agent interpretation:

- The agent should treat fresh and original zones as higher-quality contexts.
- The agent should treat retested, stairs, doji-heavy, and fourth-CP contexts as cautionary unless deterministic code approves them.
- The agent must not invent CP/PCP entries until detectors exist.

## Session 2: Strong Zones And Confirmation

Key concepts:

- A strong zone is a zone that removes the opposite zone.
- Monthly zones can use limit orders when two strong zones oppose each other.
- Around the third touch of a monthly zone, confirmation is required on the 4H timeframe.
- Weekly and daily zones require confirmation around the second touch; daily is marked risky.
- 4H confirmation requires removing the opposing zone and waiting for CP levels that also remove opposite levels.
- Inheritance zones describe weakness between zone 1 and zone 2 when later zones fail to hold.
- Flip zones are retracement/support-resistance style areas where CP levels can form entries.
- Trend direction changes when a trendline breaks and two opposite zones are removed.
- Market movement is described as moving between monthly supply and demand.

Agent interpretation:

- The current executable strategy only implements the strong-zone removal slice.
- Touch-count confirmation, inheritance zones, flip zones, and CP confirmation are documented context only until deterministic detectors are added.
- If a setup depends on a third-touch monthly or second-touch weekly/daily confirmation, the agent should describe it as not executable yet unless code evidence exists.

## Session 3: Trendline And High/Low Curve

Key concepts:

- Higher timeframes use strong monthly zones.
- Lower timeframes use CP levels for entries.
- A trendline is drawn from the last two swing highs or lows.
- Trend change requires trendline break plus opposing-zone removal.
- Market moves between last monthly supply and demand areas.
- The middle between monthly supply and demand is 50%.
- The 0-25% area near monthly supply is seller area.
- The 0-25% area near monthly demand is buyer area.
- Buying is not allowed in the seller area; selling is not allowed in the buyer area.
- Examples show monthly demand as low-curve area and monthly supply as high-curve area.

Agent interpretation:

- The current strategy implements a simplified 0-25% high/low curve filter.
- The full nested monthly supply/demand curve model is not complete.
- Trendline break and trend-change logic are not executable yet.

## User Chart Addendum: Supply And Demand In Sequence

Key concept:

- A supply zone below a descending trendline is a preferred bearish continuation context.
- The first chart shows the expected trade idea: market is anticipated to reject/drop from the supply in sequence.
- The second chart shows the completed behavior: market dropped from that supply in sequence and continued lower.
- The visual confluence is supply-in-sequence plus descending trendline pressure.
- A demand zone above an ascending trendline is a preferred bullish continuation context.
- When price returns to an untested demand zone near the ascending trendline, the documented action is an immediate buy candidate.
- The same first-touch and trendline-nearness rules apply to supply in sequence and demand in sequence.

Agent interpretation:

- The agent should remember this as bullish and bearish playbook context.
- The first deterministic implementation is `trendline_zone_sequence`.
- `trendline_zone_sequence` can produce immediate candidates on first touch of an untested zone near the correct trendline; risk, spread, broker reconciliation, live-mode, and idempotency gates still control execution.
- The current implementation uses a simplified two-swing trendline and fixed 2R first target; full multi-timeframe challenge-management rules remain future work.

## Current Translation Status

Implemented or partially implemented:

- Strong zone as active opposing zone removal.
- Fresh-zone lifecycle and retest rejection.
- 0-25% high/low curve filter.
- Monthly/weekly/daily direction context.
- Nearest opposing zone target.
- Trendline-zone sequence first-touch entries.
- Risk gate and execution policy.

Still needs deterministic detectors:

- Proximal/distal evidence output.
- 1-6 candle base grouping.
- Doji/hammer/marubozu base quality scoring.
- CP levels.
- PCP levels.
- Gap-before-zone setup.
- Stairs-zone rejection.
- Original-zone classification.
- Touch-count confirmation rules.
- Inheritance-zone classification.
- Flip-zone classification.
- Full visual trendline management beyond the first two-swing trendline-zone sequence detector.
- Trend-change confirmation with trendline break and two opposite-zone removals.
- Full monthly supply/demand nested curve model.

## Rule For The Agent

The agent may use these session concepts to explain why a setup is promising, risky, or incomplete. It must not describe any concept as executable unless the deterministic strategy evidence includes that rule.
