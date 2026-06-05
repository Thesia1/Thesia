# Deriv MT5 Windows Troubleshooting

This project uses OANDA for read-only market data and Deriv MT5 for order execution. Live order submission requires both a valid strategy/risk decision and a reconciled Deriv MT5 terminal session.

## `(-10003, "IPC initialize failed, Process create failed ...")`

This error means Python tried to start the configured MT5 terminal executable, but Windows could not find or launch it. If the probe reports `"mt5_path_exists": false`, the configured `MT5_PATH` is wrong for that machine.

Find the real path on Windows:

1. Open the Start menu and search for Deriv MT5.
2. Right-click the Deriv MT5 app and choose `Open file location`.
3. Right-click the Deriv MT5 shortcut and choose `Properties`.
4. Copy the `Target` path.
5. Use that exact path for `MT5_PATH`.

Common locations include:

```dotenv
MT5_PATH=C:\Program Files\Deriv MT5\terminal64.exe
MT5_PATH=C:\Program Files (x86)\Deriv MT5\terminal64.exe
MT5_PATH=C:\Users\YourWindowsUser\AppData\Roaming\MetaQuotes\Terminal\...\terminal64.exe
```

After updating `.env`, rerun:

```powershell
py -m forex_bot doctor mt5 --environment live --probe --symbols EUR_USD
```

## `(-10005, 'IPC timeout')`

This error means the MetaTrader5 Python bridge could not establish local IPC communication with the MT5 terminal before the timeout. It is a terminal-connection problem, not a strategy approval.

Check these items on the Windows machine running the bot:

1. Open Deriv MT5 manually before running the bot.
2. Confirm the correct live Deriv MT5 account is logged in inside the terminal.
3. Close first-run prompts, update dialogs, login popups, or modal windows inside MT5.
4. Set `MT5_PATH` to the exact `terminal64.exe` for the Deriv MT5 terminal.
5. Run PowerShell and Deriv MT5 as the same Windows user and privilege level.
6. Confirm the bot is using a 64-bit Python where `py -m pip show MetaTrader5` succeeds.
7. Increase `MT5_TIMEOUT_MS` if the terminal is slow to start or the Windows laptop is under load.
8. Restart Deriv MT5 and rerun the probe.

Example `.env` values:

```dotenv
EXECUTION_PROVIDER=mt5
EXECUTION_ENVIRONMENT=live
MT5_LOGIN=12345678
MT5_PASSWORD=your_deriv_mt5_password
MT5_SERVER=Deriv-Server-Name-From-Terminal
MT5_PATH=C:\Program Files\Deriv MT5\terminal64.exe
MT5_TIMEOUT_MS=60000
EXECUTION_ENABLE_ORDER_PLACEMENT=false
```

Probe command:

```powershell
py -m forex_bot doctor mt5 --environment live --probe --symbols EUR_USD
```

Expected healthy probe shape with order placement still disabled:

```json
{
  "terminal_connected": true,
  "account_info_visible": true,
  "positions_visible": true,
  "orders_visible": true,
  "ticks_visible": true,
  "symbol_info_visible": true,
  "reconciliation_ok": true,
  "can_place_orders": false
}
```

`can_place_orders` should remain `false` until `EXECUTION_ENABLE_ORDER_PLACEMENT=true` is intentionally enabled.

## Why Execution Can Still Block After MT5 Works

The execution command will still return `BLOCK_EXECUTION` when any deterministic gate fails:

- No current strategy trade candidate.
- Risk approval is missing or rejected.
- News blackout is active.
- MT5 reconciliation is not verified.
- Order placement is disabled.
- The idempotency ledger has already seen the same strategy decision.

For example, if the H1 setup is bearish but weekly and daily context are opposed, the strategy state should remain `NO_TRADE`. In that case the bot must not place a live order even when Deriv MT5 is connected.
