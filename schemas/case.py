"""Serializable case facts shared by text, vision, tools and UI decisions."""
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FactRevision:
    value: Any
    source: str
    confirmed: bool
    turn_id: str
    case_version: int
    kind: str = "context"


@dataclass
class CaseFact:
    key: str
    value: Any
    source: str
    confirmed: bool
    turn_id: str
    case_version: int
    kind: str = "context"
    history: list[FactRevision] = field(default_factory=list)

    def replace(
        self, value: Any, source: str, confirmed: bool,
        turn_id: str, case_version: int, kind: str = "context",
    ) -> None:
        if value != self.value or source != self.source or confirmed != self.confirmed:
            self.history.append(FactRevision(
                value=self.value,
                source=self.source,
                confirmed=self.confirmed,
                turn_id=self.turn_id,
                case_version=self.case_version,
                kind=self.kind,
            ))
        self.value = value
        self.source = source
        self.confirmed = confirmed
        self.turn_id = turn_id
        self.case_version = case_version
        self.kind = kind

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CaseFact":
        return cls(
            key=data["key"], value=data.get("value"), source=data["source"],
            confirmed=bool(data.get("confirmed")), turn_id=data["turn_id"],
            case_version=int(data["case_version"]),
            kind=data.get("kind", "context"),
            history=[FactRevision(**item) for item in data.get("history", [])],
        )
