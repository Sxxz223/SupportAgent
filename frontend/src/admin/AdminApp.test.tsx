import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createCustomer,
  createOrder,
  deleteCustomer,
  deleteOrder,
  getCustomer,
  listCustomers,
  listProducts,
  updateCustomer,
  updateOrder,
} from "../api/client";
import type { Customer, CustomerDetail, Order, Product } from "../types/admin";
import AdminApp from "./AdminApp";

vi.mock("../api/client", () => ({
  createCustomer: vi.fn(), createOrder: vi.fn(), deleteCustomer: vi.fn(), deleteOrder: vi.fn(),
  getCustomer: vi.fn(), listCustomers: vi.fn(), listProducts: vi.fn(), updateCustomer: vi.fn(), updateOrder: vi.fn(),
}));

const alice: Customer = { customer_id: "cust-alice", name: "Alice", phone_last4: "3721", created_at: "2026-01-01", updated_at: "2026-01-01" };
const product: Product = { product_id: "anker-nano-70w", display_name: "Anker Nano Charger (70W, 3 Ports)", model: "A121A", category: "charger", rag_namespace: "nano-70w", aliases: [] };
const order: Order = { order_no: "ANK-001", customer_id: alice.customer_id, product_id: product.product_id, purchase_date: "2026-09-01", warranty_until: "2027-09-01", status: "active", created_at: "2026-09-01", updated_at: "2026-09-01", product };
const detail: CustomerDetail = { ...alice, orders: [order] };

const mocks = {
  createCustomer: vi.mocked(createCustomer), createOrder: vi.mocked(createOrder), deleteCustomer: vi.mocked(deleteCustomer),
  deleteOrder: vi.mocked(deleteOrder), getCustomer: vi.mocked(getCustomer), listCustomers: vi.mocked(listCustomers),
  listProducts: vi.mocked(listProducts), updateCustomer: vi.mocked(updateCustomer), updateOrder: vi.mocked(updateOrder),
};

describe("Customer Admin", () => {
  beforeEach(() => {
    Object.values(mocks).forEach((mock) => mock.mockReset());
    mocks.listCustomers.mockResolvedValue([alice]);
    mocks.listProducts.mockResolvedValue([product]);
    mocks.getCustomer.mockResolvedValue(detail);
    mocks.deleteCustomer.mockResolvedValue();
    mocks.deleteOrder.mockResolvedValue();
  });

  it("renders the customer list, masked phone, and order product details", async () => {
    render(<AdminApp />);
    expect(await screen.findByText("Alice")).toBeInTheDocument();
    expect(screen.getAllByText("****3721").length).toBeGreaterThan(0);
    expect(await screen.findByText(product.display_name)).toBeInTheDocument();
    expect(screen.getByText("A121A")).toBeInTheDocument();
    expect(screen.getByText("ANK-001")).toBeInTheDocument();
  });

  it("creates a customer and automatically selects the saved record", async () => {
    const jack = { ...alice, customer_id: "cust-jack", name: "Jack", phone_last4: "8842" };
    mocks.createCustomer.mockResolvedValue(jack);
    mocks.listCustomers.mockResolvedValueOnce([alice]).mockResolvedValueOnce([alice, jack]);
    mocks.getCustomer.mockImplementation(async (id) => id === jack.customer_id ? { ...jack, orders: [] } : detail);
    const user = userEvent.setup();
    render(<AdminApp />);
    await screen.findByText("Alice");

    await user.click(screen.getByRole("button", { name: "+ New" }));
    await user.type(screen.getByLabelText("Name"), "Jack");
    await user.type(screen.getByLabelText("Phone last 4"), "8842");
    await user.click(screen.getByRole("button", { name: "Save customer" }));

    await waitFor(() => expect(mocks.createCustomer).toHaveBeenCalledWith({ name: "Jack", phone_last4: "8842" }));
    expect(await screen.findByRole("heading", { name: "Jack" })).toBeInTheDocument();
  });

  it("edits a customer", async () => {
    const edited = { ...alice, name: "Alice Chen" };
    mocks.updateCustomer.mockResolvedValue(edited);
    mocks.getCustomer.mockResolvedValueOnce(detail).mockResolvedValueOnce({ ...edited, orders: [order] });
    const user = userEvent.setup();
    render(<AdminApp />);
    await screen.findByText(product.display_name);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const name = screen.getByLabelText("Name");
    await user.clear(name);
    await user.type(name, "Alice Chen");
    await user.click(screen.getByRole("button", { name: "Save customer" }));

    await waitFor(() => expect(mocks.updateCustomer).toHaveBeenCalledWith(alice.customer_id, { name: "Alice Chen", phone_last4: "3721" }));
  });

  it("requires confirmation before deleting a customer", async () => {
    mocks.listCustomers.mockResolvedValueOnce([alice]).mockResolvedValueOnce([]);
    const user = userEvent.setup();
    render(<AdminApp />);
    await screen.findByText(product.display_name);
    await user.click(screen.getByRole("button", { name: "Delete" }));

    const dialog = screen.getByRole("dialog", { name: "Delete Alice?" });
    expect(within(dialog).getByText("This will also remove associated orders.")).toBeInTheDocument();
    expect(mocks.deleteCustomer).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(mocks.deleteCustomer).toHaveBeenCalledWith(alice.customer_id));
  });

  it("loads products into the order dropdown and creates an order", async () => {
    mocks.createOrder.mockResolvedValue(order);
    const user = userEvent.setup();
    render(<AdminApp />);
    await screen.findByText(product.display_name);
    await user.click(screen.getByRole("button", { name: "+ Add order" }));

    expect(screen.getByRole("option", { name: product.display_name })).toHaveValue(product.product_id);
    await user.type(screen.getByLabelText("Order number"), "ANK-JACK-001");
    await user.type(screen.getByLabelText("Purchase date"), "2026-09-01");
    await user.click(screen.getByRole("button", { name: "Save order" }));
    await waitFor(() => expect(mocks.createOrder).toHaveBeenCalledWith(alice.customer_id, expect.objectContaining({ order_no: "ANK-JACK-001", product_id: product.product_id })));
  });

  it("rejects an invalid phone last 4 without calling the API", async () => {
    const user = userEvent.setup();
    render(<AdminApp />);
    await screen.findByText("Alice");
    await user.click(screen.getByRole("button", { name: "+ New" }));
    await user.type(screen.getByLabelText("Name"), "Jack");
    await user.type(screen.getByLabelText("Phone last 4"), "12ab");
    await user.click(screen.getByRole("button", { name: "Save customer" }));
    expect(screen.getByRole("alert")).toHaveTextContent("exactly 4 digits");
    expect(mocks.createCustomer).not.toHaveBeenCalled();
  });

  it("shows an actionable error when the Admin API fails", async () => {
    mocks.listCustomers.mockRejectedValue(new Error("offline"));
    render(<AdminApp />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Customer data could not be loaded");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
