"""Cost ledger and budget gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from .markdown import iso_now


DEFAULT_LIMITS = {
    "per_subtask": 1.00,
    "per_research_task": 5.00,
    "per_deep_research": 10.00,
    "per_lint_run": 3.00,
    "per_day_total": 20.00,
    "warn_at_pct": 0.80,
    "monthly_target": 300.00,
}


@dataclass(frozen=True)
class CostEntry:
    timestamp: str
    scope: str
    operation: str
    model: str
    cost_usd: float
    notes: str = ""


@dataclass(frozen=True)
class CostGate:
    allowed: bool
    warning: bool
    spent_before: float
    projected: float
    limit: float
    reason: str


class CostLedger:
    def __init__(self, path: Path, limits: dict[str, float] | None = None) -> None:
        self.path = path
        self.limits = dict(DEFAULT_LIMITS)
        if limits:
            self.limits.update(limits)

    def ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                "# Cost Ledger\n\n"
                "| timestamp | scope | operation | model | cost_usd | notes |\n"
                "|---|---|---|---|---:|---|\n",
                encoding="utf-8",
            )

    def entries(self) -> list[CostEntry]:
        if not self.path.exists():
            return []
        rows: list[CostEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|") or line.startswith("|---") or "timestamp" in line:
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) < 6:
                continue
            try:
                rows.append(CostEntry(cells[0], cells[1], cells[2], cells[3], float(cells[4]), cells[5]))
            except ValueError:
                continue
        return rows

    def spent_today(self, *, entries: Iterable[CostEntry] | None = None, day: date | None = None) -> float:
        day_text = (day or datetime.now(timezone.utc).date()).isoformat()
        return sum(entry.cost_usd for entry in (entries or self.entries()) if entry.timestamp.startswith(day_text))

    def gate(self, amount: float, *, limit_key: str = "per_day_total", day: date | None = None) -> CostGate:
        limit = float(self.limits[limit_key])
        spent = self.spent_today(day=day)
        projected = spent + amount
        warn_at = limit * float(self.limits["warn_at_pct"])
        if projected > limit:
            return CostGate(False, True, spent, projected, limit, f"projected ${projected:.2f} exceeds {limit_key} ${limit:.2f}")
        if projected >= warn_at:
            return CostGate(True, True, spent, projected, limit, f"projected ${projected:.2f} is at or above 80% of {limit_key}")
        return CostGate(True, False, spent, projected, limit, "within budget")

    def record(
        self,
        *,
        scope: str,
        operation: str,
        model: str,
        cost_usd: float,
        notes: str = "",
        enforce: bool = True,
        limit_key: str = "per_day_total",
    ) -> CostGate:
        self.ensure()
        gate = self.gate(cost_usd, limit_key=limit_key)
        if enforce and not gate.allowed:
            return gate
        safe_notes = notes.replace("|", "/").replace("\n", " ")
        row = f"| {iso_now()} | {scope} | {operation} | {model} | {cost_usd:.6f} | {safe_notes} |\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(row)
        return gate

    def rollup(self, *, day: date | None = None) -> str:
        entries = self.entries()
        day_text = (day or datetime.now(timezone.utc).date()).isoformat()
        todays = [entry for entry in entries if entry.timestamp.startswith(day_text)]
        total = sum(entry.cost_usd for entry in todays)
        by_scope: dict[str, float] = {}
        for entry in todays:
            by_scope[entry.scope] = by_scope.get(entry.scope, 0.0) + entry.cost_usd
        lines = [f"# Cost Summary for {day_text}", "", f"Total: ${total:.4f}"]
        for scope, cost in sorted(by_scope.items()):
            lines.append(f"- {scope}: ${cost:.4f}")
        return "\n".join(lines) + "\n"
