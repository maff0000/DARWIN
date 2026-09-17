"""ResearchRun creation and instrument/timeframe binding (Amendment A-001,
PID-001 §1a/§20/§22).

This is the only supported way to construct a `ResearchRun`. It enforces,
at creation time rather than as an assumed invariant, that a run's
instrument/timeframe agree with the `MarketDataset` it is bound to, and
builds the immutable human-readable `display_title` (strategy + version +
instrument + timeframe + run type — see §1a "Run title / human visibility").
"""
from __future__ import annotations

from darwin.core.errors import RunBindingError
from darwin.core.evidence import EvidenceLevel
from darwin.core.identities import new_id
from darwin.hermes.contract import Timeframe
from darwin.research_store.models import ResearchRun


def _timeframe_value(timeframe: Timeframe | str) -> str:
    return timeframe.value if isinstance(timeframe, Timeframe) else str(timeframe)


def build_run_title(
    *,
    instrument: str,
    timeframe: Timeframe | str,
    run_type: str,
    strategy_title: str | None = None,
    version_label: str | None = None,
) -> str:
    """`<INSTRUMENT · TIMEFRAME> Strategy Name vN — RUN_TYPE` (§1a). Exact
    punctuation is not architectural; the semantic content (strategy,
    version, instrument, timeframe, run type all visible) is. Not identity
    — UUID/version/dataset identity remains authoritative.
    """
    tf = _timeframe_value(timeframe)
    strategy_part = strategy_title or "Unspecified strategy"
    if version_label:
        strategy_part = f"{strategy_part} {version_label}"
    return f"<{instrument} · {tf}> {strategy_part} — {run_type}"


def create_research_run(
    *,
    result_kind: EvidenceLevel,
    engine: str,
    build_version: str,
    status: str,
    instrument: str,
    timeframe: Timeframe | str,
    run_type: str,
    strategy_title: str | None = None,
    version_label: str | None = None,
    candidate_id: str | None = None,
    version_id: str | None = None,
    dataset_id: str | None = None,
    dataset_instrument: str | None = None,
    dataset_timeframe: Timeframe | str | None = None,
    configuration_fingerprint: str | None = None,
) -> ResearchRun:
    """Construct a `ResearchRun`, rejecting an instrument or timeframe
    mismatch against its bound `MarketDataset` (§1a) rather than silently
    storing it.

    `dataset_instrument`/`dataset_timeframe` are the bound dataset's own
    values (from a `MarketDataset` or persisted `MarketDatasetRecord`) —
    pass them whenever `dataset_id` is supplied so the mismatch can
    actually be checked; a `dataset_id` given without them is not itself
    validated here (the caller vouches for it), but callers with the
    dataset in hand should always pass its instrument/timeframe.
    """
    instrument_tf = _timeframe_value(timeframe)

    if dataset_id is not None:
        if dataset_instrument is not None and instrument != dataset_instrument:
            raise RunBindingError(
                f"Run instrument {instrument!r} does not match bound MarketDataset "
                f"instrument {dataset_instrument!r} (dataset_id={dataset_id})"
            )
        if dataset_timeframe is not None:
            dataset_tf = _timeframe_value(dataset_timeframe)
            if instrument_tf != dataset_tf:
                raise RunBindingError(
                    f"Run timeframe {instrument_tf!r} does not match bound MarketDataset "
                    f"timeframe {dataset_tf!r} (dataset_id={dataset_id})"
                )

    display_title = build_run_title(
        instrument=instrument,
        timeframe=timeframe,
        run_type=run_type,
        strategy_title=strategy_title,
        version_label=version_label,
    )

    return ResearchRun(
        id=new_id(),
        result_kind=result_kind,
        engine=engine,
        build_version=build_version,
        status=status,
        instrument=instrument,
        timeframe=instrument_tf,
        display_title=display_title,
        candidate_id=candidate_id,
        version_id=version_id,
        dataset_id=dataset_id,
        configuration_fingerprint=configuration_fingerprint,
    )
