import { ApiError } from "../api/client";

interface ErrorStateProps {
  error: Error;
  dependency?: string;
  onRetry?: () => void;
}

/** Identifies the affected dependency, never shows a raw stack trace, and
 * distinguishes a DARWIN-not-ready condition from a genuine API failure
 * (PID-002 §14/§16). */
export function ErrorState({ error, dependency, onRetry }: ErrorStateProps) {
  const apiErr = error instanceof ApiError ? error : null;
  const isNotReady = apiErr?.code === "NOT_READY";

  return (
    <div className="error-state" role="alert">
      <p className="error-state__title">
        {isNotReady ? "DARWIN is not ready" : `Couldn't load ${dependency ?? "this data"}`}
      </p>
      <p className="error-state__body">
        {isNotReady
          ? "A required dependency (PostgreSQL or migrations) isn't ready yet. This view will recover automatically once it is."
          : apiErr
            ? apiErr.message
            : "An unexpected error occurred while contacting the DARWIN API."}
      </p>
      {onRetry && (
        <button type="button" className="button button--secondary" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
