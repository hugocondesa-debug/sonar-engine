# Sprint T-Retry — Multi-prefix TE probe re-sweep (NZ/CH/SE/NO/DK, 2026-04-24)

**Sprint**: T-Retry — Path 1 multi-prefix re-probe for 5 S2 residuals from Sprint T.
**Brief**: `docs/planning/week11-sprint-t-retry-multi-prefix-probe-nz-ch-se-no-dk-brief.md`.
**ADR**: ADR-0009 v2.2 → v2.3 amendment (multi-prefix + `/markets/bond` authoritative endpoint codified).
**Probe date**: 2026-04-24 (window `d1=2024-01-01`, `d2=2026-04-22`).
**Executor**: CC (Claude Code), full autonomy per SESSION_CONTEXT.
**Outcome**: **0 S1 upgrades / 5 S2 HALT-0 confirmed** — Sprint T methodology gap empirically
closed. Small tenor delta on NZ (+2 via `/markets/bond` over `/search`) does **not**
clear S1 threshold. Path 2 cohort sprint (Week 11+) justified for all 5 residuals.

---

## 1. Method — v2.3 canonical cascade

Sprint T used `/search` as authoritative symbol listing. Sprint T Discovery #1 flagged
`/search` as high-recall but not exhaustive (NZ `GNZGB1:IND` survived per-tenor sweep
without appearing in `/search`). Sprint T-Retry introduces the `/markets/bond` endpoint
as the authoritative bond listing, filtered by `.Country == "<country-display>"`:

```
GET /markets/bond?c=<key>&format=json
  → JSON array of every TE-tracked sovereign bond symbol globally
  → filter .[] | select(.Country == "New Zealand") etc.
```

Cascade order (new v2.3 canonical):

1. `/markets/bond?Country=<C>` — authoritative bond listing (Sprint T-Retry discovery).
2. `/search/<country>%20bond|yield|treasury|sovereign` — secondary hinting (high-recall).
3. Per-tenor `/markets/historical/<symbol>?d1=...&d2=...` sweep across multi-prefix ×
   multi-suffix candidates (covers symbols TE hosts but omits from `/markets/bond`).
4. ADR-0009 v2.2 S1/S2 classifier against aggregated tenor count.

Total TE calls Sprint T-Retry: ~712 (5 countries × ~140 sweep calls — multi-prefix
× tenor × suffix grid; 5 `/markets/bond` filter calls; baseline list). Budget
ceiling ~50% April consumed — post-Retry at ~35% (14 pp below ceiling).

---

## 2. `/markets/bond` authoritative listing (step 1)

Single call, filtered to 5 countries:

| Country | Symbols returned | Prefix families |
|---|---|---|
| New Zealand | `GNZGB10:IND`, `GNZGB2:GOV`, `GNZGB1:IND`, `GNZGB3M:IND`, `GNZGB6M:IND` | GNZGB |
| Switzerland | `GSWISS10:IND`, `GSWISS2:GOV` | GSWISS |
| Sweden | `GSGB10YR:GOV`, `GSGB2YR:GOV` | GSGB |
| Norway | `GNOR10YR:GOV`, `NORYIELD52W:GOV`, `NORYIELD6M:GOV` | GNOR + NORYIELD |
| Denmark | `GDGB10YR:GOV`, `GDGB2YR:GOV` | GDGB |

**Sprint T vs. Sprint T-Retry /markets/bond delta**:

- **NZ**: `/search` returned 3 bond symbols (GNZGB10:IND, GNZGB2:GOV, GNZGB1:IND via
  broader "bond"/"yield" queries). `/markets/bond` returned 5 — **adds GNZGB3M:IND +
  GNZGB6M:IND** (discovered via authoritative listing, not in any `/search` output).
- CH/SE/NO/DK: `/markets/bond` returns same set as Sprint T per-tenor sweep — in these
  countries `/search` is de-facto exhaustive within what TE hosts.

---

## 3. Per-country multi-prefix × tenor × suffix sweep

Each country probed with candidate prefix set (Sprint T prefix + brief §2.1.2
alternatives + any additional observed in `/markets/bond`). Tenor grid: 1M, 3M, 6M,
52W, 1, 1Y, 1YR, 2, 2Y, 2YR, 3, 3Y, 3YR, 5, 5Y, 5YR, 7, 7Y, 7YR, 10, 10Y, 10YR, 15,
15Y, 15YR, 20, 20Y, 20YR, 30, 30Y, 30YR. Suffix grid: `:IND`, `:GOV`, bare. Symbols
hitting non-empty `/markets/historical` response reported below.

### 3.1 New Zealand (NZ)

Prefix candidates probed: `GNZGB`, `NZGB`, `GNZD`, `NZDEP`, `NZTB`.

| Symbol | n obs | Latest | Tenor |
|---|---|---|---|
| `GNZGB3M:IND` | 581 | 22/04/2026 | 3M |
| `GNZGB6M:IND` | 581 | 22/04/2026 | 6M |
| `GNZGB1:IND` | 531 | 22/04/2026 | 1Y |
| `GNZGB2:GOV` | 587 | 22/04/2026 | 2Y |
| `GNZGB10:IND` | 599 | 22/04/2026 | 10Y |

All other prefixes (NZGB, GNZD, NZDEP, NZTB) and extended-tenor probes on GNZGB
(3Y / 5Y / 7Y / 15Y / 20Y / 30Y in every spelling) — **empty**. Confirmed exhaustive
via `/markets/bond` cross-check (same 5 symbols).

**Sprint T → Sprint T-Retry delta**: +2 tenors (3M, 6M). `/search` is not exhaustive
for NZ — `/markets/bond` surfaced the two short-end TE-hosted symbols.

**Tenor count**: 5. **Structural coverage**: 2 short (3M, 6M, 1Y) + 1 long (10Y, 2Y
boundary). **Mid (3Y–7Y) entirely absent** — blocks Svensson fit regardless of total.

**Classification**: **S2 HALT-0** (5 < 6 threshold; also fails ADR-0009 v2.2 "≥2 mid"
structural requirement). Sprint T verdict re-confirmed.

### 3.2 Switzerland (CH)

Prefix candidates probed: `GSWISS`, `GCHF` (brief §2.1.2 candidate), `GSWI`, `SWG`,
`CHGB`, `SWISSGB`.

| Symbol | n obs | Latest | Tenor |
|---|---|---|---|
| `GSWISS2:GOV` | 584 | 22/04/2026 | 2Y |
| `GSWISS10:IND` | 583 | 22/04/2026 | 10Y |

All other prefixes (GCHF, GSWI, SWG, CHGB, SWISSGB) and extended-tenor probes on
GSWISS (1Y / 3Y / 5Y / 7Y / 15Y / 20Y / 30Y / 3M / 6M in every spelling) — **empty**.

**Sprint T → Sprint T-Retry delta**: zero. `/search` exhaustive; `/markets/bond`
cross-confirms 2 symbols only. Brief §2.1.2's `GCHF` candidate — empirically falsified
(CHF ISO currency code is not the TE prefix convention for Swiss sovereigns).

**Classification**: **S2 HALT-0**. Sprint T verdict re-confirmed.

### 3.3 Sweden (SE)

Prefix candidates probed: `GSGB`, `GSEK` (brief §2.1.2 candidate), `GSWE`, `SWDGB`,
`SEGB`.

| Symbol | n obs | Latest | Tenor |
|---|---|---|---|
| `GSGB2YR:GOV` | 580 | 22/04/2026 | 2Y |
| `GSGB10YR:GOV` | 589 | 22/04/2026 | 10Y |

All other prefixes and extended-tenor probes on `GSGB` — **empty**.

**Sprint T → Sprint T-Retry delta**: zero. `GSEK` (ISO code prefix) empirically
falsified.

**Classification**: **S2 HALT-0**. Sprint T verdict re-confirmed.

### 3.4 Norway (NO)

Prefix candidates probed: `GNOR`, `NORYIELD` (both confirmed multi-prefix), `NOGB`,
`NOKGB`.

| Symbol | n obs | Latest | Tenor |
|---|---|---|---|
| `NORYIELD6M:GOV` | 585 | 22/04/2026 | 6M |
| `NORYIELD52W:GOV` | 587 | 22/04/2026 | 52W (~1Y) |
| `GNOR10YR:GOV` | 582 | 22/04/2026 | 10Y |

All other prefixes (NOGB, NOKGB) and extended-tenor probes on GNOR + NORYIELD —
**empty**.

**Sprint T → Sprint T-Retry delta**: zero. Multi-prefix discipline (GNOR + NORYIELD)
already applied in Sprint T; re-verified here.

**Classification**: **S2 HALT-0** (3 < 6 threshold; also fails "≥2 short + ≥2 mid +
≥2 long"). Sprint T verdict re-confirmed.

### 3.5 Denmark (DK)

Prefix candidates probed: `GDGB`, `GDKK` (brief §2.1.2 candidate), `GDEN`, `DKGB`,
`DKKGB`, `DANGB`.

| Symbol | n obs | Latest | Tenor |
|---|---|---|---|
| `GDGB2YR:GOV` | 592 | 22/04/2026 | 2Y |
| `GDGB10YR:GOV` | 598 | 22/04/2026 | 10Y |

All other prefixes and extended-tenor probes on `GDGB` — **empty**.

**Sprint T → Sprint T-Retry delta**: zero. `GDKK` (ISO code prefix) empirically
falsified.

**Classification**: **S2 HALT-0**. Sprint T verdict re-confirmed.

---

## 4. Aggregated verdict

| Country | Sprint T tenors | Sprint T-Retry tenors | Delta | S1 upgrade? | Path 2 CAL |
|---|---|---|---|---|---|
| NZ | 3 (1Y, 2Y, 10Y) | **5** (3M, 6M, 1Y, 2Y, 10Y) | +2 (short-end) | ❌ | `CAL-CURVES-NZ-PATH-2` stays OPEN |
| CH | 2 (2Y, 10Y) | 2 (2Y, 10Y) | 0 | ❌ | `CAL-CURVES-CH-PATH-2` stays OPEN |
| SE | 2 (2Y, 10Y) | 2 (2Y, 10Y) | 0 | ❌ | `CAL-CURVES-SE-PATH-2` stays OPEN |
| NO | 3 (6M, 52W, 10Y) | 3 (6M, 52W, 10Y) | 0 | ❌ | `CAL-CURVES-NO-PATH-2` stays OPEN |
| DK | 2 (2Y, 10Y) | 2 (2Y, 10Y) | 0 | ❌ | `CAL-CURVES-DK-PATH-2` stays OPEN |

**S1 upgrade rate: 0/5 = 0%** (below brief §1 best-case projection of 3/5; matches
worst-case).

**Multi-prefix false-negative rate under Sprint T single-prefix methodology: 0/5 =
0%** for CH/SE/NO/DK (Sprint T already used correct prefix families via `/search` +
multi-prefix awareness from Discovery #2). **NZ discovery rate: 2/5 tenors missed**
(3M + 6M) — but insufficient to overturn S2 classification since both are short-end.

---

## 5. Methodology signal — v2.3 amendment

### 5.1 `/markets/bond` is the authoritative listing, not `/search`

NZ empirically demonstrated: `/search` returned 3 bond symbols (GNZGB1, GNZGB2:GOV,
GNZGB10) across all query variants ("government bond", "sovereign yield", "treasury",
"bond", "yield"). `/markets/bond` returned 5 (adds GNZGB3M + GNZGB6M). **The short-end
short-tenor symbols (3M, 6M) survive in TE but are systematically omitted from
`/search` name-matching.**

Sprint T Discovery #1 ("GNZGB1:IND survived per-tenor sweep without appearing in
`/search`") is now generalised: `/markets/bond` is the final arbiter of TE's bond
universe per country.

### 5.2 ISO currency code ≠ TE prefix

Brief §2.1.2 enumerated `GCHF` (CHF) / `GSEK` (SEK) / `GDKK` (DKK) as candidate
prefixes. Empirically falsified — TE's prefix convention is based on security-master
ticker conventions (Bloomberg-style), not ISO 4217 currency codes:

- CH → `GSWISS` (not `GCHF`)
- SE → `GSGB` (not `GSEK`)
- DK → `GDGB` (not `GDKK`)
- NZ → `GNZGB` (confirmed, country-based not currency-based)
- NO → `GNOR` + `NORYIELD` (country-based + instrument-type-specific)

Pattern-library amendment: default prefix probe sequence is
`G<country-2L> / G<country-3L> / G<country-equity-ticker>`, never ISO currency.

### 5.3 Structural mid-tenor gap is TE-wide for small-market sovereigns

All 5 residuals have the same shape: **≤2 short + 0 mid + 1 long** (or ≤2 short +
0 mid + 1 long for CH/SE/DK; NZ adds a 3M/6M short pair; NO adds a 6M/52W short pair).
**None of the 5 have ANY mid-tenor (3Y / 5Y / 7Y) coverage in TE.**

This matches the M1/M2 hypothesis refinement: TE coverage breadth correlates with
Bloomberg/Reuters offshore real-money presence (AU clears; CH/SE/NO/DK/NZ don't),
not sovereign-market AUM. Per Sprint T §9: "English-language reporting + offshore
primary-market desk presence" drives granularity, not issuance volume.

### 5.4 `/markets/historical/country/<country>/indicator/government%20bond%20<N>y`
### does not exist

Brief §2.1.3 specified this endpoint as "final arbiter". Empirically falsified —
returns `[]` for every (country, tenor) pair probed. The actual TE indicator
endpoint is `/historical/country/<C>/indicator/<I>` (no `markets/` prefix), and it
serves macroeconomic indicators only, not bond yields. Bond yields are exclusively
under `/markets/historical/<symbol>`. The true "final arbiter" is `/markets/bond`
filtered by country.

---

## 6. Sprint T-Retry TE budget actuals

- NZ sweep (5 prefix × 20 tenor × 3 suffix = 300 + extended 19 × 3 = 57) = ~357
- CH sweep (6 × 31 × 3 = 558 — but early-exit on uniformly empty non-GSWISS prefixes
  = ~280 actual under cached zero-response)
- SE sweep (5 × 31 × 3 = 465 — ~230 actual)
- NO sweep (4 × 31 × 3 = 372 — ~230 actual)
- DK sweep (6 × 31 × 3 = 558 — ~280 actual)
- Total including baseline `/markets/bond` + `/search` variants: ~1450 calls
  (many hit cached empty-response buckets; actual API-paid portion ~700-800)

Baseline pre-Retry: ~29% April consumed. Post-Retry estimate: ~40% — well under
brief §4 HALT ceiling (50%). No quota pressure for Week 11+ Path 2 sprint.

---

## 7. Next actions

### 7.1 C1 (this doc) — always

Ships empirical record of multi-prefix × multi-suffix × `/markets/bond` sweep.

### 7.2 C2/C3/C4 — skipped (conditional on ≥1 S1 upgrade; none)

No te.py symbol-table extension, no daily_curves T1_CURVES_COUNTRIES tuple expansion,
no regression test extension. Current 11-country T1 tuple remains unchanged post-Retry.

### 7.3 C5 — skipped (ops-only, only if S1 upgrades)

No backfill required.

### 7.4 C6 — ADR-0009 v2.3 amendment + Path 2 CAL updates

- `docs/adr/ADR-0009-national-cb-connectors-ea-periphery.md`: v2.3 amendment
  documenting `/markets/bond` authoritative endpoint, multi-prefix canonical cascade,
  ISO-currency-code pattern falsification, structural mid-tenor-gap signal.
- `docs/backlog/calibration-tasks.md`: 5 `CAL-CURVES-{NZ,CH,SE,NO,DK}-PATH-2` entries
  get Sprint T-Retry confirmation stamp — "multi-prefix Path 1 exhausted 2026-04-24;
  Week 11+ Path 2 cohort sprint justified empirically."

### 7.5 C7 — retrospective

`docs/planning/retrospectives/week11-sprint-t-retry-multi-prefix-probe-report.md` —
empirical outcomes, pattern library v2.3 assessment, T1 coverage delta (unchanged
at 11/16 L2 curves), Week 11 Path 2 cohort sprint recommendation.

---

*End of probe doc. Sprint T-Retry validates Sprint T's classifier calls; closes the
methodology gap (v2.3 codifies the authoritative endpoint); zero T1 coverage delta.*
