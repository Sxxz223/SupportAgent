"""Process-local ticket storage for the demo; replace in production."""
from uuid import uuid4

from .ticket_repository import TicketRecord


class DemoTicketRepository:
    def __init__(self) -> None:
        self.records: dict[str, TicketRecord] = {}

    def create_ticket(self, product: str, issue: str) -> TicketRecord:
        ticket_id = f"DEMO-{uuid4().hex[:12].upper()}"
        record = TicketRecord(
            ticket_id=ticket_id,
            product=product,
            issue=issue,
            status="open",
        )
        self.records[ticket_id] = record
        return record
