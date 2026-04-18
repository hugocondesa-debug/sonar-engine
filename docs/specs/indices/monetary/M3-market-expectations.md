# M3 — Market-Implied Expectations — Spec

> Layer L3 · index · cycle: monetary · slug: `m3-market-expectations` · methodology_version: `M3_MARKET_EXPECTATIONS_v0.1`
> Last review: 2026-04-19 (Phase 0 Bloco E2)

## 1. Purpose

Mede a **trajetória esperada de policy rates** implícita em market prices (forwards 1y1y / 2y1y / 5y5y) + **credibility da inflation anchor** (5y5y forward breakeven vs BC target). Forward-looking sub-índice — sinaliza se mercado pricing tightening / easing path, e se inflation expectations ancoradas. Mapeia ao sub-index EP (Expected Path — Cap 15.5) + componente nominal de CS (Credibility Signal).

## 2. Inputs

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `policy_rate_pct` | `float` (decimal) | current rate | mesmo input que M1 |
| `forward_1y1y_pct` | `float` (decimal) | from `yield_curves_forwards.forwards_json["1y1y"]` | `overlays/nss-curves` |
| `forward_2y1y_pct` | `float` (decimal) | derived from NSS forwards (compounded) | `overlays/nss-curves` |
| `forward_5y5y_pct` | `float` (decimal) | from `yield_curves_forwards.forwards_json["5y5y"]` | `overlays/nss-curves` |
| `breakeven_5y5y_pct` | `float` (decimal) | from `expected_inflation_canonical["5y5y"]` | `overlays/expected-inflation` |
| `inflation_target_pct` | `float` (decimal) | per BC; `bc_targets.yaml` | config |
| `anchor_status` | `str` | enum `{well_anchored, moderately_anchored, drifting, unanchored, NULL}` | `overlays/expected-inflation` |
| `anchor_deviation_bps` | `int` | `5y5y − target` em bps (signed) | `overlays/expected-inflation` |
| `policy_surprise_bps` | `int` | optional; last decision day Kuttner-style | `connectors/policy_surprise` (Tier 2; Miranda-Agrippino dataset) |
| `country_code` | `str` | ISO α-2 upper | config |
| `date` | `date` | business day local | param |

### Preconditions

- `overlays/nss-curves` row para `(country, date)` com `confidence ≥ 0.50`; `forwards_json` contém `"1y1y"` AND `"5y5y"`; senão raise `InsufficientDataError`.
- `overlays/expected-inflation` canonical row com `5y5y` tenor não-NULL; senão `breakeven` componente skip + flag `ANCHOR_UNCOMPUTABLE` (reemit).
- Para CN/TR/AR (sem operative target): `anchor_deviation_bps = NULL`; flag `NO_TARGET` reemitido.
- `policy_surprise_bps` opcional — disponível só pós-FOMC/GovC days; quando ausente, peso 0% (Cap 15.5 EP variant 4).
- `methodology_version` dos overlays consumidos bate com runtime ou raise `VersionMismatchError`.

## 3. Outputs

Uma row per `(country_code, date)` em `monetary_m3_market_expectations`.

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `score_normalized` | `float` | z-score → `[0, 100]` (higher = market expects tighter) | column |
| `score_raw` | `float` | pp (`forward_1y1y − policy_rate`); positivo = market prices hiking | column |
| `forward_1y1y_pct` | `float` | decimal | column |
| `forward_2y1y_pct` | `float` | decimal | column |
| `forward_5y5y_pct` | `float` | decimal | column |
| `breakeven_5y5y_pct` | `float` | decimal | column |
| `anchor_status` | `str` | enum (passthrough) | column |
| `anchor_deviation_bps` | `int` | signed | column |
| `policy_surprise_bps` | `int` (nullable) | signed; last decision | column |
| `components_json` | `str (JSON)` | EP sub-components + weights | column |
| `lookback_years` | `int` | years (default 30 — to span ZLB regime) | column |
| `confidence` | `float` | 0-1 | column |
| `flags` | `str (CSV)` | — | column |
| `methodology_version` | `str` | — | column |

**Canonical JSON shape** (`components_json`):

```json
{
  "ep_subscore_1y1y_vs_policy": 58.0,
  "ep_subscore_2y1y_vs_policy": 62.0,
  "ep_subscore_5y5y_vs_target": 55.0,
  "ep_subscore_recent_surprise": 50.0,
  "ep_weights": {"1y1y": 0.40, "2y1y": 0.25, "5y5y_anchor": 0.20, "surprise": 0.15},
  "anchor_band": "moderately_anchored",
  "credibility_signal_passthrough": 0.10
}
```

## 4. Algorithm

> **Units**: rates em decimal; `_bps` (anchor deviation, surprise) em integer signed. `score_normalized` é `[0, 100]` float. Regras em [`conventions/units.md`](../../conventions/units.md).

**Formula** (EP sub-index per Cap 15.5):

```text
g_1y1y_vs_policy   = forward_1y1y − policy_rate                  # > 0 → market prices hiking
g_2y1y_vs_policy   = forward_2y1y − policy_rate
g_5y5y_anchor      = (breakeven_5y5y − inflation_target)         # signed; pp
g_surprise         = policy_surprise_bps / 100                     # last meeting; pp

EP_raw = 0.40 · z(g_1y1y_vs_policy)
       + 0.25 · z(g_2y1y_vs_policy)
       + 0.20 · z(g_5y5y_anchor)                                  # tighter implied if breakeven > target
       + 0.15 · z(g_surprise)                                      # hawkish surprise → tight

score_normalized = clip(50 + 16.67 · EP_raw, 0, 100)
score_raw        = g_1y1y_vs_policy                                # natural unit (pp)
```

`z(x)` = z-score sobre rolling window 30 anos (cobre ZLB + post-2008).

**Pseudocode** (deterministic):

1. Lookup `forwards_json` from `overlays/nss-curves.yield_curves_forwards` for `(country, date)`. Validate keys `"1y1y"`, `"5y5y"`.
2. Compute `forward_2y1y` from NSS forwards (compounded): se já em `forwards_json` use directly; senão derive via `[(1+f_3y)^3 / (1+f_2y)^2 − 1]` com NSS zero curve.
3. Lookup `breakeven_5y5y_pct` from `expected_inflation_canonical.expected_inflation_tenors_json["5y5y"]`. Inherit `anchor_status` + `anchor_deviation_bps`.
4. Resolve `inflation_target_pct` from `bc_targets.yaml`. NO_TARGET countries → skip 5y5y anchor component, reweight EP `[0.50/0.30/0/0.20]`.
5. Lookup `policy_surprise_bps` from `connectors/policy_surprise` for last decision day ≤ 90 dias; else `NULL` and reweight EP.
6. Compute 4 component gaps per formula.
7. Compute z-score de cada gap sobre 30Y window do mesmo país.
8. Aggregate EP_raw via Cap 15.5 weights → `score_normalized`.
9. Compute `confidence` via §6 matrix; inherit upstream flags from NSS + expected-inflation.
10. Persist row em §8 schema.

## 5. Dependencies

| Package | Min | Use |
|---|---|---|
| `numpy` | 1.26 | z-score, arrays |
| `pandas` | 2.1 | timeseries i/o, rolling windows |
| `pyyaml` | 6.0 | `bc_targets.yaml` config load |
| `sqlalchemy` | 2.0 | persistence |
| `pydantic` | 2.6 | output validation |

No network — todos inputs via overlays L2 + connectors L0/L1.

## 6. Edge cases

Flags → [`conventions/flags.md`](../../conventions/flags.md). Exceptions → [`conventions/exceptions.md`](../../conventions/exceptions.md).

| Trigger | Handling | Confidence |
|---|---|---|
| `nss-curves` row missing OR `confidence < 0.50` | raise `InsufficientDataError` | n/a |
| `expected-inflation` 5y5y missing | drop anchor component; reweight EP; reemit `ANCHOR_UNCOMPUTABLE` | −0.10 |
| `bei_vs_survey_divergence > 100 bps` (upstream flag) | inherit `INFLATION_METHOD_DIVERGENCE` | −0.10 |
| `forward_1y1y < −0.01` (negative implausible) | inherit `NEG_FORWARD`; clamp para −0.01 | −0.15 |
| Country `NO_TARGET` (CN, TR, AR) | skip 5y5y anchor; reweight EP; reemit `NO_TARGET` | −0.05 |
| `policy_surprise_bps` last meeting > 90 dias | drop component; reweight EP | −0.05 |
| Surprise > 25 bps (proxy "regime shift") | flag `POLICY_SURPRISE_LARGE` (proposed); register in editorial | −0.05 |
| OIS data missing (Tier 4) → derive from NSS forwards only | accept; flag `OIS_PROXY` (proposed) | −0.05 |
| Country tier 4 (CN, IN, BR, TR, MX) | inherit `EM_COVERAGE`; cap conf | cap 0.65 |
| `lookback_years < 20` | flag `INSUFFICIENT_HISTORY` (proposed); reduce window | cap 0.70 |
| Stored upstream `methodology_version` ≠ runtime | raise `VersionMismatchError` | n/a |

## 7. Test fixtures

Stored em `tests/fixtures/m3-market-expectations/`.

| Fixture id | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2026_04_17` | policy=0.04375, fwd_1y1y=0.040, fwd_5y5y=0.0385, BEI_5y5y=0.0254, π*=0.02 | `score_raw≈−0.00375` (market expects easing); `anchor_dev_bps≈+54`; `score_norm≈45` | ±5 bps; ±5 score |
| `us_2022_q1` (Fed-behind-curve) | policy=0.0025, fwd_1y1y=0.020, BEI_5y5y=0.029 | `score_raw≈+0.0175` (market hawkish); `score_norm>75` | ±10 bps |
| `ea_2026_04_17` | DFR=0.02, fwd_1y1y=0.018, fwd_5y5y=0.025, BEI_5y5y=0.0240 | `score_raw≈−0.002`; `anchor=well_anchored`; `score_norm≈48` | ±5 bps |
| `pt_2026_04_17` | inherits EA forwards via `nss-curves` PT; BEI from DERIVED path | inherits EA expectations; `confidence ≤ 0.80` | — |
| `jp_2024_03_15` (BoJ exit YCC) | policy=0.005 (after exit), fwd_1y1y=0.012, BEI_5y5y=0.018 | `score_raw≈+0.007` (market expects normalization); `anchor=drifting` | — |
| `us_anchor_unanchored_1980` | BEI_5y5y=0.07, π*=0.02 | `anchor_dev_bps=+500`; flag inherit `unanchored`; `score_norm>85` | — |
| `cn_no_target` | CN curve fitted; no breakeven | flag `NO_TARGET`; reweight; `confidence ≤ 0.55` | — |
| `policy_surprise_25bps` | last FOMC: surprise=+25bps | `g_surprise=+0.25`; flag `POLICY_SURPRISE_LARGE` | — |

## 8. Storage schema

```sql
CREATE TABLE monetary_m3_market_expectations (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code             TEXT    NOT NULL,
    date                     DATE    NOT NULL,
    methodology_version      TEXT    NOT NULL,            -- 'M3_MARKET_EXPECTATIONS_v0.1'
    score_normalized         REAL    NOT NULL CHECK (score_normalized BETWEEN 0 AND 100),
    score_raw                REAL    NOT NULL,            -- pp (decimal); fwd_1y1y − policy
    forward_1y1y_pct         REAL    NOT NULL,            -- decimal
    forward_2y1y_pct         REAL    NOT NULL,            -- decimal
    forward_5y5y_pct         REAL    NOT NULL,            -- decimal
    breakeven_5y5y_pct       REAL,                        -- decimal; NULL se ANCHOR_UNCOMPUTABLE
    anchor_status            TEXT,                        -- enum or NULL
    anchor_deviation_bps     INTEGER,                     -- signed bps; NULL para NO_TARGET
    policy_surprise_bps      INTEGER,                     -- signed; NULL se sem decisão recente
    components_json          TEXT    NOT NULL,            -- EP sub-components + weights
    lookback_years           INTEGER NOT NULL,
    confidence               REAL    NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                    TEXT,
    nss_fit_id               TEXT    NOT NULL,            -- FK to yield_curves_spot.fit_id
    exp_inf_id               TEXT,                        -- FK to expected_inflation_canonical.exp_inf_id
    source_connector         TEXT    NOT NULL,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, methodology_version)
);
CREATE INDEX idx_m3_cd ON monetary_m3_market_expectations (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `cycles/monetary-msc` | L4 | `score_normalized` (peso ~25% MSC; mapeia EP + parcial CS via anchor) |
| `cycles/monetary-msc` (Dilemma) | L4 | `anchor_status` + `anchor_deviation_bps` para Dilemma trigger A (price stability vs financial stability) |
| `outputs/editorial` | L7 | `score_raw` ("market prices 50 bps cuts over 12m") + anchor narrative |
| `integration/diagnostics/regime-shift` | L6 | `policy_surprise_bps > 25` → regime shift marker |

## 10. Reference

- **Methodology**: [`docs/reference/indices/monetary/M3-market-expectations.md`](../../../reference/indices/monetary/M3-market-expectations.md) — Manual Cap 9 (Market-implied expectations).
- **Composite design**: [`docs/reference/cycles/monetary.md`](../../../reference/cycles/monetary.md) Cap 15.5 (Sub-index EP weights 40/25/20/15) + Cap 15.6 (MSC weights).
- **Data sources**: [`docs/data_sources/monetary.md`](../../../data_sources/monetary.md) §3 (Market-implied expectations) — OIS, fed funds futures, breakevens, dot plot.
- **Architecture**: [`specs/conventions/patterns.md`](../../conventions/patterns.md) §Pattern 2 (Hierarchy best-of inherited from `expected-inflation` overlay); [`adr/ADR-0005-country-tiers-classification.md`](../../../adr/ADR-0005-country-tiers-classification.md) (T1 linker countries + T2+ SURVEY-only).
- **Proxies**: [`specs/conventions/proxies.md`](../../conventions/proxies.md) — `BREAKEVEN_PROXY_SURVEY` propagated from `expected-inflation` quando linker indisponível.
- **Licensing**: [`governance/LICENSING.md`](../../../governance/LICENSING.md) §3 (FRED/ECB SDW/BoJ/Miranda-Agrippino attribution).
- **Papers**:
  - Kuttner K. (2001), "Monetary policy surprises and interest rates: Evidence from the Fed funds futures market", *JME* 47(3).
  - Gürkaynak R., Sack B., Swanson E. (2005), "Do Actions Speak Louder Than Words?", *Int. J. Central Banking* 1(1).
  - Miranda-Agrippino S., Ricco G. (2021), "The Transmission of Monetary Policy Shocks", *AEJ: Macro* 13(3).
  - Woodford M. (2003), *Interest and Prices: Foundations of a Theory of Monetary Policy*, Princeton.
- **Cross-validation**: FRED `T5YIFR` (US 5y5y inflation forward); CME FedWatch (US fed funds path); ECB SDW `FM` swap dataset (EA OIS).

## 11. Non-requirements

- Does not fit OIS / fed funds futures curves — `overlays/nss-curves` consome OIS-implied forwards (where available) e produz `yield_curves_forwards`; M3 só consome.
- Does not compute breakevens — `overlays/expected-inflation` produz canonical 5y5y; M3 só consome.
- Does not implement dot plot scraping — Tier 2 connector futuro `connectors/fomc_sep`; quando disponível consumido como input do CS sub-index dentro de `cycles/monetary-msc` (não M3).
- Does not classify Dilemma — `anchor_status` é input para `cycles/monetary-msc` Cap 16 logic; M3 só passa-through.
- Does not emit Krippner ETL (Expected Time to Lift-off) — alternative metric não usada em MSC v0.1.
- Does not handle term premium decomposition — `forward_5y5y` contém embedded term premium; literature flag (Cap 9.9 limitations) registada como diagnostic, não corrigida nesta spec.
- Does not compute policy surprise itself — consume Miranda-Agrippino dataset (Tier 2 connector); intra-day window estimation é fora de escopo.
- Does not auto-detect regime shifts — `POLICY_SURPRISE_LARGE` flag emitida; classification em `integration/diagnostics`.
