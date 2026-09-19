"""Customer asset data-access contract."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProductRecord:
    customer_id: str
    product_id: str
    model: str
    product_name: str
    display_name: str
    category: str
    rag_namespace: str
    ownership_status: str
    order_number: str
    purchase_date: str
    warranty_until: str | None = None
    warranty_status: str | None = None
    warranty_expires_at: str | None = None


@dataclass(frozen=True)
class CustomerRecord:
    customer_id: str
    name: str
    phone_last4: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class OrderRecord:
    order_no: str
    customer_id: str
    product_id: str
    purchase_date: str
    warranty_until: str | None
    status: str
    created_at: str
    updated_at: str


class CustomerRepository(Protocol):
    """Customer records, identity evidence, orders, and ID-scoped ownership."""

    def create_customer(self, name: str, phone_last4: str) -> CustomerRecord: ...
    def get_customer(self, customer_id: str) -> CustomerRecord | None: ...
    def list_customers(self) -> list[CustomerRecord]: ...
    def update_customer(
        self, customer_id: str, *, name: str | None = None, phone_last4: str | None = None
    ) -> CustomerRecord | None: ...
    def delete_customer(self, customer_id: str) -> bool: ...
    def find_customer(
        self, *, name: str | None = None, phone_last4: str | None = None,
        order_no: str | None = None,
    ) -> list[CustomerRecord]: ...
    def create_order(
        self, order_no: str, customer_id: str, product_id: str, purchase_date: str,
        warranty_until: str | None, status: str,
    ) -> OrderRecord: ...
    def get_order(self, order_no: str) -> OrderRecord | None: ...
    def list_orders_for_customer(self, customer_id: str) -> list[OrderRecord]: ...
    def update_order(self, order_no: str, **changes: str | None) -> OrderRecord | None: ...
    def delete_order(self, order_no: str) -> bool: ...
    def get_owned_products(self, customer_id: str) -> list[ProductRecord]: ...
