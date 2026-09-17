"""Amendment A-001 (PID-001 §1a) — ResearchRun instrument/timeframe binding
and run-title construction.
"""
import pytest

from darwin.core.errors import RunBindingError
from darwin.core.evidence import EvidenceLevel
from darwin.hermes.contract import Timeframe
from darwin.research_store.run_binding import build_run_title, create_research_run


def test_build_run_title_contains_all_mandatory_semantic_content():
    title = build_run_title(
        instrument="XAU_USD", timeframe=Timeframe.H1, run_type="ATHENA",
        strategy_title="London Breakout", version_label="v3",
    )
    assert "XAU_USD" in title
    assert "H1" in title
    assert "London Breakout" in title
    assert "v3" in title
    assert "ATHENA" in title


def test_build_run_title_accepts_string_timeframe():
    title = build_run_title(instrument="EUR_USD", timeframe="M15", run_type="APOLLO")
    assert "EUR_USD" in title
    assert "M15" in title
    assert "APOLLO" in title


def test_create_research_run_matching_dataset_succeeds():
    run = create_research_run(
        result_kind=EvidenceLevel.ATHENA_RESULT, engine="athena", build_version="test",
        status="RUNNING", instrument="XAU_USD", instrument_definition_id="def-xau-v1",
        timeframe=Timeframe.H1, run_type="ATHENA",
        dataset_id="d1", dataset_instrument="XAU_USD", dataset_timeframe=Timeframe.H1,
        dataset_instrument_definition_id="def-xau-v1",
    )
    assert run.instrument == "XAU_USD"
    assert run.instrument_definition_id == "def-xau-v1"
    assert run.timeframe == "H1"
    assert run.dataset_id == "d1"
    assert "XAU_USD" in run.display_title


def test_create_research_run_rejects_instrument_definition_mismatch():
    """Amendment A-002: instrument-definition identity is checked the same
    way instrument/timeframe already are.
    """
    with pytest.raises(RunBindingError):
        create_research_run(
            result_kind=EvidenceLevel.APOLLO_PROOF, engine="apollo", build_version="test",
            status="RUNNING", instrument="XAU_USD", instrument_definition_id="def-xau-v2",
            timeframe=Timeframe.H1, run_type="APOLLO",
            dataset_id="d1", dataset_instrument="XAU_USD", dataset_timeframe=Timeframe.H1,
            dataset_instrument_definition_id="def-xau-v1",
        )


def test_create_research_run_without_dataset_is_not_checked():
    """No dataset bound yet -- nothing to mismatch against."""
    run = create_research_run(
        result_kind=EvidenceLevel.SOURCE_CLAIM, engine="scout", build_version="test",
        status="DISCOVERED", instrument="GBP_USD", instrument_definition_id="def-gbp-v1",
        timeframe=Timeframe.D1, run_type="SCOUT",
    )
    assert run.instrument == "GBP_USD"
    assert run.dataset_id is None


def test_create_research_run_rejects_instrument_mismatch():
    with pytest.raises(RunBindingError):
        create_research_run(
            result_kind=EvidenceLevel.APOLLO_PROOF, engine="apollo", build_version="test",
            status="RUNNING", instrument="EUR_USD", instrument_definition_id="def-eur-v1",
            timeframe=Timeframe.H1, run_type="APOLLO",
            dataset_id="d1", dataset_instrument="XAU_USD", dataset_timeframe=Timeframe.H1,
        )


def test_create_research_run_rejects_timeframe_mismatch():
    with pytest.raises(RunBindingError):
        create_research_run(
            result_kind=EvidenceLevel.APOLLO_PROOF, engine="apollo", build_version="test",
            status="RUNNING", instrument="XAU_USD", instrument_definition_id="def-xau-v1",
            timeframe=Timeframe.M15, run_type="APOLLO",
            dataset_id="d1", dataset_instrument="XAU_USD", dataset_timeframe=Timeframe.H1,
        )


def test_create_research_run_instrument_mismatch_error_names_both_values():
    with pytest.raises(RunBindingError, match="EUR_USD.*XAU_USD"):
        create_research_run(
            result_kind=EvidenceLevel.APOLLO_PROOF, engine="apollo", build_version="test",
            status="RUNNING", instrument="EUR_USD", instrument_definition_id="def-eur-v1",
            timeframe=Timeframe.H1, run_type="APOLLO",
            dataset_id="d1", dataset_instrument="XAU_USD", dataset_timeframe=Timeframe.H1,
        )
