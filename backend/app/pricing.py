"""US-26: LLM cost estimates from token usage and a per-model price table.

Prices live in a JSON config file (backend/app/llm_prices.json by default, or LLM_PRICES_FILE), never in code.
Costs are computed when they are shown, at the prices in the table now, so they are estimates. A model
that isn't in the table has an unknown cost (None) rather than an error or a silent $0.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

DEFAULT_PRICES_PATH = Path(__file__).resolve().parent / "llm_prices.json"  # shipped in the Docker image with app/
PER_MILLION = 1_000_000
# A dated snapshot name (gpt-4.1-mini-2025-04-14, claude-x-20251001) uses its base model's price.
_DATED = re.compile(r"-(\d{4}-\d{2}-\d{2}|\d{8})$")


class PriceTableError(ValueError):
    """The price file is missing, not JSON, or has an invalid entry. The message names the file."""


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: float
    output_per_million: float


@dataclass(frozen=True)
class AttemptUsage:
    """One LLM attempt's token usage, with the analysis it belongs to (for cost summaries)."""
    analysis_id: str
    analysis_created_at: datetime | None
    attempt_number: int
    input_tokens: int
    output_tokens: int
    provider: str | None
    model: str | None


class PriceTable:
    def __init__(self, prices: Mapping[str, ModelPrice]):
        self.prices = dict(prices)

    def price(self, model: str | None) -> ModelPrice | None:
        if not model:
            return None
        return self.prices.get(model) or self.prices.get(_DATED.sub("", model))

    def cost(self, model: str | None, input_tokens: int, output_tokens: int) -> float | None:
        """Dollars for one attempt, or None when the model has no price."""
        p = self.price(model)
        if p is None:
            return None
        return (input_tokens * p.input_per_million + output_tokens * p.output_per_million) / PER_MILLION

    def with_prices(self, extra: Mapping[str, ModelPrice]) -> "PriceTable":
        return PriceTable({**self.prices, **extra})


def _rate(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise PriceTableError(f"{where} must be a non-negative number")
    return float(value)


def load_price_table(path: str | Path = DEFAULT_PRICES_PATH) -> PriceTable:
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as err:
        raise PriceTableError(f"can't read LLM price table {path.name}: {err}") from err
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, dict):
        raise PriceTableError(f"{path.name} needs a \"models\" object of model name -> prices")
    prices = {}
    for name, entry in models.items():
        if not isinstance(entry, dict):
            raise PriceTableError(f"{path.name}: {name} must be an object")
        prices[name] = ModelPrice(_rate(entry.get("input_per_million"), f"{path.name}: {name}.input_per_million"),
                                  _rate(entry.get("output_per_million"), f"{path.name}: {name}.output_per_million"))
    return PriceTable(prices)


def summarize_costs(rows: Iterable[AttemptUsage], prices: PriceTable) -> dict:
    """Totals over attempts. Attempts 2 and 3 are correction retries. Unknown costs are counted, not added."""
    rows = list(rows)
    total = retry = 0.0
    unknown = 0
    for r in rows:
        cost = prices.cost(r.model, r.input_tokens, r.output_tokens)
        if cost is None:
            unknown += 1
            continue
        total += cost
        if r.attempt_number > 1:
            retry += cost
    analyses = len({r.analysis_id for r in rows})
    return {
        "analysis_count": analyses,
        "attempt_count": len(rows),
        "retry_attempt_count": sum(1 for r in rows if r.attempt_number > 1),
        "input_tokens": sum(r.input_tokens for r in rows),
        "output_tokens": sum(r.output_tokens for r in rows),
        "total_cost": total,
        "average_cost": total / analyses if analyses else None,
        "retry_cost": retry,
        "retry_share": retry / total if total else None,
        "unknown_cost_attempts": unknown,
    }
