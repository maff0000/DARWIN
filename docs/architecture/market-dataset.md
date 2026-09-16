# MarketDataset

## HERMES contract reference

Canonical repository `github.com/maff0000/hermes`, contract commit
`3f90e640c9c9c1f4a22ba4ac586a1d478f35a997` (`darwin/hermes/contract.py`).
Allowed objects: `canonical_candles_m1/m5/m15/h1/h4/d1` and the unified
`canonical_candles`. The timeframe→object mapping is fixed and closed —
no runtime input ever selects a table name.

## In-memory representation

HERMES prices are `DECIMAL(12,5)`. DARWIN converts each to a fixed-point
`int64` by multiplying by `100000` (`darwin/hermes/dataset.py:PRICE_SCALE`)
— an exact operation, never routed through a binary float, so a five-decimal
canonical market fact (including wick `high`/`low`) cannot be silently
altered by floating-point rounding. Timestamps are stored as `int64` UTC
epoch seconds. Volume is `int64`.

Recovering the exact original decimal is `value / 100000` — implemented as
`from_fixed_point()` for anywhere a human-readable/decimal view is needed;
the canonical hot-path representation stays integer throughout.

## Immutability

`MarketDataset` is a frozen dataclass; its underlying NumPy arrays are marked
non-writeable (`arr.flags.writeable = False`) in `__post_init__`. There is no
supported way for a consumer to mutate a loaded dataset in place.

## Fingerprint

`compute_fingerprint()` hashes (SHA-256) the instrument, timeframe, and every
row's `(open_time_epoch_s, open_fp, high_fp, low_fp, close_fp, volume)` tuple
in ascending order — nothing else. It deliberately excludes load timestamp,
Python object identity, database row IDs, `derivation_run_id`, and
host/machine identity, so two independent loads of unchanged HERMES rows for
the same range produce the same fingerprint. Verified by
`tests/unit/test_dataset_fingerprint.py` and by the real HERMES DEV proof
(load twice, compare fingerprints).

## Gap semantics

`compute_gap_summary()` computes the raw fixed-step expected-grid difference
between the requested interval and the actual returned open times. It never
fabricates a candle, never forward-fills, and never invents a trading-calendar
doctrine (weekend/market-closed awareness is deliberately out of scope here —
see PID-001 §18). Whether a given gap pattern invalidates a later experiment
is a decision for that experiment's own specification, not a Foundation rule.

## Wick high/low requirement

`high`/`low` are preserved exactly through the entire path: HERMES row →
`validation.py` (rejects impossible OHLC relationships) →
`dataset.build_market_dataset()` (fixed-point conversion) → the frozen
`MarketDataset.high_fp` / `low_fp` arrays. `MarketDataset.high_low_at(index)`
recovers the exact original decimal losslessly. No close-only approximation
exists anywhere in this path.

## No-SQL-inner-loop invariant

`darwin.hermes.reader.load_market_dataset()` issues exactly one bulk,
parameterised, ascending-ordered SQL query per call. There is no per-candle
query path anywhere in this package. Later ATHENA/APOLLO modules are expected
to receive one `MarketDataset` and iterate it in memory across every
parameter/strategy evaluation in a research workload — re-querying HERMES
per evaluation would be a regression against this invariant, not a
Foundation-authorised pattern.
