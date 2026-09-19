import { useState, type FormEvent } from "react";
import type { Order, OrderInput, OrderStatus, Product } from "../../types/admin";

type Props = {
  order?: Order;
  products: Product[];
  saving: boolean;
  onSubmit: (input: OrderInput) => Promise<void>;
  onCancel: () => void;
};

export default function OrderForm({ order, products, saving, onSubmit, onCancel }: Props) {
  const [orderNo, setOrderNo] = useState(order?.order_no ?? "");
  const [productId, setProductId] = useState(order?.product_id ?? products[0]?.product_id ?? "");
  const [purchaseDate, setPurchaseDate] = useState(order?.purchase_date ?? "");
  const [warrantyUntil, setWarrantyUntil] = useState(order?.warranty_until ?? "");
  const [status, setStatus] = useState<OrderStatus>(order?.status ?? "active");
  const [validation, setValidation] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!orderNo.trim() || !productId || !purchaseDate) {
      setValidation("Order number, product, and purchase date are required.");
      return;
    }
    setValidation("");
    void onSubmit({
      order_no: orderNo.trim(),
      product_id: productId,
      purchase_date: purchaseDate,
      warranty_until: warrantyUntil || null,
      status,
    });
  };

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="modal-card" role="dialog" aria-modal="true" aria-labelledby="order-form-title" onSubmit={submit}>
        <h2 id="order-form-title">{order ? "Edit order" : "New order"}</h2>
        <label className="form-field">
          <span>Order number</span>
          <input value={orderNo} onChange={(event) => setOrderNo(event.target.value)} disabled={saving || Boolean(order)} autoFocus />
        </label>
        <label className="form-field">
          <span>Product</span>
          <select aria-label="Product" value={productId} onChange={(event) => setProductId(event.target.value)} disabled={saving}>
            {products.map((product) => <option key={product.product_id} value={product.product_id}>{product.display_name}</option>)}
          </select>
        </label>
        <div className="form-grid">
          <label className="form-field">
            <span>Purchase date</span>
            <input type="date" value={purchaseDate} onChange={(event) => setPurchaseDate(event.target.value)} disabled={saving} />
          </label>
          <label className="form-field">
            <span>Warranty until</span>
            <input type="date" value={warrantyUntil} onChange={(event) => setWarrantyUntil(event.target.value)} disabled={saving} />
          </label>
        </div>
        <label className="form-field">
          <span>Status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value as OrderStatus)} disabled={saving}>
            <option value="active">Active</option>
            <option value="returned">Returned</option>
            <option value="replaced">Replaced</option>
          </select>
        </label>
        {validation ? <p className="form-error" role="alert">{validation}</p> : null}
        <div className="modal-actions">
          <button type="button" className="button" onClick={onCancel} disabled={saving}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={saving || products.length === 0}>
            {saving ? "Saving…" : "Save order"}
          </button>
        </div>
      </form>
    </div>
  );
}
