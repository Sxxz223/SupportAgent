"""Application services backed by replaceable repositories."""

from .customer_service import (
    CustomerConflictError,
    CustomerLookupResult,
    IdentityVerificationResult,
    CustomerNotFoundError,
    CustomerService,
    CustomerValidationError,
    ProductLookupResult,
    WarrantyLookupResult,
    get_customer_service,
)
from .ticket_service import TicketCreationResult, TicketService, get_ticket_service

__all__ = [
    "CustomerService",
    "CustomerConflictError",
    "CustomerLookupResult",
    "IdentityVerificationResult",
    "CustomerNotFoundError",
    "CustomerValidationError",
    "ProductLookupResult",
    "TicketCreationResult",
    "TicketService",
    "WarrantyLookupResult",
    "get_customer_service",
    "get_ticket_service",
]
