"""Local runtime context shared with Agents SDK tools."""
from dataclasses import dataclass, field

from .session import SupportSession
from services.customer_service import CustomerService, get_customer_service
from services.ticket_service import TicketService, get_ticket_service


@dataclass(frozen=True)
class AppContext:
    """Expose the current session to local tools without adding it to the prompt."""

    session: SupportSession
    customer_service: CustomerService = field(default_factory=get_customer_service)
    ticket_service: TicketService = field(default_factory=get_ticket_service)
