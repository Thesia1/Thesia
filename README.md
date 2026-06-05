# Thesia Forex Bot

Thesia is a live-capable, agentic forex trading bot project. The goal is to build a disciplined trading system that can scan markets, identify deterministic supply/demand setups, route candidates through strict risk controls, execute through a broker, reconcile state, and explain its actions.

This project does not promise profits. Forex trading is risky, and live automation must only be enabled after backtesting, paper trading, reconciliation checks, and risk-gate validation.

## Current Status

Implemented:

- Live architecture blueprint
- Detailed implementation plan
- Detailed task plan
- Core risk gate
- Config foundation
- Market data primitives
- Indicator primitives
- Swing detection
- Initial strategy framework
- First fixture-driven strategy pipeline
- OANDA read-only market-data scans
- Split market-data provider and execution provider config
- Deriv MT5 execution-provider scaffold
- Single-pair and multi-pair scan CLI
- Scan market-data provenance output
- Optional scan JSONL logging
- Paper-trade preview through the deterministic risk gate
- Free news fallback and agent fallback scaffolds
- Active opposite-zone object removal for the fresh strong zone strategy
- Monthly/weekly/daily top-down direction gate for broker scans
- Scheduled economic-calendar blackout gate
- Deriv MT5 reconciliation probe for account, positions, orders, margin, symbol metadata, and ticks
- Deriv MT5 guarded order-submission path
- File-backed idempotency ledger for duplicate-order protection

Not implemented yet:

- Backtesting engine
- Persistent paper-trading ledger
- Dashboard
- Fully unattended live daemon / dashboard button loop

## Test

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

## CLI

Run a scan using OANDA read-only market data:

```bash
python3 -m forex_bot scan --pair EUR_USD
```

This uses `MARKET_DATA_PROVIDER=oanda` by default and requires `OANDA_ACCOUNT_ID` and `OANDA_TOKEN` in your shell environment or local `.env`.

Run with a specific market-data provider:

```bash
python3 -m forex_bot scan --pair EUR_USD --market-data-provider oanda
python3 -m forex_bot scan --pair EUR_USD --market-data-provider forex_com
```

FOREX.com support is scaffolded. It will fail clearly until REST API access, app key, and endpoint behavior are confirmed for the account.

The intended current architecture is:

```bash
MARKET_DATA_PROVIDER=oanda
EXECUTION_PROVIDER=mt5
```

OANDA provides read-only candles and pricing. Deriv MT5 is the execution path. MT5 order submission is guarded by strategy, risk, reconciliation, explicit live mode, the order-placement switch, and the idempotency ledger.

Run an OANDA connectivity check:

```bash
python3 -m forex_bot doctor oanda --pair EUR_USD
```

Run a Deriv MT5 execution-readiness check:

```bash
python3 -m forex_bot doctor mt5
```

Run a Deriv MT5 live read-only probe:

```bash
python3 -m forex_bot doctor mt5 --environment live --probe --symbols EUR_USD,GBP_USD,USD_JPY
```

This checks live MT5 terminal, account, open positions, open orders, equity/margin, symbol metadata, and tick visibility. It does not place orders. The probe requires the `MetaTrader5` Python package and access to a Deriv MT5 terminal/session on the machine running the command.

For macOS execution limits and the recommended Windows VPS / execution-bridge setup, see [MT5 Execution On macOS](docs/MT5_MAC_EXECUTION.md).

For Windows Deriv MT5 probe failures such as `(-10005, 'IPC timeout')`, see [Deriv MT5 Windows Troubleshooting](docs/MT5_WINDOWS_TROUBLESHOOTING.md).

For the newly reviewed Session 1-3 strategy pictures and translation notes, see [Strategy Sessions 1-3 Review](docs/STRATEGY_SESSION_REVIEW.md).

Check whether the agent prompt is grounded in the current playbook:

```bash
python3 -m forex_bot doctor agent-playbook
```

Check whether the bot is ready for hands-off autonomous trading:

```bash
python3 -m forex_bot doctor automation-readiness
```

This reports machine-readable playbook coverage, execution readiness, and the agent policy decision. The expected answer is still `ready: false` unless there is also a live strategy candidate, risk approval, verified MT5 reconciliation, and an enabled order-placement path.

Preview the live execution chain without submitting:

```bash
python3 -m forex_bot execute --pair EUR_USD
```

Submit only when all gates are green and live order placement is explicitly enabled:

```bash
THESIA_MODE=AUTONOMOUS_LIVE
THESIA_ENABLE_LIVE=true
EXECUTION_ENVIRONMENT=live
EXECUTION_ENABLE_ORDER_PLACEMENT=true
python3 -m forex_bot execute --pair EUR_USD --submit-live-order
```

The command still returns `BLOCK_EXECUTION` instead of submitting if there is no current strategy candidate, risk is rejected, news blackout is active, MT5 reconciliation fails, or the idempotency ledger has already seen the same decision.

Run a multi-pair scan:

```bash
python3 -m forex_bot scan --pairs EUR_USD,GBP_USD,USD_JPY --count 200
```

Run a scan with optional higher-timeframe confirmation:

```bash
python3 -m forex_bot scan --pair EUR_USD --granularity H1 --higher-timeframe H4 --count 200
```

Write scan records to a JSONL file:

```bash
python3 -m forex_bot scan --pairs EUR_USD,GBP_USD --log-path data/scan-log.jsonl
```

Preview whether a strategy candidate would pass the current paper risk gate:

```bash
python3 -m forex_bot scan --pair EUR_USD --paper-preview
```

`--paper-preview` does not place, submit, or reserve an order. It only applies the deterministic risk gate to the candidate and reports the simulated units, entry, stop, and target when approved.

## News Sources

Trading Economics remains the primary configured economic-calendar/news provider:

```bash
NEWS_PRIMARY_PROVIDER=trading_economics
TRADING_ECONOMICS_API_KEY=your_trading_economics_api_key_here
```

A free market-news fallback can be configured for watch-mode context:

```bash
NEWS_FALLBACK_PROVIDER=alpha_vantage
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here
```

`marketaux` is also supported as a fallback provider with `MARKETAUX_API_KEY`.

Fallback news is not treated as trade approval. Scheduled economic-calendar blackout rules are deterministic and can be fed from a local JSON file:

```bash
NEWS_BLACKOUT_EVENTS_FILE=data/economic-calendar.json
NEWS_BLACKOUT_BEFORE_MINUTES=60
NEWS_BLACKOUT_AFTER_MINUTES=30
NEWS_BLACKOUT_MIN_IMPACT=high
```

Calendar rows must include `title`, `currency`, `impact`, and `starts_at`.

## Agent LLM Fallback

Anthropic remains the primary configured agent provider:

```bash
AGENT_PRIMARY_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

OpenRouter can be configured as the fallback router for agent testing:

```bash
AGENT_FALLBACK_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openrouter/auto
```

The OpenRouter fallback uses the OpenAI-compatible chat completions endpoint. Agent output is for explanations and scenario tests only; it cannot approve risk or place orders.

Run the deterministic fixture smoke test explicitly:

```bash
python3 -m forex_bot scan --pair EUR_USD --source fixture
```

The CLI does not place orders.
