import { Link } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";

export function NotFound() {
  return (
    <div className="page">
      <EmptyState
        title="Page not found"
        body="There's no ARENA route at this address."
        hint={undefined}
      />
      <p style={{ marginTop: "var(--space-3)" }}>
        <Link to="/">Return to Overview</Link>
      </p>
    </div>
  );
}
