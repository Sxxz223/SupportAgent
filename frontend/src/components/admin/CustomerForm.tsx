import { useState, type FormEvent } from "react";
import type { Customer, CustomerInput } from "../../types/admin";

type Props = {
  customer?: Customer;
  saving: boolean;
  onSubmit: (input: CustomerInput) => Promise<void>;
  onCancel: () => void;
};

export default function CustomerForm({ customer, saving, onSubmit, onCancel }: Props) {
  const [name, setName] = useState(customer?.name ?? "");
  const [phone, setPhone] = useState(customer?.phone_last4 ?? "");
  const [validation, setValidation] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setValidation("Name is required.");
      return;
    }
    if (!/^\d{4}$/.test(phone)) {
      setValidation("Phone last 4 must be exactly 4 digits.");
      return;
    }
    setValidation("");
    void onSubmit({ name: name.trim(), phone_last4: phone });
  };

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="modal-card" role="dialog" aria-modal="true" aria-labelledby="customer-form-title" onSubmit={submit}>
        <h2 id="customer-form-title">{customer ? "Edit customer" : "New customer"}</h2>
        <label className="form-field">
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} disabled={saving} autoFocus />
        </label>
        <label className="form-field">
          <span>Phone last 4</span>
          <input inputMode="numeric" maxLength={4} value={phone} onChange={(event) => setPhone(event.target.value)} disabled={saving} />
        </label>
        {validation ? <p className="form-error" role="alert">{validation}</p> : null}
        <div className="modal-actions">
          <button type="button" className="button" onClick={onCancel} disabled={saving}>Cancel</button>
          <button type="submit" className="button button--primary" disabled={saving}>
            {saving ? "Saving…" : "Save customer"}
          </button>
        </div>
      </form>
    </div>
  );
}
