# Sprint M — TE Path 1 probe PT + NL (2026-04-23)

**Sprint**: M — Curves PT + NL Probe via TE Path 1.
**Brief**: `docs/planning/week10-sprint-m-curves-pt-nl-brief.md`.
**ADR**: ADR-0009 v2 — National CB Connectors for EA Periphery; TE
Path 1 **mandatory** before Path 2/3 scaffold.
**Probe date**: 2026-04-23 (window `d1=2024-01-01`, `d2=2026-04-22`).
**Executor**: CC (Claude Code), full autonomy per SESSION_CONTEXT.
**Outcome**: **PT PASS / NL HALT-0** (partial ship; 4th ADR-0009 v2
TE-path inversion documented).

---

## 1. Method

Per ADR-0009 v2 + Sprint H (IT + ES) + Sprint I (FR) canonical cascade:
per-tenor `curl` against `https://api.tradingeconomics.com/markets/historical/{symbol}?c={key}&format=json&d1=2024-01-01&d2=2026-04-22`,
iterating candidate symbols for each tenor (1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y,
10Y, 15Y, 20Y, 30Y). Naming candidates probed:

- PT: `GSPT{N}YR:IND`, `GSPT{N}Y:IND`, `GSPT{N}:IND`, and `GSPT{NM}M:IND`
  for sub-year.
- NL: `GNTH{N}YR:IND`, `GNTH{N}Y:IND`, `GNTH{N}:IND`, `GNTH{N}YR:GOV`,
  `GNTH{N}Y:GOV`, and `GNTH{NM}M:IND` for sub-year.

PASS criterion per tenor (brief §2.1): `length >= 500` historical
observations **and** latest observation within 7 days of 2026-04-22 (i.e.
cadence is live-daily). PASS criterion per country: ≥6 tenors pass
(`MIN_OBSERVATIONS_FOR_SVENSSON`).

Cross-validation: TE `/search/{country}%20government%20bond` endpoint
queried for each country as authoritative listing (catches tenors whose
bare symbol-name convention the per-tenor loop missed).

---

## 2. Portugal (PT) — PASS

### 2.1 Per-tenor sweep result

| Tenor | Symbol | n observations | First date | Latest date |
|---|---|---|---|---|
| 1M | — (probe-empty all variants: `GSPT1M:IND`) | 0 | — | — |
| 3M | `GSPT3M:IND` | 588 | 2024-01-02 | 2026-04-22 |
| 6M | `GSPT6M:IND` | 589 | 2024-01-02 | 2026-04-22 |
| 1Y | `GSPT1Y:IND` | 586 | 2024-01-02 | 2026-04-22 |
| 2Y | `GSPT2YR:IND` | 596 | 2024-01-02 | 2026-04-22 |
| 3Y | `GSPT3Y:IND` | 603 | 2024-01-02 | 2026-04-22 |
| 5Y | `GSPT5Y:IND` | 601 | 2024-01-02 | 2026-04-22 |
| 7Y | `GSPT7Y:IND` | 588 | 2024-01-02 | 2026-04-22 |
| 10Y | `GSPT10YR:IND` | 601 | 2024-01-02 | 2026-04-22 |
| 15Y | — (probe-empty all variants) | 0 | — | — |
| 20Y | `GSPT20Y:IND` | 594 | 2024-01-02 | 2026-04-22 |
| 30Y | `GSPT30Y:IND` | 591 | 2024-01-02 | 2026-04-22 |

**PT total: 10 tenors** — full 3M–30Y (missing 1M + 15Y). Every
tenor ≥ 586 observations, every `latest=22/04/2026`. All well above
`MIN_OBSERVATIONS_FOR_SVENSSON=9`; Svensson-capable with headroom.

### 2.2 PT naming quirk

PT's `GSPT` family is **mixed-suffix**: `YR` for 2Y + 10Y, bare `Y` for
1Y / 3Y / 5Y / 7Y / 20Y / 30Y, `M` for sub-year. Empirically identical
in shape to ES (`GSPG*YR`/`GSPG*`) and IT's quirk (mixed `Y` / no-suffix
+ `GBTPGR10` bare on 10Y). **Do not "normalise"** the suffix pattern
— each entry has been empirically verified below via both `/search`
listing and `/markets/historical` round-trip.

### 2.3 PT /search cross-validation

TE `/search/portugal%20government%20bond` returned exactly the 10
symbols probed above (plus the `prt.ge.per.rnk.*` perception-rank
non-bond entries). Zero additional candidates exist for 1M or 15Y —
confirming the two missing tenors are TE-coverage structural gaps
(not a probe-naming miss).

### 2.4 PT decision: **PASS**

- 10 tenors daily (≥ 6 brief §2.1 threshold ✅)
- all ≥ 500 observations (min 586 ≥ 500 ✅)
- all latest ≤ 2 days stale (every `latest=2026-04-22`; today is
  2026-04-23 ✅)
- cohorts cleanly with IT (12 tenors) / ES (9 tenors) / FR (10 tenors)
  prior Sprint H + Sprint I shipments

**Proceed with Commit C3 (te.py PT symbols) + C4 (daily_curves T1 tuple
9 → 10) + C5 (tests) + C6 (backfill + systemd verify).**

---

## 3. Netherlands (NL) — HALT-0

### 3.1 Per-tenor sweep result

| Tenor | Symbol | n observations | First date | Latest date |
|---|---|---|---|---|
| 1M | — (probe-empty) | 0 | — | — |
| 3M | `GNTH3M:IND` | 597 | 2024-01-02 | 2026-04-22 |
| 6M | `GNTH6M:IND` | 595 | 2024-01-02 | 2026-04-22 |
| 1Y | — (probe-empty all of `GNTH1YR:IND`, `GNTH1Y:IND`, `GNTH1:IND`, `GNTH1YR:GOV`, `GNTH1Y:GOV`) | 0 | — | — |
| 2Y | `GNTH2YR:GOV` (note `:GOV` suffix quirk — **unique to NL 2Y**) | 598 | 2024-01-02 | 2026-04-22 |
| 3Y | — (probe-empty all variants) | 0 | — | — |
| 5Y | — (probe-empty all variants) | 0 | — | — |
| 7Y | — (probe-empty all variants) | 0 | — | — |
| 10Y | `GNTH10YR:IND` | 600 | 2024-01-02 | 2026-04-22 |
| 15Y | — (probe-empty all variants) | 0 | — | — |
| 20Y | — (probe-empty all variants) | 0 | — | — |
| 30Y | — (probe-empty all variants) | 0 | — | — |

**NL total: 4 tenors** — 3M + 6M + 2Y + 10Y.

### 3.2 NL /search cross-validation

TE `/search/netherlands%20government%20bond` returned exactly these
4 symbols (plus the `nld.ge.per.rnk.*` non-bond entries). Confirms
TE coverage is structurally only 4 tenors daily. **No probe-naming
miss** — the 8 missing tenors (1M, 1Y, 3Y, 5Y, 7Y, 15Y, 20Y, 30Y) are
TE feed gaps, not convention discoveries.

The `:GOV` suffix on NL 2Y (vs the `:IND` suffix used everywhere else
in both PT and all prior T1 countries) is a TE internal namespace
artifact. Its `Symbol` field in the response payload is still
`GNTH2YR:GOV`, so downstream consumers can key on it; but it's a
standalone quirk worth noting for any future Path 2 fallback logic.

### 3.3 NL decision: **HALT-0**

- 4 tenors daily < 6 threshold ❌ (below `MIN_OBSERVATIONS_FOR_SVENSSON=6`
  brief §2.1 floor)
- Those 4 that *do* pass are high-quality (all ≥ 595 obs, all latest
  2026-04-22) but insufficient for Svensson fitting. NS-min (4 knots)
  is theoretically possible on 4 tenors but is a different methodology
  (Nelson-Siegel instead of Svensson) — outside Sprint M scope.
- Cohorts with the Sprint G-original `HALT-0 all-5-paths-dead` NL
  framing, but **narrows** it to "Path 1 insufficient for Svensson";
  Path 2 (DNB — De Nederlandsche Bank) remains untested.

**Skip Commits C3-C6 for NL. Open CAL-CURVES-NL-DNB-PROBE + ship
ADR-0009 v2 addendum (4th inversion).**

---

## 4. ADR-0009 v2 inversion ledger update

Prior inversions (per Sprint I FR retro + ADR-0009):

1. **IT** (Sprint H, 2026-04-22) — TE PASS 12 tenors; inversion = no
   BdI/MEF cascade needed.
2. **ES** (Sprint H, 2026-04-22) — TE PASS 9 tenors; inversion = no
   BdE/Tesoro cascade needed.
3. **FR** (Sprint I, 2026-04-22) — TE PASS 10 tenors; inversion = no
   BdF Webstat cascade needed.

Sprint M adds:

4. **PT** (2026-04-23) — TE PASS 10 tenors; inversion = no BPstat
   cascade needed. `CAL-CURVES-PT-BPSTAT` closed pre-open.
5. **NL** (2026-04-23) — TE **FAIL** 4 tenors (below Svensson floor);
   **no inversion — Path 1 insufficient**, Path 2 (DNB) warranted.
   `CAL-CURVES-NL-DNB-PROBE` opens Week 11.

ADR-0009 v2 canonical statement holds: **"probe TE Path 1 first; escalate
to Path 2/3 only on empirical Path 1 failure"**. Sprint M is the first
Path 1 failure observed → first non-inversion (Path 2 scaffold
authorised). Addendum shipping at `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md`
§5 "NL HALT-0 Evidence" — see Commit C7.

---

## 5. Sprint M downstream actions (post-probe)

| Country | Path 1 | Action | Commits |
|---|---|---|---|
| PT | PASS 10 tenors | Ship via te.py + daily_curves tuple 9 → 10 | C3 + C4 + C5 + C6 |
| NL | HALT-0 4 tenors | Skip Commits C3-C6. Open CAL-CURVES-NL-DNB-PROBE Week 11. Ship ADR-0009 addendum. | — |

### 5.1 TE_YIELD_CURVE_SYMBOLS PT entry (shipping in C3)

```python
"PT": {
    "3M": "GSPT3M:IND",
    "6M": "GSPT6M:IND",
    "1Y": "GSPT1Y:IND",
    "2Y": "GSPT2YR:IND",
    "3Y": "GSPT3Y:IND",
    "5Y": "GSPT5Y:IND",
    "7Y": "GSPT7Y:IND",
    "10Y": "GSPT10YR:IND",
    "20Y": "GSPT20Y:IND",
    "30Y": "GSPT30Y:IND",
},
```

(1M + 15Y omitted — TE-empty per §2.1; confirmed non-convention miss
via §2.3 `/search` cross-validation.)

### 5.2 daily_curves T1 tuple extension (shipping in C4)

```python
T1_COUNTRIES = ("US", "DE", "EA", "GB", "JP", "CA", "IT", "ES", "FR", "PT")
# 10 countries — NL deferred pending CAL-CURVES-NL-DNB-PROBE
```

---

## 6. TE quota impact

Calls made by this probe:

- PT per-tenor sweep (`:IND` suffix 12 + alt-suffix variants 14) = **26 calls**
- NL per-tenor sweep (`:IND` 12 + alt-suffix 16 + `:GOV` 18) = **46 calls**
- `/search` cross-validation (2 countries) = **2 calls**
- `/markets/historical` pre-flight headers probe = **1 call**

**Total Sprint M probe: ~75 TE calls.** Well within April budget
(baseline 23.32% consumed / 5000 quota per brief §2.2 ⇒ ~3830 remaining
before probe; post-probe ~3755 = 25 % consumed / 75 % remaining).
Zero HALT-pre-flight triggered.

---

*End probe results. PT PASS → C3-C6 ship. NL HALT-0 → CAL-CURVES-NL-DNB-PROBE + ADR-0009 addendum.*
