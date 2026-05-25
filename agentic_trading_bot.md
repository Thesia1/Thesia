forex-bot/
├── apps/
│   ├── ingestor/        # market data + news workers
│   ├── strategy/        # signal generation, backtests
│   ├── agent/           # Claude orchestrator, tool registry
│   ├── risk/            # risk gate service
│   ├── executor/        # OMS + broker adapter
│   └── dashboard/       # Next.js or Streamlit UI
├── libs/
│   ├── broker_adapters/ # OANDA, IBKR
│   ├── indicators/
│   ├── schemas/         # Pydantic models, shared across services
│   ├── eventbus/        # Redis Streams wrapper
│   └── shared/          # logging, config, telemetry
├── infra/
│   ├── docker-compose.yml
│   ├── prometheus/
│   ├── grafana/
│   ├── alertmanager/
│   └── migrations/      # alembic for TimescaleDB
├── notebooks/           # research, backtests, agent eval
├── scripts/             # ops scripts (backup, restore, replay)
└── tests/               # unit + integration + property-based (hypothesis)