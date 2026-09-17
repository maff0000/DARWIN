interface LoadingStateProps {
  label: string;
}

/** A designed, deliberate loading placeholder -- never a bare "Loading…"
 * string with no visual weight (PID-002 §4). Every view awaiting a real
 * DARWIN_core request renders this instead of unstyled text, so a screen
 * caught mid-request still reads as an intentional state, not a stall. */
export function LoadingState({ label }: LoadingStateProps) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <span className="loading-state__pulse" aria-hidden="true" />
      <span className="loading-state__label">{label}</span>
    </div>
  );
}
