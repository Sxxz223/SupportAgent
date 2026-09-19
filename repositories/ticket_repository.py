"""Support ticket persistence contract."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TicketRecord:
    ticket_id: str
    product: str
    issue: str
    status: str


class SupportTicketRepository(Protocol):
    def create_ticket(self, product: str, issue: str) -> TicketRecord: ...
