interface EmptyStateProps {
  title: string;
  body: string;
  hint?: string;
}

/** An empty screen is an invitation to act, not an apology (PID-002 §15).
 * Every call site supplies real, specific copy about what the object is —
 * never a generic "no data" placeholder. */
export function EmptyState({ title, body, hint }: EmptyStateProps) {
  return (
    <div className="empty-state" role="status">
      <p className="empty-state__title">{title}</p>
      <p className="empty-state__body">{body}</p>
      {hint && <p className="empty-state__hint">{hint}</p>}
    </div>
  );
}
