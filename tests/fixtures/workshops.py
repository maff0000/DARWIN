"""Shared PID-004B Workshop test helpers -- mirrors
tests/fixtures/specification_drafts.py's "TEST-controlled fixture data"
discipline. Lives under tests/fixtures because it is test-only scaffolding,
never presented as real research evidence.
"""
from __future__ import annotations

import psycopg

from darwin.core.identities import new_id
from darwin.research_store.models import StrategyCandidate
from darwin.research_store.repositories import StrategyCandidateRepository
from darwin.scout import service as scout_service
from darwin.scout.domain import OriginKind


def new_candidate(conn: psycopg.Connection, *, title: str = "Workshop test candidate") -> str:
    candidate_id = new_id()
    StrategyCandidateRepository(conn).create(StrategyCandidate(id=candidate_id, title=title))
    return candidate_id


def new_user_discovered_discovery(
    conn: psycopg.Connection, *, title: str = "A workshop test discovery",
    source_symbol: str | None = "XAUUSD", origin_url: str | None = "https://example.invalid/strategy/1",
) -> str:
    """A real USER_DISCOVERED SCOUT discovery row -- for tests that need a
    genuine `scout_discoveries.id` to open a Workshop against, and for the
    SCOUT-fidelity/instrument-mapping proofs, which specifically need a
    discovery carrying a raw, uninterpreted `source_symbol` (e.g.
    'XAUUSD'). Routed through the SAME `darwin.scout.service.
    create_manual_discovery` that `darwin.app`'s own
    `/api/v1/scout/discoveries` endpoint uses -- never a hand-rolled
    INSERT that could drift from that function's own snapshot/claim
    bookkeeping."""
    discovery = scout_service.create_manual_discovery(
        conn, origin_kind=OriginKind.USER_DISCOVERED, title=title, source_symbol=source_symbol,
        origin_url=origin_url,
    )
    return str(discovery["id"])


def new_my_idea_discovery(conn: psycopg.Connection, *, title: str = "Matt's own idea") -> str:
    discovery = scout_service.create_manual_discovery(conn, origin_kind=OriginKind.MY_IDEA, title=title)
    return str(discovery["id"])
