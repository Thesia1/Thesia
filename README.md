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

Run the current fixture-backed scan:

```bash
python3 -m forex_bot scan --pair EUR_USD
```

The CLI currently uses local fixture data. It does not connect to a broker or place orders.

