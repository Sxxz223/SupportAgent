"""JSON-backed customer assets for local demonstration only."""
import json
from pathlib import Path
from typing import Any

DEFAULT_DEMO_DATA = Path(__file__).resolve().parents[1] / "data" / "demo_customers.json"


class DemoCustomerRepository:
    """Resolve only explicitly configured demo identities; never fall back."""

    def __init__(self, data_path: str | Path = DEFAULT_DEMO_DATA) -> None:
        self.data_path = Path(data_path)

    def _load(self) -> dict[str, Any]:
        return json.loads(self.data_path.read_text(encoding="utf-8"))
