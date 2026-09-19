import type { Customer } from "../../types/admin";

type Props = {
  customers: Customer[];
  selectedId: string | null;
  query: string;
  loading: boolean;
  onQueryChange: (value: string) => void;
  onSelect: (customerId: string) => void;
  onNew: () => void;
};

export default function CustomerSidebar({
  customers,
  selectedId,
  query,
  loading,
  onQueryChange,
  onSelect,
  onNew,
}: Props) {
  return (
    <aside className="admin-sidebar" aria-label="Customers">
      <div className="admin-sidebar__heading">
        <h2>Customers</h2>
        <button className="button button--primary button--compact" onClick={onNew}>
          + New
        </button>
      </div>
      <label className="admin-search">
        <span className="sr-only">Search customers</span>
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search name or phone"
        />
      </label>
      <div className="customer-list">
        {loading ? <p className="admin-muted">Loading customers…</p> : null}
        {!loading && customers.length === 0 ? (
          <div className="admin-empty">
            <strong>No customers found</strong>
            <span>{query ? "Try another search." : "Create the first customer."}</span>
          </div>
        ) : null}
        {customers.map((customer) => (
          <button
            key={customer.customer_id}
            className={`customer-list__item${selectedId === customer.customer_id ? " customer-list__item--active" : ""}`}
            onClick={() => onSelect(customer.customer_id)}
          >
            <strong>{customer.name}</strong>
            <span>****{customer.phone_last4}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}
