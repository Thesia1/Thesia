# Work Log

## 2026-05-25

### Step 1: Project Baseline

Work completed:

- Added `README.md` with project purpose, safety warning, current status, test command, and CLI command.
- Added `pyproject.toml` so the package has a clear Python project identity.

Review:

- This makes the project easier to run and hand off. The README deliberately states that live execution is not implemented yet, which prevents accidental overconfidence.

### Step 2: Configuration and Domain Models

Work completed:

- Added environment-backed config objects.
- Expanded domain models to include candles, prices, spreads, zones, strategy decisions, order intents, broker orders, positions, audit records, and mode changes.

Review:

- These models define the bot's internal language. They are intentionally strict around trade candidates and order intents because live trading must be traceable.

### Step 3: Market Data and Indicators

Work completed:

- Added candle sorting and continuity checks.
- Added ATR and candle metric helpers.
- Added swing high/low detection with a live-safe confirmation delay.

Review:

- These primitives are deliberately dependency-free. They give us a deterministic base for supply/demand detection without hiding behavior inside a third-party strategy package.

### Step 4: Strategy Framework and First Detector

Work completed:

- Added a strategy result framework.
- Added base/departure candle detection.
- Added simple supply/demand zone construction.
- Added a first `fresh_strong_zone_continuation` detector that can produce `NO_TRADE`, `WATCH`, or `TRADE_CANDIDATE`.

Review:

- The detector is intentionally conservative and fixture-driven. It is not yet a full Raja/PoB implementation, but it creates the correct pipeline shape: rules produce evidence, evidence produces a candidate, and the candidate can be passed to risk.

### Step 5: CLI and Tests

Work completed:

- Added a fixture-backed CLI command: `python3 -m forex_bot scan --pair EUR_USD`.
- Added tests for config, models, market data, indicators, and strategy behavior.

Review:

- The CLI is not connected to OANDA yet. That is by design: the first sprint proves the local decision pipeline before broker code exists.

