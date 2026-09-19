"""Replaceable data-access contracts and demo implementations."""

from .customer_repository import CustomerRecord, CustomerRepository, OrderRecord, ProductRecord
from .demo_customer_repository import DemoCustomerRepository
from .demo_ticket_repository import DemoTicketRepository
from .ticket_repository import SupportTicketRepository, TicketRecord
from .sqlite_customer_repository import SQLiteCustomerRepository

__all__ = [
    "CustomerRepository",
    "CustomerRecord",
    "DemoCustomerRepository",
    "DemoTicketRepository",
    "ProductRecord",
    "OrderRecord",
    "SQLiteCustomerRepository",
    "SupportTicketRepository",
    "TicketRecord",
]
