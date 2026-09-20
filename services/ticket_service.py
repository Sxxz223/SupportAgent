"""Support ticket creation service."""
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

from repositories.demo_ticket_repository import DemoTicketRepository
from repositories.ticket_repository import SupportTicketRepository


@dataclass(frozen=True)
class TicketCreationResult:
    created: bool
    ticket_id: str | None = None
    status: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TicketService:
    def __init__(self, repository: SupportTicketRepository) -> None:
        self.repository = repository

    def create_ticket(self, product: str, issue: str) -> TicketCreationResult:
        if not product.strip() or not issue.strip():
            return TicketCreationResult(created=False, error="missing_required_fields")
        record = self.repository.create_ticket(product, issue)
        return TicketCreationResult(
            created=True,
            ticket_id=record.ticket_id,
            status=record.status,
        )


@lru_cache(maxsize=1)
def get_ticket_service() -> TicketService:
    return TicketService(DemoTicketRepository())
