# Financial Cycle Score (FCS) — Spec

> Layer L4 · cycle: financial · slug: `financial-fcs` · methodology_version: `FCS_COMPOSITE_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E3)

## 1. Purpose

Compute o **Financial Cycle Score** per `(country, date)` — composite `[0, 100]` agregando F1-F4 (L3 indices) com pesos canónicos `0.30 / 0.25 / 0.25 / 0.20` (manual cap 15.5-15.6). Classifica em 4 regimes (`STRESS / CAUTION / OPTIMISM / EUPHORIA`) com anti-whipsaw hysteresis e emite Bubble Warning overlay quando FCS elevado coincide com BIS credit/property gap extremos (cap 16). Sign convention: **higher = mais euforia / risk-on**.

## 2. Inputs

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |
| `date` | `date` | business day local | param |
| `f1_score_0_100` | `float` | F1 valuations composite | `indices/financial/F1-valuations.f1_valuations.score_normalized` |
| `f2_score_0_100` | `float` | F2 momentum composite | `indices/financial/F2-momentum.f2_momentum.score_normalized` |
| `f3_score_0_100` | `float` | F3 risk-appetite composite | `indices/financial/F3-risk-appetite.f3_risk_appetite.score_normalized` |
| `f4_score_0_100` | `float` \| `None` | F4 positioning (tier-conditional; ver Policy 4) | `indices/financial/F4-positioning.f4_positioning.score_normalized` |
| `country_tier` | `int` | `1..4` per `docs/data_sources/country_tiers.yaml` (canonical per ADR-0005) | config |

### Cross-cycle reads (diagnostic / overlay inputs, NOT composite components)

| Nome | Fonte | Uso |
|---|---|---|
| `m4_score_0_100` | `indices/monetary/M4-fci.monetary_m4_fci.score_normalized` | Diagnostic `f3_m4_divergence` (Policy 5) |
| `credit_gap_pp` | `indices/credit/L2-credit-to-gdp-gap.credit_to_gdp_gap.gap_hp_pp` | Bubble Warning condition 2 (cap 16) |
| `bis_property_gap_pct` | `connectors/bis_property_gaps` (primary) → fallback `indices/financial/F1-valuations.components_json.property_gap_z` levantado de `property_gap_pp` | Bubble Warning condition 3 |

### Country tier policy (F4 conditional — Policy 4)

Tier list materializada em [`docs/data_sources/country_tiers.yaml`](../../data_sources/country_tiers.yaml) per ADR-0005 (canonical artifact Bloco D1 2026-04-18); Phase 1 pipeline runtime lê este YAML directamente. Spec referencia canonicamente esse ficheiro e lista abaixo apenas para traceability.

| Tier | Countries | F4 handling | Confidence cap on re-weight |
|---|---|---|---|
| 1 | US, DE, UK, JP | **required**; F4 missing → raise `InsufficientDataError`, FCS not emitted | n/a (F4 present) |
| 2 | FR, IT, ES, CA, AU | **best-effort**; F4 missing → re-weight F1+F2+F3 proportionally, flag `F4_COVERAGE_SPARSE` | 0.80 |
| 3 | PT, IE, NL, SE, CH | **best-effort**; same behaviour as Tier 2 | 0.80 |
| 4 EM | CN, IN, BR, TR, MX, ZA, ID | **not expected**; FCS always = F1+F2+F3 re-weighted; flag `F4_COVERAGE_SPARSE` always set | 0.75 |

### Preconditions

- `country_tier` resolvido via [`docs/data_sources/country_tiers.yaml`](../../data_sources/country_tiers.yaml) (ADR-0005 canonical); `UnknownConnectorError` se country ausente (default T4 per YAML `default: T4`).
- `F1, F2, F3` rows existem para `(country_code, date)` com respective `methodology_version` ≥ `v0.1` e `confidence ≥ 0.30`; stored versions batem runtime ou raise `VersionMismatchError`.
- **Policy 1 baseline**: ≥ 3 sub-indices disponíveis senão raise `InsufficientDataError`; re-weight renormaliza proporcionalmente os restantes.
- **Policy 4 (F4 tier-conditional)**: Tier 1 obriga F4 presente; Tier 2-4 aceitam F4 `NULL`.
- `M4` row best-effort — ausente ≠ erro (Policy 5 permite `f3_m4_divergence = NULL`).
- `L2 credit_to_gdp_gap` row em quarterly grid; carry-forward até 180 dias para diagnostic daily; `> 180 d` → skip Bubble Warning condition 2 (ficheiro permanece inativo).
- `bis_property_gap_pct` freshness ≤ 180 dias; senão fallback para `F1.components_json.property_gap_pp` se disponível; senão skip condition 3.
- Prior FCS row do mesmo country consultada para `regime_persistence_days` e hysteresis state (§4 passo 7).

## 3. Outputs

Single row per `(country_code, date, methodology_version)` em `financial_cycle_scores`. Correlation UUID: `fcs_id`.

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `fcs_id` | `str (uuid4)` | — | `financial_cycle_scores` |
| `score_0_100` | `float` | `[0, 100]` (higher = euforia) | idem |
| `regime` | `str` | `STRESS` \| `CAUTION` \| `OPTIMISM` \| `EUPHORIA` | idem |
| `regime_persistence_days` | `int` | BD count since last regime change | idem |
| `f{1..4}_score_0_100` | `float` \| `NULL` | componente verbatim | idem |
| `f{1..4}_weight_effective` | `float` | peso após re-weighting; soma ≡ 1.0 | idem |
| `indices_available` | `int` | `3..4` | idem |
| `country_tier` | `int` | `1..4` | idem |
| `f3_m4_divergence` | `float` \| `NULL` | diagnostic (ver §4) | idem |
| `bubble_warning_active` | `int (0/1)` | Boolean overlay | idem |
| `bubble_warning_components_json` | `str (JSON)` \| `NULL` | `{fcs, credit_gap_pp, property_gap_pp}` | idem |
| `confidence` | `float` | `[0, 1]` | idem |
| `flags` | `str (CSV)` | — | idem |

**Canonical JSON shape** (operational API):

```json
{"country": "US", "date": "2026-04-17", "fcs_id": "…",
 "score_0_100": 68.4, "regime": "OPTIMISM", "regime_persistence_days": 42,
 "components": {"F1": 78.1, "F2": 71.3, "F3": 64.2, "F4": 58.9},
 "weights_effective": {"F1": 0.30, "F2": 0.25, "F3": 0.25, "F4": 0.20},
 "f3_m4_divergence": 12.4,
 "bubble_warning_active": false,
 "confidence": 0.83, "flags": []}
```

## 4. Algorithm

> **Units**: F1-F4 scores `float ∈ [0, 100]`; weights `float`; `f3_m4_divergence` in **points** (native 0-100 scale); `credit_gap_pp` pp; `bis_property_gap_pct` percent. Full rules em [`conventions/units.md`](../conventions/units.md).

**Canonical formula** (cap 15.5 / 15.6):

```text
FCS_t = w1·F1_t + w2·F2_t + w3·F3_t + w4·F4_t
with canonical  (w1, w2, w3, w4) = (0.30, 0.25, 0.25, 0.20)
when indices_available < 4: renormalize w_i = w_i_canonical / Σ_avail w_j_canonical
FCS ∈ [0, 100], higher = euphoric / risk-on
```

**Regime mapping** (cap 15.7):

```text
STRESS    : FCS <  30
CAUTION   : 30 ≤ FCS ≤ 55
OPTIMISM  : 55 <  FCS ≤ 75
EUPHORIA  : FCS >  75
```

**Anti-whipsaw hysteresis**: transition requires `|ΔFCS| > 5 pts` vs. the level at the last transition AND `persistence ≥ 3 business days` crossing the threshold. While hysteresis holds the prior regime, `regime_persistence_days` continua a incrementar.

**F3 ↔ M4 divergence diagnostic** (Policy 5):

```text
f3_m4_divergence = F3_score_0_100 − (100 − M4_score_0_100)
# M4 é "higher = tighter FCI" (stance monetária), F3 é "higher = risk-on complacent";
# devem mover inversely, portanto M4 inverted antes da subtracção.
flag F3_M4_DIVERGENCE when |f3_m4_divergence| > 15
```

**Bubble Warning overlay** (cap 16):

```text
bubble_warning_active = 1 IFF
    (score_0_100 > 70)                          # FCS level
    AND (credit_gap_pp > 10)                    # L2 gap_hp_pp
    AND (property_gap_available AND
         bis_property_gap_pct > 20)             # BIS primary OR F1 fallback
components_json = {"fcs": score, "credit_gap_pp": …, "property_gap_pp": …}
```

> **Placeholder thresholds — recalibrate after 24m de production data + walk-forward backtest contra Joint Bubble episodes documented em manual cap 16.4 (Japan 1988-90, US 1999-2000, US 2005-07, Spain/Ireland/Iceland 2005-08, UK 2006-08, China 2016-18)**.

**Pipeline per `(country_code, date)`**:

1. Resolve `country_tier` via [`docs/data_sources/country_tiers.yaml`](../../data_sources/country_tiers.yaml) (ADR-0005 canonical). Load `F1, F2, F3, F4` rows; validate `methodology_version` (raise `VersionMismatchError` se mismatch).
2. Apply **Policy 4**:
   - Tier 1 e F4 `NULL` → raise `InsufficientDataError` (no row persisted).
   - Tier 2-3 e F4 `NULL` → set F4 weight = 0, flag `F4_COVERAGE_SPARSE`, cap confidence ≤ 0.80.
   - Tier 4 EM → always set F4 weight = 0 (even if F4 row exists, it is ignored), flag `F4_COVERAGE_SPARSE`, cap confidence ≤ 0.75.
3. Apply **Policy 1 baseline**: if `indices_available < 3` → raise `InsufficientDataError`; else flag `{INDEX}_MISSING` per F_i ausente (e.g. `F2_MISSING`) e re-weight proporcionalmente; cap confidence ≤ 0.75.
4. Compute `score_0_100 = Σ w_i · F_i` (com effective weights); persist `f{i}_weight_effective`.
5. Load previous FCS row (`country_code`, `date − 1 BD`). Apply hysteresis:
   - Compute raw regime do `score_0_100` vs. thresholds.
   - Se raw regime ≠ prev regime: check `|score_0_100 − score_at_last_transition| > 5` AND streak contígua `≥ 3 BD` em raw new regime. Se sim → commit transition, reset `regime_persistence_days = 1`; senão → persist prior regime, `regime_persistence_days += 1`.
   - Cold-start (sem prior row): commit raw regime, `regime_persistence_days = 1`.
6. Load `M4` row para `(country_code, date)` se existir. Compute `f3_m4_divergence` (see formula). Flag `F3_M4_DIVERGENCE` se `|divergence| > 15`. Persist column; `NULL` se M4 ausente.
7. Evaluate **Bubble Warning** (cap 16):
   - Load `L2 credit_to_gdp_gap` row (carry-forward quarterly até 180 d).
   - Load `bis_property_gap_pct` via `connectors/bis_property_gaps`; fallback para `F1.components_json.property_gap_pp` (informational — flag `BUBBLE_PROPERTY_FALLBACK`).
   - `bubble_warning_active = (score > 70) AND (credit_gap_pp > 10) AND (property_gap > 20)`.
   - Se `True` → persist `bubble_warning_components_json`.
8. Inherit flags upstream de F1-F4, M4, L2 per `flags.md` § Convenção de propagação.
9. Compute `confidence` per §6 matrix. Persist row atomically.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | arithmetic, clip |
| `pandas` | 2.1 | history lookup (hysteresis, carry-forward) |
| `sqlalchemy` | 2.0 | persistence, prior-row lookup |
| `pydantic` | 2.6 | `bubble_warning_components_json` validation |
| `pyyaml` | 6.0 | read `docs/data_sources/country_tiers.yaml` (ADR-0005) |

No network calls — all inputs pre-computed em L3 tables / connectors.

## 6. Edge cases

Flags → [`conventions/flags.md`](../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../conventions/exceptions.md). Confidence impact aplicado per "Convenção de propagação".

| Trigger | Handling | Confidence |
|---|---|---|
| Tier 1 country e F4 `NULL` | raise `InsufficientDataError`; FCS not emitted | n/a |
| Tier 2-3 country e F4 `NULL` | flag `F4_COVERAGE_SPARSE`; re-weight F1+F2+F3 | cap 0.80 |
| Tier 4 EM (any date) | flag `F4_COVERAGE_SPARSE` (always); F4 ignored | cap 0.75 |
| `indices_available < 3` | raise `InsufficientDataError` | n/a |
| Any single F_i missing (allowed tier) | flag `F{i}_MISSING` (proposed); re-weight proporcionalmente | cap 0.75 |
| F_i inherits `OVERLAY_MISS` / `EM_COVERAGE` / `INSUFFICIENT_HISTORY` | inherit verbatim | propagated per input |
| Stored `F{i}.methodology_version` ≠ runtime | raise `VersionMismatchError` | n/a |
| M4 row ausente para `(country, date)` | persist `f3_m4_divergence = NULL`; no flag | none |
| `|f3_m4_divergence| > 15` | flag `F3_M4_DIVERGENCE` | informational |
| L2 credit_gap carry-forward > 180 d | skip Bubble Warning condition 2; flag `CALIBRATION_STALE` | −0.10 |
| `bis_property_gap_pct` connector missing, fallback to F1 `property_gap_pp` | flag `BUBBLE_PROPERTY_FALLBACK` (proposed) | −0.05 |
| Both BIS property primary + F1 fallback missing | Bubble Warning cannot activate; `bubble_warning_active = 0`; flag `BUBBLE_PROPERTY_UNAVAILABLE` (proposed) | −0.05 |
| Prior-day row missing (cold-start OR gap > 1 BD) | commit raw regime; `regime_persistence_days = 1`; flag `REGIME_BOOTSTRAP` (proposed) | −0.05 |
| Hysteresis holds (raw ≠ committed regime) | persist committed regime; informational flag `REGIME_HYSTERESIS_HOLD` (proposed) | none |
| Score computed `outside [0, 100]` post-renorm | raise `OutOfBoundsError` (bug upstream) | n/a |
| `country_code` não presente em `docs/data_sources/country_tiers.yaml` (nem default T4) | raise `UnknownConnectorError` | n/a |

## 7. Test fixtures

Stored em `tests/fixtures/financial-fcs/`. Each `input_<id>.json` + `expected_<id>.json`.

| Fixture | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02` | F1=73, F2=70, F3=68, F4=65 | `score ≈ 69.3`, regime `OPTIMISM`, no flags | ±1 score |
| `us_2021_11_03_euphoria` | F1=82, F2=78, F3=76, F4=88; credit_gap=8.5, property_gap=18 | `score ≈ 80.6`, `EUPHORIA`; bubble inactive (credit/property below thresholds) | ±1 score |
| `us_2007_q3_bubble_active` | F1=80, F2=70, F3=72, F4=74; credit_gap=12, property_gap=25 | `score > 73`, `EUPHORIA`; `bubble_warning_active=1` | ±2 score |
| `us_2009_03_09_stress` | F1=12, F2=8, F3=6, F4=10 | `score < 10`, `STRESS` | ±2 score |
| `pt_2024_01_02_tier3_f4_missing` | Tier 3 PT; F4 `NULL`; F1=42, F2=48, F3=52 | flag `F4_COVERAGE_SPARSE`, `F4_MISSING`; re-weight; `confidence ≤ 0.80` | ±2 score |
| `cn_2024_01_02_tier4` | Tier 4 CN; F1=45, F2=50, F3=48; F4 ignored | flag `F4_COVERAGE_SPARSE`; `confidence ≤ 0.75` | ±2 score |
| `us_f4_missing_tier1` | Tier 1 US; F4 `NULL` | raises `InsufficientDataError`; no row persisted | n/a |
| `hysteresis_whipsaw_blocked` | Prior FCS=72 OPTIMISM, today raw FCS=76 EUPHORIA but only 2 BD streak | commit `OPTIMISM`; flag `REGIME_HYSTERESIS_HOLD` | — |
| `hysteresis_transition_confirmed` | Prior OPTIMISM, 3 BD above 75 with Δ = 7 | commit `EUPHORIA`; `regime_persistence_days=1` | — |
| `m4_divergence_flagged` | F3=72, M4=40 → `divergence = 72 − (100−40) = 12`; synth F3=80, M4=30 → `divergence = 80 − 70 = 10` (no flag); F3=80, M4=10 → `divergence = 70 > 15` | flag `F3_M4_DIVERGENCE` só no terceiro caso | — |
| `bubble_property_fallback` | BIS connector 404; F1.property_gap_pp=22 | flag `BUBBLE_PROPERTY_FALLBACK`; bubble evaluated | — |
| `insufficient_two_indices` | F1, F2 only | raises `InsufficientDataError` | n/a |
| `version_mismatch` | F1 row stored with `F1_VALUATIONS_v0.0` | raises `VersionMismatchError` | n/a |
| `cold_start` | First row for new country | regime committed from raw; `regime_persistence_days=1`; flag `REGIME_BOOTSTRAP` | — |

## 8. Storage schema

```sql
CREATE TABLE financial_cycle_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fcs_id TEXT NOT NULL UNIQUE,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    methodology_version TEXT NOT NULL,                               -- 'FCS_COMPOSITE_v0.1'
    score_0_100 REAL NOT NULL CHECK (score_0_100 BETWEEN 0 AND 100),
    regime TEXT NOT NULL,                                             -- STRESS | CAUTION | OPTIMISM | EUPHORIA
    regime_persistence_days INTEGER NOT NULL,
    -- component scores
    f1_score_0_100 REAL,
    f2_score_0_100 REAL,
    f3_score_0_100 REAL,
    f4_score_0_100 REAL,
    f1_weight_effective REAL NOT NULL,
    f2_weight_effective REAL NOT NULL,
    f3_weight_effective REAL NOT NULL,
    f4_weight_effective REAL NOT NULL,
    indices_available INTEGER NOT NULL CHECK (indices_available BETWEEN 3 AND 4),
    country_tier INTEGER NOT NULL CHECK (country_tier BETWEEN 1 AND 4),
    -- cross-cycle diagnostic
    f3_m4_divergence REAL,                                            -- NULL if M4 unavailable
    -- overlays
    bubble_warning_active INTEGER NOT NULL DEFAULT 0,
    bubble_warning_components_json TEXT,                              -- {fcs, credit_gap_pp, property_gap_pp}
    -- meta
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_fcs_cd ON financial_cycle_scores (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `integration/matriz-4way` | L6 | `score_0_100` + `regime` compõem o eixo financeiro da matriz 4-way (cap 17) |
| `integration/diagnostics/bubble-detection` | L6 | `bubble_warning_active` + `bubble_warning_components_json` — overlay alerting |
| `integration/cost-of-capital` | L6 | `regime == EUPHORIA` reduz term-premium estimate (risk-on compression) |
| `outputs/editorial` | L7 | regime changes + `bubble_warning_active` são flagship editorial angles |

## 10. Reference

- **Methodology**: [`docs/reference/cycles/financial.md`](../../reference/cycles/financial.md) — caps 15 (FCS design + weights + state classification), 16 (Bubble Warning overlay), 4.6-4.7 (state definitions), 15.11 (walk-forward robustness).
- **Data sources**: [`docs/data_sources/financial.md`](../../data_sources/financial.md) §BIS overlay (`financial_bis_overlay`), §FCS composite; [`data_sources/country_tiers.yaml`](../../data_sources/country_tiers.yaml) (ADR-0005 tier assignments).
- **Architecture**: [`specs/conventions/patterns.md`](../conventions/patterns.md) §Pattern 4 (TE markets breadth + native overrides upstream via F1-F4); [`adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) (**FCS Policy 4 é a instantiation canonical da tier classification — T1 F4 required, T2-3 F4 optional cap 0.80, T4 F4 ignored cap 0.75**).
- **Proxies**: [`specs/conventions/proxies.md`](../conventions/proxies.md) — F4 non-US via `AAII_PROXY` (inherited from F4 spec); F3 via `VOL_PROXY_GLOBAL` / `MOVE_PROXY`.
- **Licensing**: [`governance/LICENSING.md`](../../governance/LICENSING.md) §3 (Shiller/Damodaran via F1 + FRED via F2-F3 attribution inherited) + §7 scrape ethics (F4 positioning composites-only per Override 2).
- **Peer specs**:
  - `indices/financial/F1-valuations` · `F2-momentum` · `F3-risk-appetite` · `F4-positioning` (L3 inputs).
  - `indices/monetary/M4-fci` (cross-cycle diagnostic).
  - `indices/credit/L2-credit-to-gdp-gap` (Bubble Warning input).
- **Papers**:
  - Borio C., Drehmann M. (2009), "Assessing the risk of banking crises — revisited", *BIS Q. Review* — medium-term overlay.
  - Kindleberger C., Aliber R. (2015), *Manias, Panics and Crashes* (7th ed.), Palgrave — joint bubble framework.
  - Schularick M., Taylor A. (2012), "Credit Booms Gone Bust", *AER* 102(2) — credit-gap leading indicator.
  - Shiller R. (2015), *Irrational Exuberance* (3rd ed.), Princeton — FCS-adjacent asset pricing lens.
- **Cross-validation**: walk-forward OOS 2000-2023 vs. NBER/Pagan-Sossounov bull/bear dating (cap 15.11); historical Joint Bubble Warning hit-rate vs. documented crises (cap 16.4).

## 11. Non-requirements

- Does **not** define asset-class-specific bubbles (equity-only, RE-only, crypto-only) separately — Bubble Warning é **global composite per country**; asset-class FCS complementary (cap 15.9) vive num módulo separado v0.2.
- Does **not** consume M4 como componente do FCS — F3 é canonical risk-appetite contributor; M4 é strictly diagnostic (Policy 5).
- Does **not** recompute F1-F4 — puro composite L4, consume `score_normalized` verbatim.
- Does **not** compute global / cross-country aggregate FCS — per-country apenas; aggregate lives em `integration/global-fcs` (Phase 2).
- Does **not** emit transition probability forecasts (cap 15.8 JSON `transition_probability_6M`) — contínuo apenas; forecasting vive em `cycles/forecasting` (Phase 5).
- Does **not** gap-fill across dates — daily batch only; backfill em `pipelines/backfill-strategy`.
- Does **not** classify asset-specific states nem sub-states (`early / mid / late`) — cap 15.8 sub-state é Phase 2; v0.1 só 4 regimes canónicos.
- Does **not** expose BIS DSR como condição Bubble Warning adicional — v0.1 limita-se a credit-gap + property-gap (cap 16.2 threshold "2 de 3" BIS metrics simplificado para 2 específicos em v0.1; DSR em v0.2).

---
