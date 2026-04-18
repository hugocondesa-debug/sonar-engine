# {Title} — Spec

> Layer L{N} · {category} · slug: `{slug}` · methodology_version: `{name}_v0.1`

## 1. Purpose

{1-3 linhas. O que computa e porque existe. Evitar narrativa histórica — isso vive em `docs/reference/`.}

## 2. Inputs

| Nome | Tipo | Constraints | Source |
|---|---|---|---|
| `input_a` | `pd.Series[float]` | tenors ∈ grid canónico, ≥6 obs | `connectors/<name>` |
| `input_b` | `date` | business day | param |
| `country_code` | `str` | ISO 3166-1 α-2 upper | config |

### Preconditions

Invariantes antes da invocação:

- `input_a` e `input_b` vêm do mesmo connector para `(country_code, date)`
- Nenhum NaN (connector pré-limpa)
- `date` é business day local do país
- Connector `fetched_at` ≤ 24h face a `date`
- Schema da tabela source já migrada à `methodology_version` atual

## 3. Outputs

| Nome | Tipo | Unit | Storage |
|---|---|---|---|
| `output_primary` | `dict[str, float]` | % | table `<table_name>` |
| `confidence` | `float` | 0-1 | idem |
| `methodology_version` | `str` | — | idem |

**Canonical JSON shape**:

```json
{"country": "PT", "date": "2026-04-17", "curve_type": "...", "values": {"10Y": 3.35}, "confidence": 0.88}
```

## 4. Algorithm

> **Units**: decimal storage/compute, percent display-only, bps como `int`. Full rules em [`conventions/units.md`](../conventions/units.md).

**Formula**:

```text
f(x) = ...
```

**Pseudocode** (numbered, deterministic):

1. Load `input_a` from connector X for `country_code`, `date`.
2. Validate: `len(input_a) >= 6`, no NaN, yields ∈ [-0.05, 0.30].
3. Fit via `scipy.optimize.minimize(objective, x0, method="L-BFGS-B", bounds=BOUNDS)`.
4. Derive secondary outputs from primary.
5. Compute `rmse_bps = sqrt(mean((fit - observed)**2)) * 10000`.
6. Set `confidence` via calibration table §6.
7. Persist to §8 schema with `methodology_version`.

## 5. Dependencies

| Package | Min version | Use |
|---|---|---|
| `numpy` | 1.26 | arrays, vector ops |
| `scipy` | 1.11 | `optimize.minimize` |
| `pandas` | 2.1 | series storage |
| `sqlalchemy` | 2.0 | persistence |

No network calls inside the algorithm — inputs come pre-fetched from connectors.

## 6. Edge cases

| Trigger | Handling | Confidence impact |
|---|---|---|
| `<6 observations` | raise `InsufficientDataError` | n/a |
| NaN in inputs | drop obs, log WARNING | −0.10 per NaN dropped |
| Optimization did not converge | fallback to linear interp + flag `NSS_FAIL` | cap at 0.50 |
| Extrapolation beyond observed tenor | emit `EXTRAPOLATED` flag | −0.20 |
| Country tier 4 | wider bounds, accept RMSE up to 15bps | cap at 0.70 |

## 7. Test fixtures

Store in `tests/fixtures/<slug>/`. Each `input_<name>.json` + `expected_<name>.json`.

| Fixture | Input | Expected | Tolerance |
|---|---|---|---|
| `us_2024_01_02` | Treasury par yields 11 tenors | `β0≈0.0415`, `rmse_bps<5` | ±10% on β, ±2bps on RMSE |
| `de_2024_01_02` | Bundesbank raw yields | cross-check vs published Svensson <5bps | ±5bps |
| `pt_2024_01_02` | IGCP OTs | fitted 10Y within 15bps of ECB SDW | ±15bps |
| `insufficient_5_tenors` | 5 yields | raises `InsufficientDataError` | n/a |
| `em_tr_2024_01_02` | TR CBRT sparse | confidence ≤ 0.70, flag `EM_COVERAGE` | — |

## 8. Storage schema

```sql
CREATE TABLE <table_name> (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code          TEXT NOT NULL,
    date                  DATE NOT NULL,
    curve_type            TEXT NOT NULL,        -- enum: spot|zero|forward|real|swap
    methodology_version   TEXT NOT NULL,
    -- params
    beta_0                REAL,
    beta_1                REAL,
    -- outputs
    fitted_yields_json    TEXT NOT NULL,
    rmse_bps              REAL,
    confidence            REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    flags                 TEXT,                  -- CSV of flag tokens
    source_connector      TEXT NOT NULL,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (country_code, date, curve_type, methodology_version)
);
CREATE INDEX idx_<table>_cd ON <table_name> (country_code, date);
```

## 9. Consumers

| Consumer | Layer | Uses |
|---|---|---|
| `overlays/erp-daily` | L2 | risk-free rate from spot 10Y |
| `indices/monetary/M1` | L3 | curve slope (10Y − 2Y) |
| `cycles/monetary-msc` | L4 | β1 as stance signal |

## 10. Reference

- **Methodology**: [`docs/reference/overlays/<slug>.md`](../../reference/overlays/<slug>.md) — caps {N-M} do manual.
- **Data sources**: [`docs/data_sources/<cycle>.md`](../../data_sources/<cycle>.md) § {section}.
- **Papers**: Author (YYYY), "Title", Journal.
- **Cross-validation**: {BC source} · RMSE target {N bps}.

## 11. Non-requirements *(optional)*

Scope boundaries. O que este componente **não** faz — pertence a outro módulo ou está fora de escopo v2:

- Does not {X} — {upstream/downstream concern + onde vive}
- Does not {Y} — {razão}
- Does not ...
