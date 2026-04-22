# Sprint J — CAL-M4-T1-FCI-EXPANSION — Pre-flight findings

Probe date: 2026-04-22. Branch: `sprint-m4-fci-t1-expansion`.

Target: M4 FCI 5-component viability (credit spread, equity vol, 10Y
gov yield, NEER, mortgage rate) per 16 T1 country + EA aggregate
(`XM`).

`MIN_CUSTOM_COMPONENTS = 5` per `sonar/indices/monetary/m4_fci.py` —
partial (< 5) compute is not emitted; the compute side raises
`InsufficientDataError`. Builders at < 5 must therefore either (a)
raise from the builder with a `{CODE}_M4_SCAFFOLD_ONLY` flag + CAL
pointer, or (b) be skipped via `NotImplementedError`. The US NFCI
short-circuit (spec §4 step 1) bypasses the 5-component floor for US
only.

## 1. Data-source probe matrix

| Source                                       | Coverage                                                                                          | Notes                                                                                                                                   |
|----------------------------------------------|---------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| **FRED NFCI** (`NFCI`)                        | **US only** (weekly, Chicago Fed)                                                                  | 7 obs Nov-Dec 2024; live. Canonical US M4 provider — spec §4 step 1.                                                                    |
| **FRED VIX** (`VIXCLS`)                       | **US**                                                                                             | Already wired as `fetch_vix_us`.                                                                                                         |
| **TE markets** `VIX:IND`                      | US (daily)                                                                                         | 4 obs 2024-12-02 → 2024-12-05 close 13.54.                                                                                              |
| **TE markets** `VSTOXX:IND`                   | **EA** (daily; proxy for EA members)                                                               | 4 obs 2024-12-02 → 2024-12-05 close 15.00. Used as vol for DE/FR/IT/ES/NL/PT (EA implied vol, common practice).                         |
| **TE markets** `V2TX / VFTSE / VNKY / NKYVOLX`| **EMPTY** — not provisioned at our TE tier.                                                        | Direct-probed all four; zero rows. GB / JP vol uncovered at this tier.                                                                  |
| **FRED OAS** `BAMLC0A0CM` (US IG)             | **US IG corporate OAS** (daily)                                                                    | 4 obs 2024-12-02=0.81 pp.                                                                                                                |
| **FRED OAS** `BAMLH0A0HYM2` (US HY)           | **US HY**                                                                                          | Alternate US credit spread — not wired this sprint.                                                                                     |
| **FRED OAS** `BAMLHE00EHYIOAS` (EA HY)        | **EA** (daily)                                                                                     | 4 obs 2024-12-02=3.32 pp. Used as credit spread for EA aggregate + EA-member custom paths (no per-country IG OAS at FRED).              |
| **BIS WS_EER** (`M.N.B.{CTY}`)                | **17/17** (US, DE, FR, IT, ES, NL, PT, GB, JP, CA, AU, NZ, CH, SE, NO, DK, XM)                     | Monthly, broad basket. US=106.26 Oct-2024, EA (XM)=108.64 Nov-2024. Monthly frequency → `_M4_NEER_MONTHLY_CADENCE` flag per builder.    |
| **ECB SDW MIR** (`M.{CC}.B.A2C.A.R.A.2250.EUR.N`) | **EA aggregate (U2) + DE + FR + IT + ES + NL + PT** (monthly)                                  | Household mortgage rates, new business, MFI. PT Jan-2026 = 3.30 %. Not yet wired.                                                       |
| **FRED MORTGAGE30US**                         | **US** (weekly)                                                                                    | Already wired as `fetch_mortgage30_us`. Used by US NFCI-bypass path only (NFCI is already z-scored).                                    |
| **TE per-country `/historical/.../indicator/volatility`** | **EMPTY** — our TE tier does not provision this endpoint for any probed country.      | Confirmed 17 probes (US + 16 T1). API returns `200 []`. Not a usable path for vol at this tier.                                          |
| **TE per-country `/historical/.../indicator/corporate%20bond%20spread`** | **EMPTY** — same limitation.                                              | Per-country credit spread not viable at this TE tier. Documented as source gap; CAL follow-up.                                          |

## 2. Per-country component matrix (T1 + EA aggregate)

Components per spec §4 custom path (5 weighted): credit / vol / 10Y /
NEER / mortgage. Mapping = wired source identifier.

| Country | Credit spread           | Vol index        | 10Y yield (L2 overlay)                  | NEER (monthly)    | Mortgage rate           | n_viable | Mode         |
|---------|-------------------------|------------------|------------------------------------------|-------------------|--------------------------|----------|--------------|
| **US**  | BAMLC0A0CM              | VIXCLS           | `overlays.nss-curves` US 10Y             | DTWEXBGS (daily) | MORTGAGE30US             | **5**    | FULL (NFCI direct-provider — 5-component path bypassed) |
| **EA**  | BAMLHE00EHYIOAS         | VSTOXX (TE)      | ECB SDW Bund / GDBR10 TE                 | BIS `XM`          | MIR `M.U2`               | **5**    | **FULL NEW** |
| **DE**  | BAMLHE00EHYIOAS (proxy) | VSTOXX (proxy)   | `overlays.nss-curves` DE 10Y / TE        | BIS `DE`          | MIR `M.DE`               | **5**    | **FULL NEW** |
| **FR**  | BAMLHE00EHYIOAS (proxy) | VSTOXX (proxy)   | TE FR 10Y                                 | BIS `FR`          | MIR `M.FR`               | **5**    | **FULL NEW** |
| **IT**  | BAMLHE00EHYIOAS (proxy) | VSTOXX (proxy)   | TE IT 10Y                                 | BIS `IT`          | MIR `M.IT`               | **5**    | **FULL NEW** |
| **ES**  | BAMLHE00EHYIOAS (proxy) | VSTOXX (proxy)   | TE ES 10Y                                 | BIS `ES`          | MIR `M.ES`               | **5**    | **FULL NEW** |
| **NL**  | BAMLHE00EHYIOAS (proxy) | VSTOXX (proxy)   | TE NL 10Y                                 | BIS `NL`          | MIR `M.NL`               | **5**    | **FULL NEW** |
| **PT**  | BAMLHE00EHYIOAS (proxy) | VSTOXX (proxy)   | TE PT 10Y                                 | BIS `PT`          | MIR `M.PT`               | **5**    | **FULL NEW** |
| **GB**  | — (no tier-3 source)    | — (V2TX empty)   | BoE / TE GB 10Y                           | BIS `GB`          | — (BoE Bankstats gap)    | 2        | SCAFFOLD (new) |
| **JP**  | —                       | — (NKYVOLX empty)| BoJ / TE JP 10Y                           | BIS `JP`          | — (BoJ prime gap)        | 2        | SCAFFOLD (preserved) |
| **CA**  | —                       | —                | BoC / TE CA 10Y                           | BIS `CA`          | —                        | 2        | SCAFFOLD (preserved) |
| **AU**  | —                       | —                | RBA / TE AU 10Y                           | BIS `AU`          | —                        | 2        | SCAFFOLD (preserved) |
| **NZ**  | —                       | —                | RBNZ / TE NZ 10Y                          | BIS `NZ`          | —                        | 2        | SCAFFOLD (preserved) |
| **CH**  | —                       | —                | SNB / TE CH 10Y                           | BIS `CH`          | —                        | 2        | SCAFFOLD (preserved) |
| **SE**  | —                       | —                | Riksbank / TE SE 10Y                      | BIS `SE`          | —                        | 2        | SCAFFOLD (preserved) |
| **NO**  | —                       | —                | Norges / TE NO 10Y                        | BIS `NO`          | —                        | 2        | SCAFFOLD (preserved) |
| **DK**  | —                       | —                | Nationalbanken / TE DK 10Y                | BIS `DK`          | —                        | 2        | SCAFFOLD (preserved) |

## 3. HALT-0 check

Brief §5 HALT-0: "if probes reveal < 8 of 16 countries have ≥ 2
components viable, HALT scope + surface." **All 16 T1 + EA aggregate
report ≥ 2 viable components** (minimum floor is 10Y + BIS NEER for
the 9 non-EA T1 countries). HALT-0 does **not** fire.

## 4. HALT-12 / HALT-14 surface

- **HALT-12** ("> 8 countries end PARTIAL_COMPUTE") — the ≥5
  MIN_CUSTOM_COMPONENTS floor forces partial ≠ compute; non-EA T1
  builders with 2/5 components become **SCAFFOLD**, not PARTIAL.
  Trigger does not apply to the strict semantics.
- **HALT-14** ("SCAFFOLD > 6 countries") — **fires**: 9 T1 countries
  (GB + JP + CA + AU + NZ + CH + SE + NO + DK) end as SCAFFOLD
  post-sprint. Per-country SCAFFOLD reason is systematic at the
  TE / FRED / BIS / ECB tier:
  - **Vol index absent** for all 9 (TE tier-3 symbols V2TX / VFTSE /
    NKYVOLX / AU-VIX / CA-VIX not provisioned at our API key).
  - **Credit spread absent** for all 9 (no FRED OAS per T2 country;
    BIS WS_TC is credit stock, not spread; TE per-country corporate
    bond spread endpoint returns 200 []).
  - **Mortgage rate absent** for all 9 at the connector surface wired
    this sprint (BoE Bankstats / BoJ / BoC / RBA / RBNZ / SNB /
    Riksbank / Norges / Nationalbanken mortgage-specific series
    are per-CB native-connector extension territory — out of brief
    §1 scope for Sprint J).

Per-component gap CAL items to open at Commit 7 closure:

- `CAL-M4-VOL-T2-TIER3-GB-JP-CA-AU-NZ-CH-SE-NO-DK` — national equity
  vol index sourcing (TE tier-3 provisioning, or Yahoo Finance
  connector v2, or stooq extension per spec §2).
- `CAL-M4-CREDIT-SPREAD-T2-PER-COUNTRY` — per-country IG / HY OAS
  sourcing beyond BAML (ICE Data / IHS iBoxx / national-CB data).
- `CAL-M4-MORTGAGE-RATE-T1-NATIVE-EXPANSION` — per-CB native mortgage
  series (BoE IUMTLMV, BoJ prime rate, BoC V39079-family, RBA G3,
  RBNZ B19, SNB / Riksbank / Norges / Nationalbanken consumer-rate
  publications).
- `CAL-M4-NEER-FREQUENCY-DAILY` — BIS WS_EER is monthly; daily FCI
  compute uses most-recent + `_M4_NEER_MONTHLY_CADENCE` flag. Daily
  interpolation via bilateral-FX composite is a separate modelling
  decision (Phase 2.5 calibration scope).

## 5. Scope decision

**Ship FULL compute** for **EA aggregate + 6 EA members** (DE / FR / IT
/ ES / NL / PT) via the shared EA credit-spread + vol proxies with
country-specific NEER + MIR mortgage rate + 10Y overlay/TE. US M4
canonical **preserved** (NFCI direct-provider path, unchanged).

**Ship NEW scaffold** for GB (brief §1 Tier A inclusion) and **preserve
8 existing scaffolds** (AU / CA / CH / DK / JP / NO / NZ / SE). All
scaffolds emit `{CODE}_M4_SCAFFOLD_ONLY` + point to the per-component
CAL items above.

Post-sprint state:

- **FULL compute**: 8 entities (US + EA + DE + FR + IT + ES + NL + PT).
  Seven are **new FULL** vs pre-sprint (US alone was live).
- **SCAFFOLD**: 9 T1 (GB new + AU / CA / CH / DK / JP / NO / NZ / SE
  preserved).
- **Total operational**: 17/17 wired (16 T1 + EA), 8/17 compute-ready.

## 6. Connector wiring required per Commits 2-6

| Commit | Connector           | Method(s)                                                                                                        |
|--------|---------------------|------------------------------------------------------------------------------------------------------------------|
| 2      | `connectors.te`     | `fetch_vix_us_markets` + `fetch_vstoxx_ea_markets` (markets endpoint — `VIX:IND` / `VSTOXX:IND`).                |
| 2      | `connectors.fred`   | `fetch_us_ig_oas` (`BAMLC0A0CM`) + `fetch_ea_hy_oas` (`BAMLHE00EHYIOAS`).                                        |
| 3      | `connectors.bis`    | `fetch_neer` — BIS WS_EER(1.0) `M.N.B.{CTY}` broad basket.                                                       |
| 4      | `connectors.ecb_sdw`| `fetch_mortgage_rate` — MIR `M.{CC}.B.A2C.A.R.A.2250.EUR.N` household house-purchase new-business lending rate.  |
| 4      | `indices.monetary.builders` | `_assemble_m4_full_compute` helper + `build_m4_ea_inputs` + `build_m4_de_inputs` (Tier A close).           |
| 5      | `indices.monetary.builders` | `build_m4_fr / it / es / nl / pt_inputs` + `build_m4_gb_inputs` (scaffold).                                |
| 6      | `pipelines.daily_monetary_indices` | M4 dispatch for new countries + `_classify_m4_compute_mode` + smoke canary.                          |

End of pre-flight findings.
