"""SQLite customer persistence, identity matching, and Admin API tests."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import main  # Initialize project/SDK import separation.
from agents.tool_context import ToolContext
from fastapi.testclient import TestClient

from my_project.api.app import create_app
from my_project.api.session_store import InMemorySessionStore
from my_project.application.context import AppContext
from my_project.application.session import SupportSession
from my_project.repositories.sqlite_customer_repository import SQLiteCustomerRepository
from my_project.services.customer_service import (
    CustomerConflictError, CustomerService, CustomerValidationError,
)
from my_project.tools.support_tools import get_owned_products, verify_customer


class CustomerPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database_path = Path(self.directory.name) / "nested" / "support.db"
        self.repository = SQLiteCustomerRepository(self.database_path)
        self.service = CustomerService(self.repository)

    def create_customer(self, name="Alice", phone="3721"):
        return self.service.create_customer(name, phone)

    def create_order(self, customer_id, order_no="ANK-001", product_id="anker-prime-250w"):
        return self.service.create_order(
            customer_id, order_no, product_id, "2026-08-01", "2028-08-01"
        )

    def test_database_directory_and_customer_id_are_created(self):
        customer = self.create_customer()

        self.assertTrue(self.database_path.is_file())
        self.assertTrue(customer.customer_id)
        self.assertEqual(self.service.get_customer(customer.customer_id).name, "Alice")

    def test_same_name_is_allowed_and_name_only_lookup_is_ambiguous(self):
        self.create_customer("Alex", "1111")
        self.create_customer("Alex", "2222")

        lookup = self.service.find_customer(name="Alex")

        self.assertEqual(lookup.status, "AMBIGUOUS")
        self.assertFalse(lookup.confirmed)

    def test_name_and_phone_uniquely_confirm_customer(self):
        first = self.create_customer("Alex", "1111")
        self.create_customer("Alex", "2222")

        lookup = self.service.find_customer(name="Alex", phone_last4="1111")

        self.assertTrue(lookup.confirmed)
        self.assertEqual(lookup.customer.customer_id, first.customer_id)

    def test_phone_last4_must_be_exactly_four_digits(self):
        for value in ("123", "12345", "12a4"):
            with self.subTest(value=value), self.assertRaises(CustomerValidationError):
                self.create_customer(phone=value)

    def test_valid_order_uses_catalog_and_returns_complete_product(self):
        customer = self.create_customer()
        self.create_order(customer.customer_id)

        products = self.service.get_owned_products(customer.customer_id)

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].product_id, "anker-prime-250w")
        self.assertEqual(products[0].model, "A2345")
        self.assertEqual(
            products[0].display_name,
            "Anker Prime Charger (250W, 6 Ports, GaNPrime)",
        )
        self.assertEqual(products[0].rag_namespace, "anker_prime_250w")

    def test_invalid_product_and_duplicate_order_are_rejected(self):
        customer = self.create_customer()
        with self.assertRaises(CustomerValidationError):
            self.create_order(customer.customer_id, product_id="not-in-catalog")

        self.create_order(customer.customer_id)
        with self.assertRaises(CustomerConflictError):
            self.create_order(customer.customer_id)

    def test_customer_delete_cascades_orders(self):
        customer = self.create_customer()
        self.create_order(customer.customer_id)

        self.service.delete_customer(customer.customer_id)

        self.assertIsNone(self.repository.get_order("ANK-001"))
        self.assertEqual(self.repository.list_orders_for_customer(customer.customer_id), [])

    def test_order_number_can_confirm_identity(self):
        customer = self.create_customer("Jack", "8844")
        self.create_order(customer.customer_id, "ANK-JACK-001", "anker-nano-70w")

        lookup = self.service.find_customer(order_no="ANK-JACK-001")

        self.assertTrue(lookup.confirmed)
        self.assertEqual(lookup.customer.customer_id, customer.customer_id)
        self.assertEqual(lookup.products[0].product_id, "anker-nano-70w")

    def test_agent_tool_reads_products_from_injected_sqlite_service(self):
        customer = self.create_customer("Jack", "8844")
        self.create_order(customer.customer_id, "ANK-JACK-001", "anker-nano-70w")
        session = SupportSession()
        session.state.user_name = "Jack"
        context = ToolContext(
            context=AppContext(session=session, customer_service=self.service),
            tool_name=verify_customer.name,
            tool_call_id="sqlite-product",
            tool_arguments=json.dumps({"user_name": "Jack", "phone_last4": "8844"}),
        )

        result = asyncio.run(verify_customer.on_invoke_tool(
            context, json.dumps({"phone_last4": "8844"})
        ))

        self.assertTrue(json.loads(result)["verified"])
        self.assertEqual(session.state.customer_id, customer.customer_id)
        self.assertTrue(session.state.identity_verified)
        product_context = ToolContext(
            context=AppContext(session=session, customer_service=self.service),
            tool_name=get_owned_products.name,
            tool_call_id="sqlite-ownership",
            tool_arguments=json.dumps({"customer_id": customer.customer_id}),
        )
        asyncio.run(get_owned_products.on_invoke_tool(
            product_context, json.dumps({"customer_id": customer.customer_id})
        ))
        self.assertEqual(session.state.product_id, "anker-nano-70w")

    def test_unknown_identity_receives_no_supported_product(self):
        lookup = self.service.find_customer(name="Unknown", phone_last4="9999")

        self.assertEqual(lookup.status, "NOT_FOUND")
        self.assertEqual(lookup.products, ())

    def test_seed_is_idempotent(self):
        self.repository.seed_demo_data()
        self.repository.seed_demo_data()

        alice = self.service.find_customer(name="Alice", phone_last4="3721")

        self.assertTrue(alice.confirmed)
        self.assertEqual(len(self.service.list_customers()), 1)
        self.assertEqual(len(alice.products), 1)


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        repository = SQLiteCustomerRepository(Path(self.directory.name) / "support.db")
        self.service = CustomerService(repository)
        self.client = TestClient(create_app(
            InMemorySessionStore(),
            customer_service=self.service,
        ))

    def test_customer_and_order_crud_with_catalog_product_details(self):
        created = self.client.post("/admin/customers", json={
            "name": "Jack", "phone_last4": "8844",
        })
        self.assertEqual(created.status_code, 200)
        customer_id = created.json()["customer_id"]
        self.assertIn(customer_id, {
            item["customer_id"] for item in self.client.get("/admin/customers").json()
        })

        renamed = self.client.patch(f"/admin/customers/{customer_id}", json={
            "name": "Jack Chen"
        })
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["name"], "Jack Chen")

        order = self.client.post(f"/admin/customers/{customer_id}/orders", json={
            "order_no": "ANK-DEMO-JACK-001",
            "product_id": "anker-nano-70w",
            "purchase_date": "2026-08-01",
            "warranty_until": "2028-08-01",
            "status": "active",
        })
        self.assertEqual(order.status_code, 200)
        self.assertEqual(order.json()["product"]["model"], "A121A")
        listed_orders = self.client.get(f"/admin/customers/{customer_id}/orders")
        self.assertEqual(listed_orders.status_code, 200)
        self.assertEqual(listed_orders.json()[0]["order_no"], "ANK-DEMO-JACK-001")

        detail = self.client.get(f"/admin/customers/{customer_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["name"], "Jack Chen")
        self.assertEqual(detail.json()["orders"][0]["product_id"], "anker-nano-70w")
        self.assertEqual(detail.json()["orders"][0]["product"]["display_name"], "Anker Nano Charger (70W, 3 Ports)")

        updated = self.client.patch("/admin/orders/ANK-DEMO-JACK-001", json={
            "status": "replaced"
        })
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["status"], "replaced")

        self.assertEqual(
            self.client.delete("/admin/orders/ANK-DEMO-JACK-001").status_code, 204
        )
        self.assertEqual(self.client.delete(f"/admin/customers/{customer_id}").status_code, 204)

    def test_admin_rejects_invalid_product_duplicate_order_and_bad_phone(self):
        bad_phone = self.client.post("/admin/customers", json={
            "name": "Jack", "phone_last4": "12x4",
        })
        self.assertEqual(bad_phone.status_code, 422)

        customer_id = self.client.post("/admin/customers", json={
            "name": "Jack", "phone_last4": "8844",
        }).json()["customer_id"]
        payload = {
            "order_no": "ANK-JACK-001", "product_id": "not-in-catalog",
            "purchase_date": "2026-08-01", "status": "active",
        }
        self.assertEqual(
            self.client.post(f"/admin/customers/{customer_id}/orders", json=payload).status_code,
            400,
        )
        payload["product_id"] = "anker-nano-70w"
        self.assertEqual(
            self.client.post(f"/admin/customers/{customer_id}/orders", json=payload).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/admin/customers/{customer_id}/orders", json=payload).status_code,
            409,
        )

    def test_admin_products_comes_from_catalog(self):
        response = self.client.get("/admin/products")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["product_id"] for item in response.json()},
            {"anker-prime-250w", "anker-nano-70w", "soundcore-liberty-4-nc"},
        )


if __name__ == "__main__":
    unittest.main()
