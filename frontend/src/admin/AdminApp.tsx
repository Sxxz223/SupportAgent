import { useCallback, useEffect, useMemo, useState } from "react";
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
import ConfirmDialog from "../components/admin/ConfirmDialog";
import CustomerDetail from "../components/admin/CustomerDetail";
import CustomerForm from "../components/admin/CustomerForm";
import CustomerSidebar from "../components/admin/CustomerSidebar";
import OrderForm from "../components/admin/OrderForm";
import type { Customer, CustomerDetail as CustomerDetailType, CustomerInput, Order, OrderInput, Product } from "../types/admin";

type DeleteTarget = { type: "customer"; customer: CustomerDetailType } | { type: "order"; order: Order };

export default function AdminApp() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CustomerDetailType | null>(null);
  const [query, setQuery] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState("");
  const [customerForm, setCustomerForm] = useState<"new" | "edit" | null>(null);
  const [orderForm, setOrderForm] = useState<Order | "new" | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [saving, setSaving] = useState(false);

  const loadInitial = useCallback(async () => {
    setLoadingList(true);
    setError("");
    try {
      const [customerRows, productRows] = await Promise.all([listCustomers(), listProducts()]);
      setCustomers(customerRows);
      setProducts(productRows);
      setSelectedId((current) => current ?? customerRows[0]?.customer_id ?? null);
    } catch {
      setError("Customer data could not be loaded. Please try again.");
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => { void loadInitial(); }, [loadInitial]);

  const loadDetail = useCallback(async (customerId: string) => {
    setLoadingDetail(true);
    setError("");
    try {
      setDetail(await getCustomer(customerId));
    } catch {
      setDetail(null);
      setError("Customer details could not be loaded. Please try again.");
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId);
    else setDetail(null);
  }, [selectedId, loadDetail]);

  const refreshAfterMutation = async (customerId: string) => {
    const rows = await listCustomers();
    setCustomers(rows);
    setSelectedId(customerId);
    await loadDetail(customerId);
  };

  const filteredCustomers = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return customers;
    return customers.filter((customer) => customer.name.toLowerCase().includes(normalized) || customer.phone_last4.includes(normalized));
  }, [customers, query]);

  const saveCustomer = async (input: CustomerInput) => {
    setSaving(true);
    setError("");
    try {
      const saved = customerForm === "edit" && detail
        ? await updateCustomer(detail.customer_id, input)
        : await createCustomer(input);
      setCustomerForm(null);
      await refreshAfterMutation(saved.customer_id);
    } catch {
      setError("Customer could not be saved. Check the details and try again.");
    } finally { setSaving(false); }
  };

  const saveOrder = async (input: OrderInput) => {
    if (!detail) return;
    setSaving(true);
    setError("");
    try {
      if (orderForm === "new") await createOrder(detail.customer_id, input);
      else if (orderForm) {
        const { order_no: _orderNo, ...changes } = input;
        await updateOrder(orderForm.order_no, changes);
      }
      setOrderForm(null);
      await refreshAfterMutation(detail.customer_id);
    } catch {
      setError("Order could not be saved. Check the details and try again.");
    } finally { setSaving(false); }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setSaving(true);
    setError("");
    try {
      if (deleteTarget.type === "customer") {
        const deletedId = deleteTarget.customer.customer_id;
        await deleteCustomer(deletedId);
        const rows = await listCustomers();
        setCustomers(rows);
        const nextId = rows.find((item) => item.customer_id !== deletedId)?.customer_id ?? null;
        setSelectedId(nextId);
        if (!nextId) setDetail(null);
      } else if (detail) {
        await deleteOrder(deleteTarget.order.order_no);
        await refreshAfterMutation(detail.customer_id);
      }
      setDeleteTarget(null);
    } catch {
      setError("The item could not be deleted. Please try again.");
    } finally { setSaving(false); }
  };

  return (
    <div className="admin-shell">
      <header className="admin-header">
        <div><p className="eyebrow">Support operations</p><h1>Customer Data Admin</h1></div>
        <a className="admin-header__link" href="/">Open customer chat</a>
      </header>
      {error ? <div className="admin-error" role="alert"><span>{error}</span><button onClick={() => void loadInitial()}>Retry</button></div> : null}
      <div className="admin-layout">
        <CustomerSidebar customers={filteredCustomers} selectedId={selectedId} query={query} loading={loadingList} onQueryChange={setQuery} onSelect={setSelectedId} onNew={() => setCustomerForm("new")} />
        <CustomerDetail customer={detail} loading={loadingDetail} onEditCustomer={() => setCustomerForm("edit")} onDeleteCustomer={() => detail && setDeleteTarget({ type: "customer", customer: detail })} onAddOrder={() => setOrderForm("new")} onEditOrder={setOrderForm} onDeleteOrder={(order) => setDeleteTarget({ type: "order", order })} />
      </div>
      {customerForm ? <CustomerForm customer={customerForm === "edit" ? detail ?? undefined : undefined} saving={saving} onSubmit={saveCustomer} onCancel={() => setCustomerForm(null)} /> : null}
      {orderForm ? <OrderForm order={orderForm === "new" ? undefined : orderForm} products={products} saving={saving} onSubmit={saveOrder} onCancel={() => setOrderForm(null)} /> : null}
      {deleteTarget ? <ConfirmDialog title={deleteTarget.type === "customer" ? `Delete ${deleteTarget.customer.name}?` : `Delete order ${deleteTarget.order.order_no}?`} message={deleteTarget.type === "customer" ? "This will also remove associated orders." : "This order will be permanently removed."} busy={saving} onCancel={() => setDeleteTarget(null)} onConfirm={() => void confirmDelete()} /> : null}
    </div>
  );
}
