import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type {
  AtomicConditionDoc,
  ComparisonOperator,
  CompositionDoc,
  DataAuthorityClass,
  Direction,
  ExpiryMode,
  FactClass,
  InstrumentApplicabilityKind,
  InstrumentDefinition,
  IntrabarAmbiguityPolicy,
  SpecificationDraftDoc,
  Workshop,
} from "../../api/types";

const COMPARISON_OPERATORS: ComparisonOperator[] = ["EQ", "NE", "GT", "GTE", "LT", "LTE", "CROSSES_ABOVE", "CROSSES_BELOW"];
const DIRECTIONS: Direction[] = ["LONG", "SHORT", "BOTH"];
const FACT_CLASSES: FactClass[] = [
  "MARKET_OHLCV",
  "OPTIONS_CHAIN",
  "IMPLIED_VOLATILITY",
  "OPEN_INTEREST",
  "FUTURES_CURVE",
  "NEWS_CONTEXT",
  "ECONOMIC_SURPRISE",
  "PREDICTION_MARKET",
];
const AUTHORITY_CLASSES: DataAuthorityClass[] = [
  "HERMES_CANONICAL_MARKET",
  "ARES_GOVERNED_CONTEXT",
  "OPTIONS_AUTHORITY",
  "FUTURES_AUTHORITY",
  "OTHER_GOVERNED_AUTHORITY",
];
const TIMEFRAME_PRESETS = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"];
const TIMEFRAME_PATTERN = /^(M|H|D|W)[1-9][0-9]*$/;

function newAtomicCondition(idSeed: string): AtomicConditionDoc {
  return {
    __type__: "AtomicCondition",
    condition_id: idSeed,
    semantic_role: "TRIGGER",
    timeframe: "H1",
    direction: "LONG",
    expression: {
      __type__: "Comparison",
      operator: "GT",
      left: { __type__: "Literal", value: null, unit: null },
      right: { __type__: "Literal", value: null, unit: null },
    },
  };
}

function isComparison(node: unknown): node is { __type__: "Comparison"; operator: ComparisonOperator; left: any; right: any } {
  return !!node && typeof node === "object" && (node as any).__type__ === "Comparison";
}

function operandKind(node: any): "LITERAL" | "FACT" {
  return node?.__type__ === "CanonicalFactReference" ? "FACT" : "LITERAL";
}

function literalValueToText(value: any): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object" && "__decimal__" in value) return value.__decimal__;
  return String(value);
}

/** One AtomicCondition — condition_id / semantic_role / timeframe / direction
 * + a Comparison(fact-or-literal, operator, fact-or-literal) expression.
 * This is the primary, deliberately scoped-down expression shape this MVP
 * editor builds (matches `simple_atomic_condition`'s own fixture shape) —
 * BooleanExpression/TemporalPredicate/SessionPredicate/EventPredicate/
 * derived-fact nodes are NOT constructible here; if a loaded draft already
 * contains one, it round-trips through the read-only Advanced JSON view
 * below instead of this structured editor (never silently dropped). */
function AtomicConditionEditor({
  condition,
  onChange,
  onRemove,
  requirementIds,
}: {
  condition: AtomicConditionDoc;
  onChange: (next: AtomicConditionDoc) => void;
  onRemove?: () => void;
  requirementIds: string[];
}) {
  const expr = condition.expression;
  const comparison = isComparison(expr) ? expr : null;

  function updateComparisonSide(side: "left" | "right", next: any) {
    if (!comparison) return;
    onChange({ ...condition, expression: { ...comparison, [side]: next } });
  }

  function renderOperand(side: "left" | "right") {
    const node = comparison ? comparison[side] : null;
    const kind = operandKind(node);
    return (
      <div className="workshop-operand-editor">
        <select
          value={kind}
          onChange={(e) => {
            if (e.target.value === "LITERAL") {
              updateComparisonSide(side, { __type__: "Literal", value: null, unit: null });
            } else {
              updateComparisonSide(side, {
                __type__: "CanonicalFactReference",
                fact_key: "OHLCV.CLOSE",
                fact_class: "MARKET_OHLCV",
                authority_class: "HERMES_CANONICAL_MARKET",
                unit: "",
                timeframe: condition.timeframe,
                requirement_id: requirementIds[0] ?? "",
              });
            }
          }}
        >
          <option value="LITERAL">Literal value</option>
          <option value="FACT">Canonical fact reference</option>
        </select>
        {kind === "LITERAL" ? (
          <span className="workshop-operand-fields">
            <input
              placeholder="value"
              value={literalValueToText(node?.value)}
              onChange={(e) =>
                updateComparisonSide(side, {
                  __type__: "Literal",
                  value: e.target.value === "" ? null : { __decimal__: e.target.value },
                  unit: node?.unit ?? null,
                })
              }
            />
            <input
              placeholder="unit"
              value={node?.unit ?? ""}
              onChange={(e) => updateComparisonSide(side, { ...node, __type__: "Literal", unit: e.target.value || null })}
            />
          </span>
        ) : (
          <span className="workshop-operand-fields">
            <input
              placeholder="fact_key (e.g. OHLCV.CLOSE)"
              value={node?.fact_key ?? ""}
              onChange={(e) => updateComparisonSide(side, { ...node, fact_key: e.target.value })}
            />
            <select value={node?.fact_class ?? "MARKET_OHLCV"} onChange={(e) => updateComparisonSide(side, { ...node, fact_class: e.target.value })}>
              {FACT_CLASSES.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
            <select
              value={node?.authority_class ?? "HERMES_CANONICAL_MARKET"}
              onChange={(e) => updateComparisonSide(side, { ...node, authority_class: e.target.value })}
            >
              {AUTHORITY_CLASSES.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
            <input
              placeholder="unit"
              value={node?.unit ?? ""}
              onChange={(e) => updateComparisonSide(side, { ...node, unit: e.target.value })}
            />
            <select value={node?.requirement_id ?? ""} onChange={(e) => updateComparisonSide(side, { ...node, requirement_id: e.target.value })}>
              <option value="">— requirement_id —</option>
              {requirementIds.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="workshop-atomic-card">
      <div className="form-row">
        <label className="form-field">
          Condition ID
          <input value={condition.condition_id} onChange={(e) => onChange({ ...condition, condition_id: e.target.value })} />
        </label>
        <label className="form-field">
          Semantic role
          <input value={condition.semantic_role} onChange={(e) => onChange({ ...condition, semantic_role: e.target.value })} />
        </label>
        <label className="form-field">
          Timeframe
          <input
            list="workshop-timeframe-presets"
            value={condition.timeframe}
            onChange={(e) => onChange({ ...condition, timeframe: e.target.value })}
            className={TIMEFRAME_PATTERN.test(condition.timeframe) ? undefined : "workshop-input--invalid"}
          />
        </label>
        <label className="form-field">
          Direction
          <select value={condition.direction} onChange={(e) => onChange({ ...condition, direction: e.target.value as Direction })}>
            {DIRECTIONS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
      </div>
      {comparison ? (
        <div className="workshop-comparison-editor">
          {renderOperand("left")}
          <select
            value={comparison.operator}
            onChange={(e) => onChange({ ...condition, expression: { ...comparison, operator: e.target.value as ComparisonOperator } })}
          >
            {COMPARISON_OPERATORS.map((op) => (
              <option key={op} value={op}>
                {op}
              </option>
            ))}
          </select>
          {renderOperand("right")}
        </div>
      ) : (
        <p style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>
          This condition's expression is not a simple Comparison (e.g. it uses BooleanExpression/
          TemporalPredicate/SessionPredicate/EventPredicate) — not editable in this MVP structured editor; see
          the read-only Advanced JSON view below for its exact content.
        </p>
      )}
      {onRemove && (
        <div className="row-actions">
          <button type="button" className="button button--secondary" onClick={onRemove}>
            Remove condition
          </button>
        </div>
      )}
    </div>
  );
}

/** The pragmatic semantic editor (PID-004B directive) — NOT a JSON textarea
 * as the primary UI. Covers instrument applicability, composition
 * (ATOMIC/ALL/ANY/SEQUENCE/CONTEXT_TRIGGER as structured cards, never
 * flattened), intrabar ambiguity policy, setup expiry, and exit rules.
 * Every save PUTs the WHOLE current draft document under
 * `expected_revision` — the backend's `update_draft` always replaces the
 * full document, so this component always spreads `draft` before mutating
 * one field, never sends a bare partial patch that would silently erase
 * the rest of the draft. */
export function SpecificationPanel({
  workshop,
  draft,
  revision,
  onSave,
  conflict,
  onReloadDraft,
}: {
  workshop: Workshop;
  draft: SpecificationDraftDoc | null;
  revision: number | null;
  onSave: (next: SpecificationDraftDoc) => Promise<boolean>;
  conflict: string | null;
  onReloadDraft: () => Promise<void>;
}) {
  const [local, setLocal] = useState<SpecificationDraftDoc | null>(draft);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [instruments, setInstruments] = useState<InstrumentDefinition[]>([]);
  const [showJson, setShowJson] = useState(false);
  const editable = workshop.status === "ACTIVE";

  useEffect(() => {
    api.listInstrumentDefinitions().then((r) => setInstruments(r.items)).catch(() => setInstruments([]));
  }, []);

  useEffect(() => {
    if (!dirty) setLocal(draft);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, revision]);

  if (!draft || !local) {
    return (
      <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
        <h2 className="panel-heading">Specification</h2>
        <p style={{ padding: "var(--space-4)", color: "var(--ink-faint)", fontSize: 12.5 }}>
          No draft exists yet.
        </p>
      </section>
    );
  }

  function update(patch: Partial<SpecificationDraftDoc>) {
    setLocal((prev) => (prev ? { ...prev, ...patch } : prev));
    setDirty(true);
  }

  async function save() {
    if (!local) return;
    setSaving(true);
    const ok = await onSave(local);
    setSaving(false);
    if (ok) setDirty(false);
  }

  const requirementIds = Object.keys(local.data_requirements);
  const kind = local.instrument_applicability?.kind ?? "EXPLICIT_SINGLE";
  const compositionKind: "NONE" | CompositionDoc["__type__"] = local.composition
    ? local.composition.__type__
    : "NONE";

  function setCompositionKind(nextKind: string) {
    if (nextKind === "NONE") {
      update({ composition: null });
      return;
    }
    const seed = newAtomicCondition("trigger_1");
    if (nextKind === "AtomicCondition") {
      update({ composition: seed });
    } else if (nextKind === "AllComposition") {
      update({ composition: { __type__: "AllComposition", composition_id: "all_1", components: [seed], direction_relationship: null } });
    } else if (nextKind === "AnyComposition") {
      update({ composition: { __type__: "AnyComposition", composition_id: "any_1", components: [seed], direction_relationship: null } });
    } else if (nextKind === "SequenceComposition") {
      update({
        composition: {
          __type__: "SequenceComposition",
          composition_id: "seq_1",
          components: [{ sequence_index: 0, component: seed }],
          ordering_window_seconds: 3600,
          tie_semantics: "TIES_PERMITTED",
          direction_relationship: null,
        },
      });
    } else if (nextKind === "ContextTriggerComposition") {
      update({
        composition: {
          __type__: "ContextTriggerComposition",
          composition_id: "ctx_1",
          context: newAtomicCondition("context_1"),
          trigger: newAtomicCondition("trigger_1"),
          context_validity: { __type__: "ExpirySpec", mode: "NOT_APPLICABLE", frame_count: null, finest_bound_timeframe: null, duration_seconds: null },
          direction_relationship: null,
        },
      });
    }
  }

  return (
    <section className="panel workshop-specification-panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Specification</h2>
      <div style={{ padding: "var(--space-4)", display: "grid", gap: "var(--space-4)" }}>
        <datalist id="workshop-timeframe-presets">
          {TIMEFRAME_PRESETS.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>

        {/* Instrument applicability */}
        <div>
          <h3 className="workshop-subheading">Instrument applicability</h3>
          <div className="form-row">
            <label className="form-field">
              Kind
              <select
                disabled={!editable}
                value={kind}
                onChange={(e) =>
                  update({
                    instrument_applicability: {
                      __type__: "InstrumentApplicability",
                      kind: e.target.value as InstrumentApplicabilityKind,
                      instrument_ids: local.instrument_applicability?.instrument_ids ?? [],
                      generic_criteria: local.instrument_applicability?.generic_criteria ?? [],
                    },
                  })
                }
              >
                {/* Deliberately no occurrence of the word "instrument" in
                    these option labels — the sibling "Instrument" select
                    just below reuses that exact word as its OWN label
                    text, and some browsers fold a <select>'s currently
                    displayed option text into its wrapping <label>'s
                    accessible name, which would otherwise make this Kind
                    control ambiguously match "Instrument" too. */}
                <option value="EXPLICIT_SINGLE">Explicit — single</option>
                <option value="EXPLICIT_SET">Explicit — set</option>
                <option value="INSTRUMENT_GENERIC">Generic (any applicable)</option>
              </select>
            </label>
            {kind !== "INSTRUMENT_GENERIC" && (
              <label className="form-field">
                Instrument{kind === "EXPLICIT_SET" ? "(s)" : ""}
                <select
                  disabled={!editable}
                  multiple={kind === "EXPLICIT_SET"}
                  value={local.instrument_applicability?.instrument_ids ?? []}
                  onChange={(e) => {
                    const ids = Array.from(e.target.selectedOptions).map((o) => o.value);
                    update({
                      instrument_applicability: {
                        __type__: "InstrumentApplicability",
                        kind: kind,
                        instrument_ids: ids,
                        generic_criteria: [],
                      },
                    });
                  }}
                >
                  {instruments.map((i) => (
                    <option key={i.instrument_id} value={i.instrument_id}>
                      {i.instrument_id}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </div>

        {/* Composition */}
        <div>
          <h3 className="workshop-subheading">Composition</h3>
          <label className="form-field">
            Composition kind
            <select disabled={!editable} value={compositionKind} onChange={(e) => setCompositionKind(e.target.value)}>
              <option value="NONE">— none —</option>
              <option value="AtomicCondition">ATOMIC — one condition</option>
              <option value="AllComposition">ALL — every component must match</option>
              <option value="AnyComposition">ANY — at least one component matches</option>
              <option value="SequenceComposition">SEQUENCE — ordered components</option>
              <option value="ContextTriggerComposition">CONTEXT_TRIGGER — context + trigger</option>
            </select>
          </label>

          {local.composition?.__type__ === "AtomicCondition" && (
            <AtomicConditionEditor
              condition={local.composition}
              onChange={(next) => update({ composition: next })}
              requirementIds={requirementIds}
            />
          )}

          {(local.composition?.__type__ === "AllComposition" || local.composition?.__type__ === "AnyComposition") && (
            <div className="workshop-composition-group">
              {(local.composition as { components: AtomicConditionDoc[] }).components.map((c, idx) => (
                <AtomicConditionEditor
                  key={idx}
                  condition={c}
                  requirementIds={requirementIds}
                  onChange={(next) => {
                    const comp = local.composition as any;
                    const components = comp.components.slice();
                    components[idx] = next;
                    update({ composition: { ...comp, components } });
                  }}
                  onRemove={
                    (local.composition as { components: AtomicConditionDoc[] }).components.length > 1
                      ? () => {
                          const comp = local.composition as any;
                          update({ composition: { ...comp, components: comp.components.filter((_: unknown, i: number) => i !== idx) } });
                        }
                      : undefined
                  }
                />
              ))}
              {editable && (
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => {
                    const comp = local.composition as any;
                    update({
                      composition: { ...comp, components: [...comp.components, newAtomicCondition(`condition_${comp.components.length + 1}`)] },
                    });
                  }}
                >
                  + Add component
                </button>
              )}
            </div>
          )}

          {local.composition?.__type__ === "SequenceComposition" && (
            <div className="workshop-composition-group">
              {local.composition.components.map((sc, idx) => (
                <div key={idx} className="workshop-sequence-item">
                  <span className="mono">#{sc.sequence_index}</span>
                  <AtomicConditionEditor
                    condition={sc.component}
                    requirementIds={requirementIds}
                    onChange={(next) => {
                      const comp = local.composition as any;
                      const components = comp.components.slice();
                      components[idx] = { ...components[idx], component: next };
                      update({ composition: { ...comp, components } });
                    }}
                  />
                </div>
              ))}
              <div className="form-row">
                <label className="form-field">
                  Ordering window (seconds)
                  <input
                    type="number"
                    value={local.composition.ordering_window_seconds}
                    onChange={(e) => update({ composition: { ...(local.composition as any), ordering_window_seconds: Number(e.target.value) } })}
                  />
                </label>
                <label className="form-field">
                  Tie semantics
                  <select
                    value={local.composition.tie_semantics}
                    onChange={(e) => update({ composition: { ...(local.composition as any), tie_semantics: e.target.value } })}
                  >
                    <option value="TIES_PERMITTED">TIES_PERMITTED</option>
                    <option value="TIES_BREAK_ORDER">TIES_BREAK_ORDER</option>
                  </select>
                </label>
              </div>
              {editable && (
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => {
                    const comp = local.composition as any;
                    update({
                      composition: {
                        ...comp,
                        components: [
                          ...comp.components,
                          { sequence_index: comp.components.length, component: newAtomicCondition(`condition_${comp.components.length + 1}`) },
                        ],
                      },
                    });
                  }}
                >
                  + Add sequence step
                </button>
              )}
            </div>
          )}

          {local.composition?.__type__ === "ContextTriggerComposition" && (
            <div className="workshop-composition-group">
              <p className="workshop-context-trigger-label">CONTEXT (must hold):</p>
              <AtomicConditionEditor
                condition={local.composition.context}
                requirementIds={requirementIds}
                onChange={(next) => update({ composition: { ...(local.composition as any), context: next } })}
              />
              <p className="workshop-context-trigger-label">TRIGGER (fires within context validity):</p>
              <AtomicConditionEditor
                condition={local.composition.trigger}
                requirementIds={requirementIds}
                onChange={(next) => update({ composition: { ...(local.composition as any), trigger: next } })}
              />
              <label className="form-field">
                Context validity — expiry mode
                <select
                  value={local.composition.context_validity.mode}
                  onChange={(e) =>
                    update({
                      composition: {
                        ...(local.composition as any),
                        context_validity: { ...(local.composition as any).context_validity, mode: e.target.value },
                      },
                    })
                  }
                >
                  <option value="NOT_APPLICABLE">NOT_APPLICABLE</option>
                  <option value="NEVER">NEVER</option>
                  <option value="FRAMES">FRAMES</option>
                  <option value="DURATION">DURATION</option>
                </select>
              </label>
            </div>
          )}
        </div>

        {/* Intrabar ambiguity / setup expiry */}
        <div className="form-row">
          <label className="form-field">
            Intrabar ambiguity policy
            <select
              disabled={!editable}
              value={local.intrabar_ambiguity_policy ?? "NOT_APPLICABLE"}
              onChange={(e) => update({ intrabar_ambiguity_policy: e.target.value as IntrabarAmbiguityPolicy })}
            >
              <option value="NOT_APPLICABLE">NOT_APPLICABLE</option>
              <option value="CONSERVATIVE_SL_FIRST">CONSERVATIVE_SL_FIRST</option>
            </select>
          </label>
          <label className="form-field">
            Setup expiry mode
            <select
              disabled={!editable}
              value={local.setup_expiry?.mode ?? "NOT_APPLICABLE"}
              onChange={(e) =>
                update({
                  setup_expiry: {
                    __type__: "ExpirySpec",
                    mode: e.target.value as ExpiryMode,
                    frame_count: local.setup_expiry?.frame_count ?? null,
                    finest_bound_timeframe: local.setup_expiry?.finest_bound_timeframe ?? null,
                    duration_seconds: local.setup_expiry?.duration_seconds ?? null,
                  },
                })
              }
            >
              <option value="NOT_APPLICABLE">NOT_APPLICABLE</option>
              <option value="NEVER">NEVER</option>
              <option value="FRAMES">FRAMES</option>
              <option value="DURATION">DURATION</option>
            </select>
          </label>
        </div>

        {/* Exit rules */}
        <div>
          <h3 className="workshop-subheading">Exit rules</h3>
          {local.exit_rules.length === 0 ? (
            <p style={{ fontSize: 12.5, color: "var(--ink-faint)" }}>No exit rules defined.</p>
          ) : (
            local.exit_rules.map((rule, idx) => (
              <AtomicConditionEditor
                key={idx}
                condition={rule}
                requirementIds={requirementIds}
                onChange={(next) => {
                  const rules = local.exit_rules.slice();
                  rules[idx] = next;
                  update({ exit_rules: rules });
                }}
                onRemove={() => update({ exit_rules: local.exit_rules.filter((_, i) => i !== idx) })}
              />
            ))
          )}
          {editable && (
            <button
              type="button"
              className="button button--secondary"
              onClick={() => update({ exit_rules: [...local.exit_rules, newAtomicCondition(`exit_${local.exit_rules.length + 1}`)] })}
            >
              + Add exit rule
            </button>
          )}
        </div>

        {editable && (
          <div className="row-actions">
            <button type="button" className="button" onClick={save} disabled={!dirty || saving}>
              {saving ? "Saving…" : "Save specification"}
            </button>
          </div>
        )}
        {conflict && (
          <div className="form-error" role="alert">
            <p>{conflict}</p>
            <button type="button" className="button button--secondary" onClick={onReloadDraft}>
              Reload latest draft
            </button>
          </div>
        )}

        {/* Advanced read-only JSON view */}
        <div>
          <button type="button" className="button button--secondary" onClick={() => setShowJson((v) => !v)}>
            {showJson ? "Hide" : "Show"} advanced canonical JSON (read-only)
          </button>
          {showJson && <pre className="workshop-json-view">{JSON.stringify(draft, null, 2)}</pre>}
        </div>
      </div>
    </section>
  );
}
