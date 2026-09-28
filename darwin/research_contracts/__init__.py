"""PID-006A -- Shared Research/Proof Contracts (docs/pids/PID-006-APOLLO.md
sec5/sec35).

`darwin.research_contracts` holds the IMMUTABLE configuration/governance
under which DARWIN research is performed -- genuinely distinct from
`darwin.specification` (what a strategy MEANS) and from the later,
independent `darwin.apollo` (causal proof engine) and `darwin.athena`
(exploratory evaluator/search engine), neither of which this package
touches:

    darwin.specification       = what a strategy means (existing)
    darwin.research_contracts  = immutable configuration/governance under
                                  which research is performed (THIS package)
    darwin.research_store      = persistence adapters for durable DARWIN
                                  state (existing -- extended, not forked,
                                  by this work package)
    darwin.apollo               = later causal proof engine (untouched stub)
    darwin.athena                = later exploratory evaluator/search engine
                                  (untouched stub)

Dependency direction is one-way and tested
(tests/architecture/test_research_contracts_layering.py):
`darwin.research_contracts` may import from `darwin.specification`;
`darwin.specification` must NEVER import from `darwin.research_contracts`.

Nothing in this package touches HERMES, SQL, market data, historical
replay, simulation, ranking, brokers, the network, an LLM, or arbitrary
code execution (`eval`/`exec`) -- see `darwin.research_contracts.compiler`
and `darwin.research_contracts.capability` for where that boundary is
enforced and tested. Persistence for the artifacts modelled here lives in
`darwin.research_store` (migration 0012), not in this package.
"""
from __future__ import annotations
