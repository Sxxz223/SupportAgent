"""Customer, identity, ownership, and order business services."""
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
import re
import sqlite3
from typing import Any

from ..products.catalog import get_product
from ..repositories.customer_repository import (
    CustomerRecord, CustomerRepository, OrderRecord, ProductRecord,
)
from ..repositories.sqlite_customer_repository import (
    SQLiteCustomerRepository, VALID_ORDER_STATUSES,
)


class CustomerValidationError(ValueError):
    pass


class CustomerNotFoundError(LookupError):
    pass


class CustomerConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class CustomerLookupResult:
    status: str
    customer: CustomerRecord | None = None
    products: tuple[ProductRecord, ...] = ()

    @property
    def confirmed(self) -> bool:
        return self.status == "CONFIRMED" and self.customer is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "confirmed": self.confirmed,
            "found": self.confirmed and bool(self.products),
            "customer": asdict(self.customer) if self.customer else None,
            "products": [asdict(item) for item in self.products],
        }


@dataclass(frozen=True)
class IdentityVerificationResult:
    status: str
    customer_id: str | None = None

    @property
    def verified(self) -> bool:
        return self.status == "VERIFIED" and self.customer_id is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "verified": self.verified,
            "customer_id": self.customer_id,
        }


@dataclass(frozen=True)
class ProductLookupResult:
    found: bool
    products: tuple[ProductRecord, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"found": self.found, "products": [asdict(item) for item in self.products]}


@dataclass(frozen=True)
class WarrantyLookupResult:
    found: bool
    status: str | None = None
    expires_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CustomerService:
    def __init__(self, repository: CustomerRepository) -> None:
        self.repository = repository

    @staticmethod
    def _phone(value: str) -> str:
        if not re.fullmatch(r"\d{4}", value):
            raise CustomerValidationError("phone_last4 must contain exactly 4 digits")
        return value

    @staticmethod
    def _name(value: str) -> str:
        name = value.strip()
        if not name:
            raise CustomerValidationError("name must not be empty")
        return name

    @staticmethod
    def _date(value: str | None, field: str) -> str | None:
        if value is None:
            return None
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as error:
            raise CustomerValidationError(f"{field} must be an ISO date") from error

    def create_customer(self, name: str, phone_last4: str) -> CustomerRecord:
        return self.repository.create_customer(self._name(name), self._phone(phone_last4))

    def get_customer(self, customer_id: str) -> CustomerRecord:
        customer = self.repository.get_customer(customer_id)
        if customer is None:
            raise CustomerNotFoundError("Customer not found")
        return customer

    def list_customers(self) -> list[CustomerRecord]:
        return self.repository.list_customers()

    def update_customer(
        self, customer_id: str, *, name: str | None = None, phone_last4: str | None = None
    ) -> CustomerRecord:
        customer = self.repository.update_customer(
            customer_id,
            name=self._name(name) if name is not None else None,
            phone_last4=self._phone(phone_last4) if phone_last4 is not None else None,
        )
        if customer is None:
            raise CustomerNotFoundError("Customer not found")
        return customer

    def delete_customer(self, customer_id: str) -> None:
        if not self.repository.delete_customer(customer_id):
            raise CustomerNotFoundError("Customer not found")

    def find_customer(
        self, *, name: str | None = None, phone_last4: str | None = None,
        order_no: str | None = None,
    ) -> CustomerLookupResult:
        if phone_last4 is not None:
            phone_last4 = self._phone(phone_last4)
        matches = self.repository.find_customer(
            name=name.strip() if name else None,
            phone_last4=phone_last4,
            order_no=order_no.strip() if order_no else None,
        )
        if not matches:
            return CustomerLookupResult(status="NOT_FOUND")
        if len(matches) > 1:
            return CustomerLookupResult(status="AMBIGUOUS")
        customer = matches[0]
        if phone_last4 is None and order_no is None:
            return CustomerLookupResult(status="FOUND", customer=customer)
        products = tuple(self.repository.get_owned_products(customer.customer_id))
        return CustomerLookupResult("CONFIRMED", customer, products)

    def verify_customer(
        self, *, name: str | None = None, phone_last4: str | None = None,
        order_no: str | None = None,
    ) -> IdentityVerificationResult:
        """Verify identity with a name plus one customer-held credential."""
        if not name or (phone_last4 is None and order_no is None):
            return IdentityVerificationResult(status="INSUFFICIENT")
        if phone_last4 is not None:
            phone_last4 = self._phone(phone_last4)
        matches = self.repository.find_customer(
            name=self._name(name),
            phone_last4=phone_last4,
            order_no=order_no.strip() if order_no else None,
        )
        if not matches:
            return IdentityVerificationResult(status="NOT_FOUND")
        if len(matches) > 1:
            return IdentityVerificationResult(status="AMBIGUOUS")
        return IdentityVerificationResult(status="VERIFIED", customer_id=matches[0].customer_id)

    def create_order(
        self, customer_id: str, order_no: str, product_id: str, purchase_date: str,
        warranty_until: str | None = None, status: str = "active",
    ) -> OrderRecord:
        self.get_customer(customer_id)
        if get_product(product_id) is None:
            raise CustomerValidationError("product_id is not present in Product Catalog")
        if status not in VALID_ORDER_STATUSES:
            raise CustomerValidationError("status must be active, returned, or replaced")
        if not order_no.strip():
            raise CustomerValidationError("order_no must not be empty")
        try:
            return self.repository.create_order(
                order_no.strip(), customer_id, product_id,
                self._date(purchase_date, "purchase_date"),
                self._date(warranty_until, "warranty_until"), status,
            )
        except sqlite3.IntegrityError as error:
            raise CustomerConflictError("order_no already exists") from error

    def get_order(self, order_no: str) -> OrderRecord:
        order = self.repository.get_order(order_no)
        if order is None:
            raise CustomerNotFoundError("Order not found")
        return order

    def list_orders_for_customer(self, customer_id: str) -> list[OrderRecord]:
        self.get_customer(customer_id)
        return self.repository.list_orders_for_customer(customer_id)

    def update_order(self, order_no: str, **changes: str | None) -> OrderRecord:
        for required_field in ("product_id", "purchase_date", "status"):
            if required_field in changes and changes[required_field] is None:
                raise CustomerValidationError(f"{required_field} cannot be null")
        if "product_id" in changes and changes["product_id"] is not None:
            if get_product(changes["product_id"]) is None:
                raise CustomerValidationError("product_id is not present in Product Catalog")
        if "status" in changes and changes["status"] is not None:
            if changes["status"] not in VALID_ORDER_STATUSES:
                raise CustomerValidationError("status must be active, returned, or replaced")
        for field in ("purchase_date", "warranty_until"):
            if field in changes and changes[field] is not None:
                changes[field] = self._date(changes[field], field)
        order = self.repository.update_order(order_no, **changes)
        if order is None:
            raise CustomerNotFoundError("Order not found")
        return order

    def delete_order(self, order_no: str) -> None:
        if not self.repository.delete_order(order_no):
            raise CustomerNotFoundError("Order not found")

    def get_owned_products(self, customer_id: str) -> tuple[ProductRecord, ...]:
        self.get_customer(customer_id)
        return tuple(self.repository.get_owned_products(customer_id))

    def get_warranty_for_customer(
        self, customer_id: str, product: str
    ) -> WarrantyLookupResult:
        products = self.get_owned_products(customer_id)
        normalized = product.strip().casefold()
        match = next((item for item in products if normalized in {
            item.product_id.casefold(), item.model.casefold(), item.display_name.casefold()
        }), None)
        if match is None or match.warranty_status is None:
            return WarrantyLookupResult(found=False)
        return WarrantyLookupResult(True, match.warranty_status, match.warranty_expires_at)


@lru_cache(maxsize=1)
def get_customer_service() -> CustomerService:
    repository = SQLiteCustomerRepository()
    repository.seed_demo_data()
    return CustomerService(repository)
