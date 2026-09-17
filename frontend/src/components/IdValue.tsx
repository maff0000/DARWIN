import { useState } from "react";

interface IdValueProps {
  value: string;
  mono?: boolean;
  abbreviate?: boolean;
  head?: number;
  tail?: number;
}

/** Handles SHAs/fingerprints/IDs the way an instrument panel should:
 * abbreviated for scanning, full value always reachable, one-click copy.
 * PID-002 §4 requirement. */
export function IdValue({ value, mono = true, abbreviate = true, head = 8, tail = 6 }: IdValueProps) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="id-value id-value--empty">—</span>;

  // `.slice(-0)` is `.slice(0)` in JS (returns the whole string, not "") —
  // guard tail===0 explicitly rather than let that surprise ship (caught by
  // self-review screenshot of the top-bar build SHA, which is exactly the
  // head=N,tail=0 case: commit SHAs shown short-form have no tail at all).
  const tailPart = tail > 0 ? value.slice(-tail) : "";
  const display =
    abbreviate && value.length > head + tail + 3 ? `${value.slice(0, head)}…${tailPart}` : value;

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — silently ignore, copy is a convenience only */
    }
  }

  return (
    <span className="id-value">
      <span className={mono ? "mono" : undefined} title={value}>
        {display}
      </span>
      <button
        type="button"
        className="id-value__copy"
        onClick={copy}
        aria-label={`Copy full value ${value}`}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </span>
  );
}
