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

### Step 6: Remove Accidental Fixture Default

Work completed:

- Changed the default `scan` command from fixture data to OANDA read-only market data.
- Kept fixture scans available only through `--source fixture`.
- Added `.env` file loading so local credentials do not need to be exported manually.
- Added an OANDA read-only adapter for candles and current spread.
- Added tests for OANDA response parsing and CLI pair normalization.

Review:

- This fixes the hardcoded-output problem. The default scan now either uses OANDA credentials or returns a clear configuration error. Fixture output is still useful for development, but it has to be requested explicitly.

### Step 7: Multi-Broker Provider Scaffold

Work completed:

- Added a shared broker interface.
- Added `BROKER_PROVIDER` config support.
- Kept OANDA as the first read-only implementation.
- Added a FOREX.com scaffold adapter that fails clearly until REST API access is confirmed.
- Added tests for the broker factory and FOREX.com scaffold behavior.

Review:

- This lets the bot support both OANDA and FOREX.com without making the strategy engine broker-specific. FOREX.com is not implemented as a working data adapter yet; it is safely scaffolded so we can add it once account API credentials, app key, and endpoint docs are available.

### Step 8: Free News Fallback Scaffold

Work completed:

- Added news-provider configuration while keeping Trading Economics as the primary source.
- Added Alpha Vantage and Marketaux as free market-news fallback adapters.
- Added a fallback wrapper that records when fallback data was used.
- Added tests for provider config, fallback behavior, and missing fallback credentials.

Review:

- The fallback is intentionally read-only market context. It does not approve trades or replace official scheduled economic-calendar blackout logic.

### Step 9: Agent LLM Fallback Scaffold

Work completed:

- Added agent-provider configuration while keeping Anthropic as the primary provider.
- Added OpenRouter as a fallback router for agent testing.
- Added an OpenRouter chat-completions adapter using the `openrouter/auto` router model by default.
- Added tests for provider config, fallback behavior, and missing fallback credentials.

Review:

- The fallback is intentionally limited to explanation/scenario-test output. It does not add tool execution, risk approval, or broker order capability.

### Step 10: Real Testing Readiness Layer

Work completed:

- Added richer structure evidence for the fresh strong zone strategy, including the exact prior structure high or low tested by the departure candle.
- Added sell-side supply-zone continuation detection.
- Added optional higher-timeframe directional confirmation.
- Added multi-pair scan support through `--pairs`.
- Added JSONL scan logging through `--log-path`.
- Added `--paper-preview`, which runs candidates through the deterministic risk gate and reports simulated units without creating broker orders.
- Added tests for sell-side strategy behavior, higher-timeframe rejection, batch scans, paper preview, and scan-log persistence.

Review:

- This makes real read-only OANDA testing feasible and much easier to audit. It still deliberately avoids broker order placement, broker reconciliation, and persistent paper-ledger accounting. The next safe step is collecting scan logs across live market sessions before implementing any order-writing path.

### Step 11: OANDA Market Data + Deriv MT5 Execution Architecture

Work completed:

- Split provider configuration into explicit market-data and execution roles.
- Added `MARKET_DATA_PROVIDER` / `MARKET_DATA_ENVIRONMENT` while keeping legacy `BROKER_PROVIDER` / `BROKER_ENVIRONMENT` as compatibility aliases.
- Added `EXECUTION_PROVIDER` / `EXECUTION_ENVIRONMENT`.
- Added an MT5 execution-provider scaffold for Deriv MT5 credentials.
- Added `python3 -m forex_bot doctor mt5` to report whether MT5 credentials are configured.
- Added execution status to broker-backed scan output.
- Added tests for OANDA market data plus MT5 execution config and safe MT5 diagnostics.

Review:

- This fixes the account-model confusion: OANDA API credentials are now only for market data, while Deriv MT5 credentials belong to the execution path. The MT5 adapter still fails closed and cannot place orders until the execution engine, reconciliation, duplicate-order protection, and paper ledger exist.

### Step 12: Deriv MT5 Live Read-Only Probe and Agent Playbook Grounding

Work completed:

- Added optional Deriv MT5 live read-only probing through `python3 -m forex_bot doctor mt5 --environment live --probe`.
- The MT5 probe checks terminal initialization, account info, open-position visibility, and optional symbol ticks without calling order APIs.
- Added safe probe output for missing `MetaTrader5` Python package or unavailable terminal bridge.
- Added an agent playbook contract that explicitly describes the OANDA market-data role, Deriv MT5 execution role, strategy rules, risk-gate boundary, and no-order limitations.
- Added `python3 -m forex_bot doctor agent-playbook`.
- Added tests for MT5 live probe outcomes and agent playbook grounding.

Review:

- This supports live Deriv MT5 testing only as a read-only readiness check. It still cannot place orders. The agent pipeline now has a formal playbook grounding prompt, but deterministic strategy and risk code remain the trusted decision path.

### Step 13: Machine-Readable Playbook Coverage and Autonomy Policy

Work completed:

- Added a machine-readable playbook coverage report that separates implemented, partial, missing, required, and optional documented strategy concepts.
- Added an agent autonomy policy that blocks execution unless mode, playbook coverage, deterministic strategy decision, risk approval, execution readiness, and broker-state verification all pass.
- Added `python3 -m forex_bot doctor automation-readiness`.
- Wired the playbook coverage summary into the agent playbook prompt.
- Added tests for playbook coverage and the future allowed/blocked autonomy policy states.

Review:

- This moves the project closer to the real goal: autonomous trading without manual help. The current answer is intentionally still `ready: false`, but now the blockers are explicit and testable instead of vague.

### Step 14: Strategy Translation Pass

Work completed:

- Added deterministic zone lifecycle checks for the fresh strong zone strategy.
- Zones are rejected if they were invalidated before confirmation.
- Zones are rejected if they were already retested before the current return.
- Added high/low curve filtering when higher-timeframe context is supplied.
- Added nearest opposing zone target selection, while preserving the minimum reward requirement.
- Added richer rule evidence for freshness, curve location, and target selection.
- Updated playbook coverage so implemented strategy concepts are reflected in `doctor automation-readiness`.
- Added tests for prior retest rejection, invalidation rejection, curve rejection, and opposing-zone target selection.

Review:

- This translates more of the documented playbook into deterministic code. The bot is still not autonomous-trade-ready because full opposite-zone object modeling, full multi-timeframe sequence, news blackout, and Deriv MT5 reconciliation remain blockers.

### Step 15: strategy_docs Curve Rule Correction

Work completed:

- Reviewed the extracted Echo strategy document from `strategy_docs`.
- Corrected the high/low curve implementation from broad thirds to the documented 0-25% extremes.
- Updated the agent playbook prompt and machine-readable coverage notes to describe the same 0-25% rule.
- Added a regression test proving a buy setup can pass only when higher-timeframe context is inside the low 25% curve area.

Review:

- This removes a strategy mismatch between the code and the documented playbook. The curve rule is now stricter and more consistent with the Echo notes, but the full monthly, weekly, and daily curve hierarchy still needs deterministic translation before the bot can be called autonomous-trade-ready.

### Step 16: Required Readiness Blocker Implementation

Work completed:

- Replaced prior high/low proxy logic with active opposing zone object removal.
- Added monthly, weekly, and daily directional alignment as first-class strategy context.
- Wired broker scans to fetch monthly, weekly, and daily context from the market-data provider.
- Added a deterministic scheduled economic-calendar blackout gate backed by a local JSON event file.
- Wired news blackout evidence into scan decisions so active blackout windows convert candidates to `NO_TRADE`.
- Expanded Deriv MT5 reconciliation diagnostics to verify account info, open positions, open orders, equity, margin, symbol metadata, and ticks.
- Updated the agent autonomy policy to require MT5 reconciliation rather than a generic read-only probe.
- Updated machine-readable playbook coverage so the previous required blockers are no longer listed.
- Added tests for opposing zone removal, monthly/weekly/daily alignment, news blackout, scan-level blackout blocking, and MT5 reconciliation.

Review:

- This resolves the listed readiness-doctor playbook blockers as deterministic code. At this stage, the remaining work is the guarded order-submission path and idempotency ledger, while the agent policy still requires a real trade candidate, risk approval, reconciled broker state, and explicit order-placement capability before execution.

### Step 17: Guarded Live Execution Path

Work completed:

- Added execution configuration for `EXECUTION_ENABLE_ORDER_PLACEMENT`, `EXECUTION_IDEMPOTENCY_LEDGER_PATH`, `MT5_DEVIATION_POINTS`, and `MT5_MAGIC`.
- Added typed order-submission request and result models.
- Added a file-backed idempotency ledger that blocks duplicate accepted/submitted decisions.
- Added a Deriv MT5 `order_send` path that converts risk-approved units to MT5 volume using symbol contract metadata.
- Kept MT5 order submission behind reconciliation, explicit order-placement enablement, strategy candidate, risk approval, and agent policy approval.
- Added `python3 -m forex_bot execute --pair EUR_USD` for live execution-chain preview.
- Added `python3 -m forex_bot execute --pair EUR_USD --submit-live-order` for guarded live submission when every gate is green.
- Added tests for order-placement diagnostics, MT5 order request construction, duplicate ledger blocking, and CLI execution orchestration.

Review:

- This fixes the remaining structural blockers: the bot now has a deterministic path from live scan to risk approval to reconciled MT5 order submission. It still correctly refuses to trade when no setup exists, when risk rejects, when MT5 cannot reconcile, or when the explicit live/order switches are off.

### Step 18: macOS MT5 Execution Documentation

Work completed:

- Added `docs/MT5_MAC_EXECUTION.md`.
- Documented why native macOS Python cannot complete Deriv MT5 execution with the official `MetaTrader5` package.
- Documented the current bottlenecks: no candidate, no risk approval, missing MT5 bridge, missing reconciliation, disabled live switches, and missing news blackout file.
- Recommended Windows VPS execution as the safest live path.
- Documented the Mac command-center plus Windows execution-bridge architecture.
- Linked the execution note from `README.md`.

Review:

- This makes the infrastructure decision explicit: macOS can remain the control surface, but the actual Deriv MT5 `order_send` path should run on a supported Windows environment or bridge.

### Step 19: Session 1-3 Strategy Picture Review

Work completed:

- Reviewed `strategy_docs/Session 1_Basics.pdf`, `strategy_docs/Session 2.pdf`, and `strategy_docs/Session 3_ Trendline & High and Low Curve (1).pdf`.
- Extracted PDF text and embedded chart images for visual review.
- Added `docs/STRATEGY_SESSION_REVIEW.md` summarizing the session rules and chart concepts.
- Updated the agent playbook prompt with documented visual concepts: proximal/distal lines, base quality, stairs zones, CP/PCP, gaps, touch confirmations, inheritance/flip zones, trendline rules, and monthly high/low curve.
- Expanded machine-readable playbook coverage so these new concepts are represented as implemented, partial, or missing instead of being invisible to the agent.
- Linked the session review from `README.md`.

Review:

- This improves the agent's strategy understanding while preserving execution safety. The agent can now discuss the visual concepts as context, but it is still forbidden from treating them as executable until deterministic detectors and tests exist.
