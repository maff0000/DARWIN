"""Amendment A-003 (PID-001 §1d) — DIKE state / policy-identity binding."""
import pytest

from darwin.core.dike import DikeState
from darwin.core.errors import DikePolicyBindingError
from darwin.core.evidence import EvidenceLevel
from darwin.hermes.contract import Timeframe
from darwin.research_store.run_binding import create_research_run


def test_dike_disabled_run_carries_no_policy_identity():
    run = create_research_run(
        result_kind=EvidenceLevel.ATHENA_RESULT, engine="athena", build_version="test",
        status="RUNNING", instrument="XAU_USD", instrument_definition_id="def-xau-v1",
        timeframe=Timeframe.H1, run_type="ATHENA",
    )
    assert run.dike_state == DikeState.DISABLED
    assert run.dike_policy_id is None
    assert run.dike_policy_version is None
    assert run.dike_policy_fingerprint is None


def test_dike_guarded_run_requires_and_carries_full_policy_identity():
    run = create_research_run(
        result_kind=EvidenceLevel.APOLLO_PROOF, engine="apollo", build_version="test",
        status="RUNNING", instrument="XAU_USD", instrument_definition_id="def-xau-v1",
        timeframe=Timeframe.H1, run_type="APOLLO",
        dike_state=DikeState.GUARDED,
        dike_policy_id="dike-conservative-v1", dike_policy_version="v1",
        dike_policy_fingerprint="f" * 64,
    )
    assert run.dike_state == DikeState.GUARDED
    assert run.dike_policy_id == "dike-conservative-v1"
    assert run.dike_policy_version == "v1"
    assert run.dike_policy_fingerprint == "f" * 64


@pytest.mark.parametrize(
    "missing_field", ["dike_policy_id", "dike_policy_version", "dike_policy_fingerprint"]
)
def test_dike_guarded_missing_any_policy_identity_field_is_rejected(missing_field):
    kwargs = {
        "dike_policy_id": "dike-conservative-v1",
        "dike_policy_version": "v1",
        "dike_policy_fingerprint": "f" * 64,
    }
    kwargs[missing_field] = None
    with pytest.raises(DikePolicyBindingError):
        create_research_run(
            result_kind=EvidenceLevel.APOLLO_PROOF, engine="apollo", build_version="test",
            status="RUNNING", instrument="XAU_USD", instrument_definition_id="def-xau-v1",
            timeframe=Timeframe.H1, run_type="APOLLO",
            dike_state=DikeState.GUARDED, **kwargs,
        )


def test_dike_disabled_carrying_a_policy_identity_field_is_rejected():
    with pytest.raises(DikePolicyBindingError):
        create_research_run(
            result_kind=EvidenceLevel.ATHENA_RESULT, engine="athena", build_version="test",
            status="RUNNING", instrument="XAU_USD", instrument_definition_id="def-xau-v1",
            timeframe=Timeframe.H1, run_type="ATHENA",
            dike_state=DikeState.DISABLED, dike_policy_id="dike-conservative-v1",
        )


def test_dike_policy_binding_error_names_the_missing_fields():
    with pytest.raises(DikePolicyBindingError, match="dike_policy_version"):
        create_research_run(
            result_kind=EvidenceLevel.APOLLO_PROOF, engine="apollo", build_version="test",
            status="RUNNING", instrument="XAU_USD", instrument_definition_id="def-xau-v1",
            timeframe=Timeframe.H1, run_type="APOLLO",
            dike_state=DikeState.GUARDED,
            dike_policy_id="dike-conservative-v1", dike_policy_fingerprint="f" * 64,
        )
