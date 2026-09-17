import { useState, type FormEvent } from "react";
import { ApiError, api } from "../api/client";
import type { ScoutDiscovery, ScoutManualDiscoveryRequest } from "../api/types";

type ManualOriginKind = "USER_DISCOVERED" | "MY_IDEA";

interface AddStrategyModalProps {
  onClose: () => void;
  onCreated: (discovery: ScoutDiscovery) => void;
}

const METRIC_FIELDS: Array<{ key: string; label: string }> = [
  { key: "net_pnl_percent", label: "Net P&L %" },
  { key: "max_drawdown_percent", label: "Max drawdown %" },
  { key: "win_rate_percent", label: "Win rate %" },
  { key: "profit_factor", label: "Profit factor" },
  { key: "trade_count", label: "Trade count" },
  { key: "sharpe", label: "Sharpe" },
  { key: "sortino", label: "Sortino" },
];

/** POST /api/v1/scout/discoveries (manual entry) — a SEPARATE concern from
 * "Discover now" (no adapter call, no fetch of any URL). MY_IDEA must
 * never carry origin_url or claimed_metrics — the backend rejects that
 * combination with 400 SCOUT_INVALID_ORIGIN (darwin/scout/domain.py
 * build_manual_discovery), so this form hides/disables those fields
 * client-side rather than letting the user hit a confusing error, while
 * still surfacing that error gracefully if it somehow occurs. */
export function AddStrategyModal({ onClose, onCreated }: AddStrategyModalProps) {
  const [originKind, setOriginKind] = useState<ManualOriginKind>("USER_DISCOVERED");
  const [title, setTitle] = useState("");
  const [originDescription, setOriginDescription] = useState("");
  const [originUrl, setOriginUrl] = useState("");
  const [sourceSymbol, setSourceSymbol] = useState("");
  const [sourceTimeframe, setSourceTimeframe] = useState("");
  const [originalDescription, setOriginalDescription] = useState("");
  const [pastedRuleText, setPastedRuleText] = useState("");
  const [personalNotes, setPersonalNotes] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [metrics, setMetrics] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMyIdea = originKind === "MY_IDEA";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("A title is required.");
      return;
    }
    const tags = tagsText
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    const claimedMetrics: Record<string, string> = {};
    if (!isMyIdea) {
      for (const { key } of METRIC_FIELDS) {
        const v = metrics[key];
        if (v && v.trim()) claimedMetrics[key] = v.trim();
      }
    }
    const body: ScoutManualDiscoveryRequest = {
      origin_kind: originKind,
      title: title.trim(),
      origin_description: originDescription.trim() || undefined,
      origin_url: isMyIdea ? undefined : originUrl.trim() || undefined,
      source_symbol: sourceSymbol.trim() || undefined,
      source_timeframe: sourceTimeframe.trim() || undefined,
      original_description: originalDescription.trim() || undefined,
      pasted_rule_text: pastedRuleText || undefined,
      personal_notes: personalNotes.trim() || undefined,
      tags: tags.length ? tags : undefined,
      claimed_metrics: !isMyIdea && Object.keys(claimedMetrics).length ? claimedMetrics : undefined,
    };
    setSubmitting(true);
    try {
      const res = await api.scoutCreateDiscovery(body);
      onCreated(res.discovery);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the discovery.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="add-strategy-title">
        <div className="modal-panel__header">
          <h2 id="add-strategy-title">+ Add Strategy</h2>
          <button type="button" className="modal-panel__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <form className="modal-panel__body" onSubmit={submit}>
          <label className="form-field">
            Origin
            <select value={originKind} onChange={(e) => setOriginKind(e.target.value as ManualOriginKind)}>
              <option value="USER_DISCOVERED">Found externally (USER_DISCOVERED)</option>
              <option value="MY_IDEA">My own idea (MY_IDEA)</option>
            </select>
          </label>
          <p className="form-hint">
            {isMyIdea
              ? "MY_IDEA is Matt's own hypothesis — it carries no URL, no external source, and no claimed metrics."
              : "USER_DISCOVERED is a strategy idea found outside SCOUT's automated adapter (a website, TradingView, Reddit, YouTube, a paper, a forum, a trader, etc.)."}
          </p>

          <label className="form-field">
            Title *
            <input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </label>

          {!isMyIdea && (
            <label className="form-field">
              Source URL / reference
              <input
                value={originUrl}
                onChange={(e) => setOriginUrl(e.target.value)}
                placeholder="https://…"
                type="url"
              />
            </label>
          )}

          <label className="form-field">
            Origin description
            <input
              value={originDescription}
              onChange={(e) => setOriginDescription(e.target.value)}
              placeholder="e.g. Reddit post, YouTube video title…"
            />
          </label>

          <div className="form-row">
            <label className="form-field">
              Source symbol
              <input value={sourceSymbol} onChange={(e) => setSourceSymbol(e.target.value)} placeholder="e.g. XAUUSD" />
            </label>
            <label className="form-field">
              Source timeframe
              <input
                value={sourceTimeframe}
                onChange={(e) => setSourceTimeframe(e.target.value)}
                placeholder="verbatim, e.g. 1h"
              />
            </label>
          </div>

          <label className="form-field">
            Original description (verbatim)
            <textarea
              value={originalDescription}
              onChange={(e) => setOriginalDescription(e.target.value)}
              rows={2}
            />
          </label>

          <label className="form-field">
            Pasted rule/code text (stored as inert text — never executed or rendered as HTML)
            <textarea value={pastedRuleText} onChange={(e) => setPastedRuleText(e.target.value)} rows={3} />
          </label>

          <label className="form-field">
            Personal notes
            <textarea value={personalNotes} onChange={(e) => setPersonalNotes(e.target.value)} rows={2} />
          </label>

          <label className="form-field">
            Tags (comma-separated)
            <input value={tagsText} onChange={(e) => setTagsText(e.target.value)} placeholder="breakout, session, gold" />
          </label>

          {!isMyIdea && (
            <fieldset className="form-fieldset">
              <legend>Claimed metrics (optional — SOURCE_CLAIM, never verified by DARWIN)</legend>
              <div className="form-metric-grid">
                {METRIC_FIELDS.map(({ key, label }) => (
                  <label className="form-field" key={key}>
                    {label}
                    <input
                      value={metrics[key] ?? ""}
                      onChange={(e) => setMetrics((m) => ({ ...m, [key]: e.target.value }))}
                      inputMode="decimal"
                    />
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}

          <div className="modal-panel__actions">
            <button type="button" className="button button--secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="button" disabled={submitting}>
              {submitting ? "Adding…" : "Add strategy"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
