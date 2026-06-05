# MT5 Execution On macOS

## Summary

The bot can scan and make deterministic trade decisions on macOS, but Deriv MT5 live execution cannot be completed with native macOS Python in the current architecture.

The bottleneck is the official `MetaTrader5` Python package. It is distributed as Windows builds and is designed to communicate with a running MetaTrader 5 terminal. On macOS, the bot can still use OANDA market data, evaluate the playbook, run risk checks, and prepare the order request, but the actual MT5 `order_send` call must run where the MT5 Python bridge and Deriv MT5 terminal are available.

## Current Bottlenecks

- No trade candidate means no order should be created.
- Risk approval cannot exist until the strategy returns `TRADE_CANDIDATE`.
- Native macOS Python cannot import the official `MetaTrader5` package.
- Deriv MT5 reconciliation cannot pass unless the terminal account, positions, open orders, margin, symbol metadata, and ticks are visible.
- Live order placement remains blocked unless `THESIA_MODE=AUTONOMOUS_LIVE`, `THESIA_ENABLE_LIVE=true`, `EXECUTION_ENVIRONMENT=live`, and `EXECUTION_ENABLE_ORDER_PLACEMENT=true`.
- A scheduled economic-calendar blackout file should be configured before serious live automation.

## Recommended Architecture

Use macOS as the command center and run execution on a Windows machine or Windows VPS.

```text
macOS / Thesia command center
  - strategy scans
  - playbook/risk review
  - monitoring and logs
  - sends approved execution request

Windows VPS / Deriv MT5 executor
  - Deriv MT5 terminal installed and logged in
  - Windows Python with MetaTrader5 package
  - MT5 reconciliation probe
  - guarded order_send
  - idempotency ledger
```

This gives us the best blend of usability and execution reliability: the user can operate from the Mac, while the supported MT5 bridge runs on Windows.

## Viable Options

### Option 1: Windows VPS

This is the preferred live path.

Requirements:

- Windows VPS.
- Deriv MT5 terminal installed.
- Deriv MT5 account logged in.
- Python installed on Windows.
- `MetaTrader5` Python package installed.
- This repository deployed on the VPS.

Validation:

```bash
python -m pip install MetaTrader5
python -m forex_bot doctor mt5 --environment live --probe --symbols EUR_USD
```

Only continue when the output shows:

```text
reconciliation_ok: true
can_place_orders: true
```

### Option 2: Mac Command Center + Windows Execution Bridge

This is the preferred product architecture if the Mac should remain the main control surface.

Flow:

- The Mac runs the scan, strategy, risk, and agent policy.
- The Mac sends a signed approved order request to the Windows executor.
- The Windows executor verifies idempotency and MT5 reconciliation again.
- The Windows executor submits through MT5.
- The Windows executor returns the broker order result to the Mac.

Important rule:

The Windows executor must repeat safety checks. It should not trust a raw Mac request without validating idempotency, symbol, volume, stop loss, take profit, and MT5 account state.

### Option 3: Windows VM On Mac

This can work, but it is less clean than a VPS.

Use this only if:

- The VM can run Deriv MT5 reliably.
- Windows Python can install `MetaTrader5`.
- Network and terminal uptime are stable.

For live trading, a VPS is usually safer than a laptop VM because the VPS is less likely to sleep, disconnect, or be interrupted.

### Option 4: Wine/Crossover

This is not recommended for live execution.

Wine-based setups can be useful for experimentation, but they add terminal, Python, IPC, and architecture instability. For live funds, the executor should run in a supported Windows environment.

### Option 5: Replace Deriv MT5 Execution With Another Broker API

OANDA API execution would avoid the MT5 Python limitation, but it changes the execution venue from Deriv MT5 to OANDA.

Deriv's public API is useful for Deriv account and contract-style trading workflows, but it is not a drop-in replacement for Deriv MT5 CFD order execution through the MT5 terminal.

## Live Execution Checklist

Before running a real submission:

- OANDA market-data credentials work.
- Deriv MT5 credentials are configured on Windows/VPS.
- Deriv MT5 terminal is installed and logged in.
- `python -m forex_bot doctor mt5 --environment live --probe --symbols EUR_USD` returns `reconciliation_ok: true`.
- `THESIA_MODE=AUTONOMOUS_LIVE`.
- `THESIA_ENABLE_LIVE=true`.
- `EXECUTION_ENVIRONMENT=live`.
- `EXECUTION_ENABLE_ORDER_PLACEMENT=true`.
- `EXECUTION_IDEMPOTENCY_LEDGER_PATH` points to durable storage.
- News blackout file is configured.
- `python -m forex_bot execute --pair EUR_USD` returns ready without submitting.

Only then use:

```bash
python -m forex_bot execute --pair EUR_USD --submit-live-order
```

The bot must still refuse to trade if there is no current strategy candidate.
