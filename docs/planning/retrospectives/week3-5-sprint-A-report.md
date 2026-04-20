# Week 3.5 Sub-sprint A Report — Connectors foundation

## Summary

- Sub-sprint: 3.5A
- Commits: 1 (`55d9c89`)
- Duration: ~25 min actual / 1.5-2h budget
- Status: COMPLETE

## Commits

| SHA | Scope |
|---|---|
| `55d9c89` | feat(connectors): FMP Ultimate + TE historical yields |

## Files touched

- `src/sonar/config.py` — FMP_API_KEY + TE_API_KEY added (optional, default empty).
- `src/sonar/connectors/fmp.py` — new (171 LOC).
- `src/sonar/connectors/te.py` — new (159 LOC).
- `tests/unit/test_connectors/test_fmp.py` — 7 unit tests.
- `tests/unit/test_connectors/test_te.py` — 7 unit tests.

## Coverage delta

Unit-only run `-m "not integration"`:

| Scope | Before | After |
|---|---|---|
| `src/sonar/connectors` | ~91% (fred 80, shiller 75, ecb 96, bundesbank 87) | ~91% (fmp 100%, te 97.92%, others unchanged) |
| `src/sonar` global | 89.00% | 89.68% (+0.68pp) |

## Tests

- Added: 14 unit (7 FMP + 7 TE).
- Pass rate: 178/178 unit green.
- Failures: none.

## Validation results

| Connector | Endpoint | Live-validated? | Sample 2024-01-02 |
|---|---|---|---|
| FMP `historical-price-eod` (stable v3) | `https://financialmodelingprep.com/stable/historical-price-eod/full` | ✓ yes | SPX close = 4742.83, volume = 3.0B |
| FMP legacy `v3/historical-price-full` | returns HTTP 403 "Legacy Endpoint" | ✗ retired pre-2025-08-31 | n/a — we use `stable` path |
| TE `/markets/historical/<SYM>:IND` | — | ✓ yes | US 10Y close = 3.944% → 394 bps |
| TE bond symbol lookup | `/markets/bond` | ✓ yes | 9 T1 symbols discovered (US, DE, UK, JP, IT, ES, FR, NL, PT) |

## HALT triggers

None fired. §4.1 (FMP rate limit) was a possibility on 30Y+ fetches but
not exercised in this sub-sprint — only recent-dates probes. §4.5 (TE
tenor granularity) constrained: documented only 10Y support, spec'd
`ValueError` on other tenors instead of silent fallback.

## Deviations from brief

### A-1 symbol list extended

Brief §3 3.5A-1 listed ~5 sample indices ("S&P 500, DAX, CAC, FTSE,
NKY, SXXP, PSI-20, IBEX, FTSE MIB, BOVESPA"); implementation ships 12
(adds AEX, SX5E, TPX; kept BOVESPA out of Week 3.5 scope as EM is Week
4+ per brief §1 Out). FMP_INDEX_SYMBOLS is easily extendable.

### TE tenor narrowed to 10Y

Brief §3 3.5A-2 suggested "10Y yields for T1 countries". Implementation
enforces 10Y-only via explicit tenor argument + ValueError on anything
else — avoids the silent-fallback foot-gun if a caller asks for `5Y`
(TE has those symbols but Week 3.5 doesn't need them; expand in Week
4+ if consumers require).

### Dual dataclass pattern

FMP returns `FMPPriceObservation` (new dataclass — price data) instead
of the `Observation` pydantic model (yield-oriented). Documented inline
in the module docstring; CRP overlay consumers will be responsible for
computing daily returns from `close` series at the L2 boundary.

TE sticks to `Observation` with `yield_bps` since 10Y yields are a
natural fit for the existing schema.

## New backlog items

None. CAL-040 (twelvedata/yfinance validation) closed by this work per
the spec sweep that preceded this sprint (`4820b85`).

## Blockers / next steps

None for sub-sprint 3.5B. The FMP + TE foundation unblocks:

- 3.5B ERP (FMP SPX history for EY method, Shiller via separate
  connector).
- 3.5C CRP vol_ratio country-specific (FMP equity returns + TE bond
  yields → rolling stds).
- 3.5F pipeline (k_e composition reads CRP + ERP).

Next: 3.5C (CRP vol_ratio wiring + canonical 7 countries) recommended
before 3.5B — CRP builds on existing compute layer from Week 3 commit
`c1a131d`, minimal new surface. 3.5B ERP has 6 connector sub-tasks
with higher external dependency risk (PDF scrapers, unknown URL
stability) and is the best candidate for a Week 3.5 continuation
session.
