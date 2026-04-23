# Sprint T — Sparse T1 TE Path 1 probe sweep (2026-04-23)

**Sprint**: T — 6-country sparse T1 curves sweep (AU/NZ/CH/SE/NO/DK).
**Brief**: `docs/planning/week10-sprint-t-sparse-t1-sweep-au-nz-ch-se-no-dk-brief.md`.
**ADR**: ADR-0009 v2.2 — S1/S2 classifier as binary triage (first
large-scale application post-Sprint-M codification).
**Probe date**: 2026-04-23 (window `d1=2024-01-01`, `d2=2026-04-22`).
**Executor**: CC (Claude Code), full autonomy per SESSION_CONTEXT.
**Outcome**: **1 S1 PASS (AU) / 5 S2 HALT-0 (NZ/CH/SE/NO/DK)** — below
brief §1 hypothesis (3-5 PASS). Critical pattern-library signal (see §8).

---

## 1. Method

Per ADR-0009 v2 + v2.2 canonical cascade, replicating Sprint H/I/M
discipline:

1. `/search/{country}%20government%20bond` authoritative listing →
   baseline symbol set.
2. Per-tenor `/markets/historical/{symbol}?...&d1=2024-01-01&d2=2026-04-22`
   sweep against candidate naming permutations (`YR` / `Y` / bare
   number; `:IND` / `:GOV` suffix quirks per Sprint H/M precedent).
3. S1/S2 classifier (ADR-0009 v2.2):
   - **S1 PASS**: ≥6 distinct daily tenors, each ≥500 obs, LastUpdate
     ≤7 days stale, ≥2 short + 2 mid + 2 long tenors (NSS structural
     coverage).
   - **S2 HALT-0**: <6 tenors OR structural gap blocking Svensson fit.
     Defer to Path 2 (national CB) via dedicated CAL.

Total TE calls: ~104 (6 `/search` + 98 per-tenor permutations). Well
within budget (27% baseline Day 3 + ~2% = ~29% post-probe; below
brief §2.3 HALT-pre-flight threshold 45%).

---

## 2. Australia (AU) — S1 PASS

### 2.1 /search authoritative listing

TE `/search/australia%20government%20bond` returned 8 bond symbols
(plus `aus.ge.per.rnk.*` non-bond perception-rank entries):

```
GACGB1Y:IND, GACGB2Y:IND, GACGB3Y:IND, GACGB5Y:IND,
GACGB7Y:IND, GACGB10:IND, GACGB20Y:IND, GACGB30Y:IND
```

### 2.2 Per-tenor sweep result

| Tenor | Symbol | n obs | First | Latest |
|---|---|---|---|---|
| 1M  | — (probe-empty `GACGB1M:IND`) | 0 | — | — |
| 3M  | — (probe-empty `GACGB3M:IND`) | 0 | — | — |
| 6M  | — (probe-empty `GACGB6M:IND`) | 0 | — | — |
| 1Y  | `GACGB1Y:IND` | 616 | 2024-01-01 | 2026-04-22 |
| 2Y  | `GACGB2Y:IND` | 611 | 2024-01-01 | 2026-04-22 |
| 3Y  | `GACGB3Y:IND` | 611 | 2024-01-01 | 2026-04-22 |
| 5Y  | `GACGB5Y:IND` | 614 | 2024-01-01 | 2026-04-22 |
| 7Y  | `GACGB7Y:IND` | 612 | 2024-01-01 | 2026-04-22 |
| 10Y | `GACGB10:IND` (bare — IT/GB quirk echo) | 608 | 2024-01-01 | 2026-04-22 |
| 15Y | — (probe-empty `GACGB15Y:IND`) | 0 | — | — |
| 20Y | `GACGB20Y:IND` | 624 | 2024-01-01 | 2026-04-22 |
| 30Y | `GACGB30Y:IND` | 623 | 2024-01-01 | 2026-04-22 |

**AU total: 8 tenors** covering 1Y–30Y. Every tenor ≥ 608 obs,
every latest 2026-04-22 (1 day stale — well within ≤7-day window).

### 2.3 AU naming quirk

`GACGB` family is **mixed-suffix**: `Y` suffix for 1Y–7Y + 20Y + 30Y;
bare number for 10Y (`GACGB10:IND`, not `GACGB10Y` or `GACGB10YR`).
Empirically analogous to GB (`GUKG10:IND` bare; GUKG{n}Y:IND for most
others) + IT (`GBTPGR10:IND` bare among `GBTPGR{n}Y:IND` family). **Do
not "normalise"** — each entry verified via both `/search` + round-trip.

### 2.4 AU structural coverage

- **Short (≤2Y)**: 1Y, 2Y ✓
- **Mid (3Y–7Y)**: 3Y, 5Y, 7Y ✓ (3 tenors)
- **Long (≥10Y)**: 10Y, 20Y, 30Y ✓

Short-end gap (1M/3M/6M all empty) is suboptimal vs IT (1M–30Y full)
but identical to PT precedent (3M–30Y with 1M+15Y structural gaps;
shipped S1 post-Sprint-M). Svensson tails the short end naturally;
1Y anchor is sufficient. 15Y gap is filled by interpolation between
10Y + 20Y (NSS parametric handles this cleanly).

### 2.5 AU decision: **S1 PASS**

- 8 tenors ≥ 6 threshold ✓
- all ≥ 500 obs (min 608) ✓
- all latest ≤ 2 days stale ✓
- structural coverage 2+3+3 (short/mid/long) ≥ 2+2+2 floor ✓
- cohorts cleanly with GB (12)/IT (12)/PT (10)/FR (10)/JP (9)/ES (9)/CA (6)

**Proceed** with C3 (te.py AU symbols) + C4 (T1 tuple 10 → 11) +
C5 (tests) + C6 (backfill Apr 21-23).

---

## 3. New Zealand (NZ) — S2 HALT-0

### 3.1 /search authoritative listing

TE `/search/new-zealand%20government%20bond` returned 2 bond symbols:

```
GNZGB10:IND, GNZGB2:GOV
```

### 3.2 Per-tenor sweep result

| Tenor | Symbol | n obs | First | Latest |
|---|---|---|---|---|
| 1Y  | `GNZGB1:IND` (bare — not in /search) | 531 | 2024-01-03 | 2026-04-22 |
| 2Y  | `GNZGB2:GOV` (`:GOV` suffix quirk) | 587 | 2024-01-03 | 2026-04-22 |
| 10Y | `GNZGB10:IND` | 599 | 2024-01-02 | 2026-04-22 |

All variants `GNZGB{n}Y:IND`, `GNZGB{n}Y:GOV`, `GNZGB{n}YR:IND`,
`GNZGB{n}:IND`, `GNZGB{n}:GOV` probed for 3Y/5Y/7Y/15Y/20Y/30Y —
uniformly empty. No 1M/3M/6M tenor either.

### 3.3 NZ decision: **S2 HALT-0**

- 3 tenors < 6 threshold ❌
- Quality per-tenor is high (all ≥ 531 obs, all latest 2026-04-22)
  but insufficient breadth for Svensson.
- Nelson-Siegel 4-knot minimum is theoretically 4 tenors so even NS
  is unavailable (3 < 4).

### 3.4 NZ pattern-library discovery

**`GNZGB1:IND` was NOT in `/search` output** but was returned via
per-tenor sweep (531 obs, live-daily cadence). Pattern-library
implication: **`/search` is high-recall but not exhaustive**; per-tenor
sweep still adds ~1 symbol per sparse T1 country. Amendment candidate
for ADR-0009 v2.3: retain per-tenor sweep discipline even after
`/search` enumerated (cost is low — 12 calls — value is empirical
ground truth).

**Open**: `CAL-CURVES-NZ-PATH-2` — RBNZ (Reserve Bank of New Zealand)
statistics portal probe Week 11+ (bond yields table B2 candidate).

---

## 4. Switzerland (CH) — S2 HALT-0

### 4.1 /search authoritative listing

```
GSWISS10:IND, GSWISS2:GOV
```

### 4.2 Per-tenor sweep result

| Tenor | Symbol | n obs | First | Latest |
|---|---|---|---|---|
| 2Y  | `GSWISS2:GOV` | 584 | 2024-01-03 | 2026-04-22 |
| 10Y | `GSWISS10:IND` | 583 | 2024-01-03 | 2026-04-22 |

Probed `GSWISS{n}Y:IND`, `GSWISS{n}:IND`, `GSWISS3M:IND`, `GSWISS6M:IND`
for 1Y/3Y/5Y/7Y/15Y/20Y/30Y/3M/6M — uniformly empty. `/search` was
exhaustive for CH.

### 4.3 CH decision: **S2 HALT-0**

- 2 tenors < 6 threshold ❌ (also < 4 NS floor)
- Both tenors high-quality (≥ 583 obs, all latest 2026-04-22) but
  structurally incomplete.
- CHF haven-bid hypothesis (brief §1 HIGH probability ~75%) **refuted**
  by TE coverage reality.

**Open**: `CAL-CURVES-CH-PATH-2` — SNB Stats Portal probe Week 11+
(`data.snb.ch` CHF yield curves).

---

## 5. Sweden (SE) — S2 HALT-0

### 5.1 /search authoritative listing

```
GSGB10YR:GOV, GSGB2YR:GOV
```

### 5.2 Per-tenor sweep result

| Tenor | Symbol | n obs | First | Latest |
|---|---|---|---|---|
| 2Y  | `GSGB2YR:GOV` | 580 | 2024-01-02 | 2026-04-22 |
| 10Y | `GSGB10YR:GOV` | 589 | 2024-01-01 | 2026-04-22 |

Probed `GSGB{n}YR:GOV`, `GSGB{n}Y:IND`, `GSGB3M:IND`, `GSGB6M:IND`
for 1Y/3Y/5Y/7Y/15Y/20Y/30Y/3M/6M — uniformly empty. `/search`
exhaustive.

### 5.3 SE decision: **S2 HALT-0**

- 2 tenors < 6 threshold ❌
- Nordic liquidity hypothesis (brief §1 MEDIUM-HIGH ~70%) refuted.
- Both tenors `:GOV` suffix — uniform (unlike NZ's mixed `:IND`+`:GOV`).

**Open**: `CAL-CURVES-SE-PATH-2` — Riksbank statistics portal probe
Week 11+ (`www.riksbank.se/en-gb/statistics/`).

---

## 6. Norway (NO) — S2 HALT-0

### 6.1 /search authoritative listing

```
GNOR10YR:GOV, NORYIELD52W:GOV, NORYIELD6M:GOV
```

### 6.2 Per-tenor sweep result

| Tenor | Symbol | n obs | First | Latest |
|---|---|---|---|---|
| 6M   | `NORYIELD6M:GOV` (different prefix family) | 585 | 2024-01-02 | 2026-04-22 |
| 52W  | `NORYIELD52W:GOV` (~1Y equivalent) | 587 | 2024-01-01 | 2026-04-22 |
| 10Y  | `GNOR10YR:GOV` | 582 | 2024-01-02 | 2026-04-22 |

Probed `GNOR{n}YR:GOV`, `NORYIELD{n}Y:GOV`, `NORYIELD3M:GOV` for all
standard tenors — only the three listed survived.

### 6.3 NO naming quirk

**Two distinct prefix families in same country feed**:

- `GNOR{n}YR:GOV` (Bloomberg-style) covers 10Y only
- `NORYIELD{n}M:GOV` / `NORYIELD52W:GOV` (NST / Norwegian-specific
  convention) covers short-end 6M + 52W

No T1 precedent for this split (Sprint H IT/ES, Sprint I FR, Sprint M
PT all stayed in one `G*` family). Pattern-library amendment candidate
v2.3: "TE connector naming within a single country may span multiple
prefix families; per-tenor sweep must span both prefix candidates."

### 6.4 NO decision: **S2 HALT-0**

- 3 tenors < 6 threshold ❌
- 52W is semantically 1Y-equivalent (but labelled 52W per Norwegian
  convention); using 52W as 1Y is a minor reinterpretation.
- Sovereign wealth offset hypothesis (brief §1 MEDIUM ~55%) **validated**
  (smaller NOK sovereign market → thinner TE coverage).

**Open**: `CAL-CURVES-NO-PATH-2` — Norges Bank statistics portal
probe Week 11+ (`www.norges-bank.no/en/topics/Statistics/`).

---

## 7. Denmark (DK) — S2 HALT-0

### 7.1 /search authoritative listing

```
GDGB10YR:GOV, GDGB2YR:GOV
```

### 7.2 Per-tenor sweep result

| Tenor | Symbol | n obs | First | Latest |
|---|---|---|---|---|
| 2Y  | `GDGB2YR:GOV` | 592 | 2024-01-02 | 2026-04-22 |
| 10Y | `GDGB10YR:GOV` | 598 | 2024-01-02 | 2026-04-22 |

Probed `GDGB{n}YR:GOV`, `GDGB{n}Y:IND`, `GDGB3M:IND`, `GDGB6M:IND`
for 1Y/3Y/5Y/7Y/15Y/20Y/30Y/3M/6M — uniformly empty. `/search`
exhaustive.

### 7.3 DK decision: **S2 HALT-0**

- 2 tenors < 6 threshold ❌
- EUR-peg hypothesis (brief §1 MEDIUM ~60%) **partially validated**
  (peg structure does not translate to TE tenor breadth).
- Both tenors `:GOV` suffix — mirrors SE Nordic convention.

**Open**: `CAL-CURVES-DK-PATH-2` — Danmarks Nationalbanken statsbank
probe Week 11+ (`nationalbanken.statbank.dk`; Nationalbanken cascade
connector already shipped Sprint Y-DK for policy rate, so partial
infra exists — can extend to yield-curve wrapper).

---

## 8. ADR-0009 v2.2 empirical ledger update

### 8.1 Per-country classifications

| Country | Tenors | Classification | Decision | Path 2 CAL |
|---|---|---|---|---|
| AU | 8 (1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y) | **S1** | PASS ship | — |
| NZ | 3 (1Y, 2Y, 10Y) | **S2** | HALT-0 | `CAL-CURVES-NZ-PATH-2` |
| CH | 2 (2Y, 10Y) | **S2** | HALT-0 | `CAL-CURVES-CH-PATH-2` |
| SE | 2 (2Y, 10Y) | **S2** | HALT-0 | `CAL-CURVES-SE-PATH-2` |
| NO | 3 (6M, 52W, 10Y) | **S2** | HALT-0 | `CAL-CURVES-NO-PATH-2` |
| DK | 2 (2Y, 10Y) | **S2** | HALT-0 | `CAL-CURVES-DK-PATH-2` |

### 8.2 Cumulative ADR-0009 ledger post-Sprint-T

TE Path 1 decisive outcomes (Sprint H/I/M/T):

- **PASS (inversions — no national-CB Path 2 needed)**: IT (12),
  ES (9), FR (10), PT (10), **AU (8)** → **5 inversions**.
- **HALT-0 (Path 2 warranted)**: NL (4, Sprint M), NZ (3), CH (2),
  SE (2), NO (3), DK (2) → **6 non-inversions**.

### 8.3 Hypothesis accuracy assessment (brief §1 table)

| Country | Hypothesis | Actual | Accuracy |
|---|---|---|---|
| AU | HIGH ~80% | S1 PASS 8 tenors | ✓ correct |
| NZ | MEDIUM ~60% | S2 HALT-0 3 tenors | ✗ over-optimistic |
| CH | HIGH ~75% | S2 HALT-0 2 tenors | ✗ over-optimistic |
| SE | MEDIUM-HIGH ~70% | S2 HALT-0 2 tenors | ✗ over-optimistic |
| NO | MEDIUM ~55% | S2 HALT-0 3 tenors | ✗ over-optimistic |
| DK | MEDIUM ~60% | S2 HALT-0 2 tenors | ✗ over-optimistic |

**Hit rate: 1/6 (17%)**. Hypothesis was systematically biased toward
"bigger sovereign market → better TE coverage" — refuted for NZ/CH/SE/NO/DK.
The underlying driver for TE coverage appears to be **English-language
reporting + Bloomberg/Reuters primary-market desk presence**, not
sovereign AUM. AU clears it (ACGB is actively followed by offshore
real-money accounts); CHF/SEK/NOK/DKK trade primarily via local dealers.

Pattern-library signal: **sparse-T1 ≠ mid-tier-T1 liquidity**. Updated
mental model for Week 11+ probe targeting.

---

## 9. Pattern library amendment candidates (ADR-0009 v2.3)

### 9.1 `/search` endpoint is high-recall, not exhaustive

NZ's `GNZGB1:IND` (531 obs, daily-live) was not in `/search` output
but was found via per-tenor sweep. Amendment: **retain per-tenor
sweep even after `/search` enumeration** — cost is ~12 calls, value
is ground-truth coverage. Do not truncate probe scope at `/search`.

### 9.2 Multi-prefix families within a single country

NO spans two prefix families: `GNOR{n}YR:GOV` + `NORYIELD{n}M:GOV`.
No prior T1 precedent. Amendment: **probe MUST sweep all plausible
prefix candidates**, not just the dominant Bloomberg-style `G{ISO}{*}`
prefix. For any country where `/search` returns ≥2 distinct prefix
families, log both in the probe result matrix.

### 9.3 Systematic hypothesis bias

Brief §1 probability estimates were too high for sparse-T1 countries
(predicted 3-5 PASS, observed 1 PASS). Amendment: **default sparse-T1
probability to ~25-30%** (not 55-80%) until empirical evidence
updates the prior. The "mid-tier-T1 = periphery EA" cohort (IT/ES/FR/PT)
enjoys EA-sovereign-market standardisation; non-EA sparse T1 does not.

---

## 10. TE quota impact

Calls made by this probe:

- `/search` × 6 countries = 6 calls
- AU per-tenor sweep (12 tenors + 0 alt) = 12 calls
- NZ per-tenor sweep (13 primary + 9 alt) = 22 calls
- CH per-tenor sweep (11 primary + 9 alt) = 20 calls
- SE per-tenor sweep (14 candidates) = 14 calls
- NO per-tenor sweep (16 candidates) = 16 calls
- DK per-tenor sweep (14 candidates) = 14 calls

**Total Sprint T probe: ~104 TE calls.** Within brief §2.3 ceiling
(expected 150-200, ceiling 45% April consumption). Estimated quota
after probe: ~29% (27% baseline + ~2%). Zero HALT-pre-flight triggered.

---

## 11. Sprint T downstream actions (post-probe)

| Country | Path 1 | Action | Commits |
|---|---|---|---|
| AU | PASS 8 tenors | Ship via te.py + daily_curves tuple 10 → 11 | C3 + C4 + C5 + C6 |
| NZ | HALT-0 3 tenors | Skip C3-C6. Open `CAL-CURVES-NZ-PATH-2` Week 11. | — |
| CH | HALT-0 2 tenors | Skip C3-C6. Open `CAL-CURVES-CH-PATH-2` Week 11. | — |
| SE | HALT-0 2 tenors | Skip C3-C6. Open `CAL-CURVES-SE-PATH-2` Week 11. | — |
| NO | HALT-0 3 tenors | Skip C3-C6. Open `CAL-CURVES-NO-PATH-2` Week 11. | — |
| DK | HALT-0 2 tenors | Skip C3-C6. Open `CAL-CURVES-DK-PATH-2` Week 11. | — |

### 11.1 TE_YIELD_CURVE_SYMBOLS AU entry (shipping in C3)

```python
"AU": {
    "1Y":  "GACGB1Y:IND",
    "2Y":  "GACGB2Y:IND",
    "3Y":  "GACGB3Y:IND",
    "5Y":  "GACGB5Y:IND",
    "7Y":  "GACGB7Y:IND",
    "10Y": "GACGB10:IND",   # bare — IT/GB quirk echo
    "20Y": "GACGB20Y:IND",
    "30Y": "GACGB30Y:IND",
},
```

### 11.2 daily_curves T1 tuple extension (shipping in C4)

```python
T1_CURVES_COUNTRIES = ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR", "PT", "AU")
# 11 countries — NZ/CH/SE/NO/DK deferred pending CAL-CURVES-{X}-PATH-2
CURVE_SUPPORTED_COUNTRIES = frozenset({"US","DE","EA","GB","JP","CA","IT","ES","FR","PT","AU"})
```

Deferral map updates (`_DEFERRAL_CAL_MAP`): `AU` removed, 5 remaining
sparse-T1 countries re-pointed from generic `CAL-CURVES-T1-SPARSE` to
per-country `CAL-CURVES-{X}-PATH-2`.

---

*End probe results. AU S1 PASS → C3-C6 ship. 5-country S2 HALT-0 →
CALs opened + ADR-0009 v2.2 addendum.*
