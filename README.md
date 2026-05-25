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
- CLI scan stub

Not implemented yet:

- Real broker connectivity
- Backtesting engine
- Paper trading execution
- Dashboard
- Live autonomous execution

## Test

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

## CLI

Run a scan using OANDA read-only market data:

```bash
python3 -m forex_bot scan --pair EUR_USD
```

This uses `BROKER_PROVIDER=oanda` by default and requires `OANDA_ACCOUNT_ID` and `OANDA_TOKEN` in your shell environment or local `.env`.

Run with a specific provider:

```bash
python3 -m forex_bot scan --pair EUR_USD --broker-provider oanda
python3 -m forex_bot scan --pair EUR_USD --broker-provider forex_com
```

FOREX.com support is scaffolded. It will fail clearly until REST API access, app key, and endpoint behavior are confirmed for the account.

Run the deterministic fixture smoke test explicitly:

```bash
python3 -m forex_bot scan --pair EUR_USD --source fixture
```

The CLI does not place orders.
