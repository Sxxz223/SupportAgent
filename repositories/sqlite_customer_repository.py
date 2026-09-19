"""SQLite persistence for customers and their product orders."""
from datetime import date, datetime, timezone
from contextlib import closing
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4

from ..products.catalog import get_product
from .customer_repository import CustomerRecord, OrderRecord, ProductRecord


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "support.db"
VALID_ORDER_STATUSES = frozenset({"active", "returned", "replaced"})


class SQLiteCustomerRepository:
    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _customer(row: sqlite3.Row | None) -> CustomerRecord | None:
        return CustomerRecord(**dict(row)) if row else None

    @staticmethod
    def _order(row: sqlite3.Row | None) -> OrderRecord | None:
        return OrderRecord(**dict(row)) if row else None

    def initialize(self) -> None:
        with self._lock, closing(self._connect()) as connection, connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
                    phone_last4 TEXT NOT NULL CHECK(
                        length(phone_last4) = 4 AND phone_last4 NOT GLOB '*[^0-9]*'
                    ),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    order_no TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
                    product_id TEXT NOT NULL,
                    purchase_date TEXT NOT NULL,
                    warranty_until TEXT,
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'returned', 'replaced')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
                CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone_last4);
                CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
            """)

    def seed_demo_data(self) -> None:
        now = self._now()
        customer_id = "00000000-0000-0000-0000-000000000001"
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?, ?)",
                (customer_id, "Alice", "3721", now, now),
            )
            connection.execute(
                "INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "ANK-DEMO-001", customer_id, "anker-prime-250w", "2026-08-01",
                    "2027-08-01", "active", now, now,
                ),
            )

    def create_customer(self, name: str, phone_last4: str) -> CustomerRecord:
        now = self._now()
        record = CustomerRecord(str(uuid4()), name.strip(), phone_last4, now, now)
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO customers VALUES (?, ?, ?, ?, ?)", tuple(record.__dict__.values())
            )
        return record

    def get_customer(self, customer_id: str) -> CustomerRecord | None:
        with closing(self._connect()) as connection:
            return self._customer(connection.execute(
                "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
            ).fetchone())

    def list_customers(self) -> list[CustomerRecord]:
        with closing(self._connect()) as connection:
            return [self._customer(row) for row in connection.execute(
                "SELECT * FROM customers ORDER BY created_at, customer_id"
            ).fetchall()]

    def update_customer(
        self, customer_id: str, *, name: str | None = None, phone_last4: str | None = None
    ) -> CustomerRecord | None:
        changes = {key: value for key, value in {"name": name, "phone_last4": phone_last4}.items() if value is not None}
        if not changes:
            return self.get_customer(customer_id)
        changes["updated_at"] = self._now()
        assignments = ", ".join(f"{key} = ?" for key in changes)
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                f"UPDATE customers SET {assignments} WHERE customer_id = ?",
                (*changes.values(), customer_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_customer(customer_id)

    def delete_customer(self, customer_id: str) -> bool:
        with self._lock, closing(self._connect()) as connection, connection:
            return connection.execute(
                "DELETE FROM customers WHERE customer_id = ?", (customer_id,)
            ).rowcount > 0

    def find_customer(
        self, *, name: str | None = None, phone_last4: str | None = None,
        order_no: str | None = None,
    ) -> list[CustomerRecord]:
        clauses, values = [], []
        if name is not None:
            clauses.append("lower(c.name) = lower(?)")
            values.append(name.strip())
        if phone_last4 is not None:
            clauses.append("c.phone_last4 = ?")
            values.append(phone_last4)
        if order_no is not None:
            clauses.append("o.order_no = ?")
            values.append(order_no)
        if not clauses:
            return []
        join = "JOIN orders o ON o.customer_id = c.customer_id" if order_no is not None else ""
        sql = f"SELECT DISTINCT c.* FROM customers c {join} WHERE {' AND '.join(clauses)} ORDER BY c.created_at"
        with closing(self._connect()) as connection:
            return [self._customer(row) for row in connection.execute(sql, values).fetchall()]

    def create_order(
        self, order_no: str, customer_id: str, product_id: str, purchase_date: str,
        warranty_until: str | None, status: str,
    ) -> OrderRecord:
        now = self._now()
        record = OrderRecord(
            order_no, customer_id, product_id, purchase_date, warranty_until, status, now, now
        )
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(record.__dict__.values()),
            )
        return record

    def get_order(self, order_no: str) -> OrderRecord | None:
        with closing(self._connect()) as connection:
            return self._order(connection.execute(
                "SELECT * FROM orders WHERE order_no = ?", (order_no,)
            ).fetchone())

    def list_orders_for_customer(self, customer_id: str) -> list[OrderRecord]:
        with closing(self._connect()) as connection:
            return [self._order(row) for row in connection.execute(
                "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at, order_no",
                (customer_id,),
            ).fetchall()]

    def update_order(self, order_no: str, **changes: str | None) -> OrderRecord | None:
        allowed = {"product_id", "purchase_date", "warranty_until", "status"}
        values = {key: value for key, value in changes.items() if key in allowed}
        if not values:
            return self.get_order(order_no)
        values["updated_at"] = self._now()
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._lock, closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                f"UPDATE orders SET {assignments} WHERE order_no = ?",
                (*values.values(), order_no),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_order(order_no)

    def delete_order(self, order_no: str) -> bool:
        with self._lock, closing(self._connect()) as connection, connection:
            return connection.execute(
                "DELETE FROM orders WHERE order_no = ?", (order_no,)
            ).rowcount > 0

    def get_owned_products(self, customer_id: str) -> list[ProductRecord]:
        products = []
        for order in self.list_orders_for_customer(customer_id):
            if order.status == "returned":
                continue
            product = get_product(order.product_id)
            if product is None:
                continue
            warranty_status = None
            if order.warranty_until:
                warranty_status = "active" if date.fromisoformat(order.warranty_until) >= date.today() else "expired"
            products.append(ProductRecord(
                customer_id=customer_id,
                product_id=product.product_id,
                model=product.model,
                product_name=product.display_name,
                display_name=product.display_name,
                category=product.category,
                rag_namespace=product.rag_namespace,
                ownership_status="owned",
                order_number=order.order_no,
                purchase_date=order.purchase_date,
                warranty_until=order.warranty_until,
                warranty_status=warranty_status,
                warranty_expires_at=order.warranty_until,
            ))
        return products
