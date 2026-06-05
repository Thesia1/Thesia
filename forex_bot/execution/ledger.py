import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from forex_bot.execution.base import OrderSubmissionResult


@dataclass(frozen=True)
class LedgerRecord:
    idempotency_key: str
    strategy_decision_id: str
    symbol: str
    state: str
    created_at: datetime
    broker_order_id: str = ""
    broker_deal_id: str = ""
    message: str = ""


class FileOrderLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def find(self, idempotency_key: str) -> LedgerRecord | None:
        for record in self.records():
            if record.idempotency_key == idempotency_key:
                return record
        return None

    def has_submitted(self, idempotency_key: str) -> bool:
        record = self.find(idempotency_key)
        return record is not None and record.state in {"SUBMITTED", "ACCEPTED", "FILLED"}

    def record_submission(
        self,
        *,
        idempotency_key: str,
        strategy_decision_id: str,
        symbol: str,
        result: OrderSubmissionResult,
    ) -> LedgerRecord:
        record = LedgerRecord(
            idempotency_key=idempotency_key,
            strategy_decision_id=strategy_decision_id,
            symbol=symbol,
            state=result.state,
            created_at=datetime.now(timezone.utc),
            broker_order_id=result.broker_order_id,
            broker_deal_id=result.broker_deal_id,
            message=result.message,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_to_json(record), sort_keys=True) + "\n")
        return record

    def records(self) -> tuple[LedgerRecord, ...]:
        if not self.path.exists():
            return ()
        rows: list[LedgerRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            rows.append(
                LedgerRecord(
                    idempotency_key=str(payload["idempotency_key"]),
                    strategy_decision_id=str(payload["strategy_decision_id"]),
                    symbol=str(payload["symbol"]),
                    state=str(payload["state"]),
                    created_at=datetime.fromisoformat(str(payload["created_at"])),
                    broker_order_id=str(payload.get("broker_order_id", "")),
                    broker_deal_id=str(payload.get("broker_deal_id", "")),
                    message=str(payload.get("message", "")),
                )
            )
        return tuple(rows)


def _to_json(record: LedgerRecord) -> dict[str, str]:
    payload = asdict(record)
    payload["created_at"] = record.created_at.isoformat()
    return payload
