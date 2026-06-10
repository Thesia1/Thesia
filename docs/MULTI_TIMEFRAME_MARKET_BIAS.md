# Multi-Timeframe Market Bias Layer

## Purpose

This layer translates the requested top-down market-structure workflow into deterministic scan output.

It does not create trades by itself. It gives the bot a structured big-picture read so strategy candidates can be accepted, rejected, or left as wait states with clearer reasons.

## Timeframe Hierarchy

The scan report now reads:

- Monthly: major direction and broad pressure.
- Weekly: confirmation or challenge to monthly direction.
- Daily: active trading direction.
- H4: trade-idea refinement when H4 candles are supplied.
- Current scan timeframe: entry timing only.

Lower timeframes cannot override Monthly/Weekly/Daily unless the higher-timeframe context is incomplete and the report is clearly marked short-term.

## Classifications

The report can classify the asset as:

- `Long-Term Buy`
- `Short-Term Buy`
- `Long-Term Sell`
- `Short-Term Sell`
- `No Trade / Wait`

The final action field is intentionally simpler:

- `Buy`
- `Sell`
- `Wait`
- `Reject setup`

## Deterministic Bias Rules

For each timeframe, the bot first looks for confirmed swing structure:

- Bullish: higher highs and higher lows.
- Bearish: lower highs and lower lows.
- Ranging: mixed or unclear swings.

When there are not enough clean swings, the bot falls back to rising or falling closes with a lower confidence score.

If fewer than two of Monthly/Weekly/Daily have actionable context, the top-down layer says `No Trade / Wait`.

If Monthly/Weekly/Daily are aligned:

- all bullish -> `Long-Term Buy`
- all bearish -> `Long-Term Sell`

If two higher timeframes lean one way with no direct opposition:

- bullish lean -> `Short-Term Buy`
- bearish lean -> `Short-Term Sell`

If Monthly/Weekly/Daily conflict, the output is `No Trade / Wait`.

## Candidate Gate

The market-bias layer can block an existing deterministic strategy candidate only when enough higher-timeframe context exists and the candidate conflicts with that context.

Examples:

- A BUY candidate with strong Monthly/Weekly/Daily bearish context is rejected.
- A SELL candidate with strong Monthly/Weekly/Daily bullish context is rejected.
- Missing higher-timeframe data does not create a rejection by itself.

This is a safety filter, not a signal generator.

## Scan Output Fields

Every scan now includes `market_bias` with:

- `pair_asset`
- `monthly_bias`
- `weekly_bias`
- `daily_bias`
- `h4_bias`
- `lower_timeframe_entry_bias`
- `overall_market_direction`
- `trade_classification`
- `supply_demand_setup_found`
- `trendline_setup_found`
- `book_based_insight_applied`
- `entry_type`
- `entry_area`
- `stop_loss`
- `take_profit`
- `setup_quality`
- `confidence_score`
- `final_decision`
- `candidate_conflict`
- `reason`

## Practical Command

For forex testing, use H4 as the supplied refinement timeframe:

```bash
python -m forex_bot scan --pairs GBPUSD,EURUSD,USDJPY,XAUUSD,GBPJPY,AUDUSD,USDCAD,USDCHF,EURJPY --granularity H1 --higher-timeframe H4 --paper-preview --show-all-strategies
```

For one autotrade cycle:

```bash
python -m forex_bot autotrade --pairs GBPUSD,EURUSD,USDJPY,XAUUSD,GBPJPY,AUDUSD,USDCAD,USDCHF,EURJPY --granularity H1 --higher-timeframe H4 --show-all-strategies
```

The bot still needs a deterministic strategy candidate, risk approval, MT5 reconciliation, live mode, order-placement enablement, and idempotency approval before any live order can be submitted.
