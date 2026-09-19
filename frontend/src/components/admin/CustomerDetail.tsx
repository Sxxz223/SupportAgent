import type { CustomerDetail as CustomerDetailType, Order } from "../../types/admin";

type Props = {
  customer: CustomerDetailType | null;
  loading: boolean;
  onEditCustomer: () => void;
  onDeleteCustomer: () => void;
  onAddOrder: () => void;
  onEditOrder: (order: Order) => void;
  onDeleteOrder: (order: Order) => void;
};

export default function CustomerDetail({
  customer,
  loading,
  onEditCustomer,
  onDeleteCustomer,
  onAddOrder,
  onEditOrder,
  onDeleteOrder,
}: Props) {
  if (loading) return <main className="admin-detail"><p className="admin-muted">Loading customer…</p></main>;
  if (!customer) {
    return <main className="admin-detail admin-detail--empty"><div className="admin-empty"><strong>Select a customer</strong><span>Customer details and orders will appear here.</span></div></main>;
  }

  return (
    <main className="admin-detail">
      <section className="profile-section">
        <div className="section-heading">
          <div><p className="eyebrow">Customer profile</p><h2>{customer.name}</h2></div>
          <div className="button-group">
            <button className="button" onClick={onEditCustomer}>Edit</button>
            <button className="button button--danger-quiet" onClick={onDeleteCustomer}>Delete</button>
          </div>
        </div>
        <dl className="profile-fields">
          <div><dt>Phone</dt><dd>****{customer.phone_last4}</dd></div>
          <div><dt>Customer ID</dt><dd>{customer.customer_id}</dd></div>
        </dl>
      </section>

      <section className="orders-section">
        <div className="section-heading">
          <div><p className="eyebrow">Orders / Products</p><h2>Purchase history</h2></div>
          <button className="button button--primary" onClick={onAddOrder}>+ Add order</button>
        </div>
        {customer.orders.length === 0 ? (
          <div className="admin-empty admin-empty--bordered"><strong>No orders</strong><span>Add an order to connect this customer with a product.</span></div>
        ) : (
          <div className="order-list">
            {customer.orders.map((order) => (
              <article className="order-card" key={order.order_no}>
                <div className="order-card__top">
                  <div><h3>{order.product.display_name}</h3><p>{order.product.model}</p></div>
                  <span className={`status-badge status-badge--${order.status}`}>{order.status}</span>
                </div>
                <dl className="order-fields">
                  <div><dt>Order number</dt><dd>{order.order_no}</dd></div>
                  <div><dt>Purchase date</dt><dd>{order.purchase_date}</dd></div>
                  <div><dt>Warranty until</dt><dd>{order.warranty_until ?? "—"}</dd></div>
                </dl>
                <div className="order-card__actions">
                  <button className="text-button" onClick={() => onEditOrder(order)}>Edit order</button>
                  <button className="text-button text-button--danger" onClick={() => onDeleteOrder(order)}>Delete order</button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
