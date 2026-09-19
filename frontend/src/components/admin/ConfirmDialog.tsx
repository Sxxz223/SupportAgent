type Props = {
  title: string;
  message: string;
  confirmLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function ConfirmDialog({
  title,
  message,
  confirmLabel = "Delete",
  busy = false,
  onConfirm,
  onCancel,
}: Props) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-card modal-card--small" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h2 id="confirm-title">{title}</h2>
        <p>{message}</p>
        <div className="modal-actions">
          <button className="button" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="button button--danger" onClick={onConfirm} disabled={busy}>
            {busy ? "Deleting…" : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
