# Proxies registry

> **FROZEN convention.** Alterações requerem PR dedicado (consistente com `conventions/`).

Catálogo canónico de **proxies** usados por overlays L2 / indices L3 / cycles L4 quando a série canónica não está disponível. Distingue-se **proxy** vs **fallback** vs **placeholder** — conceitos relacionados mas não intermutáveis.

## Concept — distinção crítica

| Conceito | Descrição | Exemplo |
|----------|-----------|---------|
| **Fallback** | Fonte alternativa para a **mesma série** conceptual. Pattern 2 hierarchy best-of: primary → secondary → tertiary, all fetching the same economic quantity. | CDS 5Y sovereign indisponível → sovereign 10Y spread vs benchmark (same concept: country risk premium). |
| **Proxy** | Série **diferente** usada como substituto metodológico. Captura o mesmo conceito económico mas via medição diferente. Requer justification theoretical + empirical. | `USSLIND` (state leading index) como proxy para Conference Board LEI (national leading index) — diferente série mas same concept. |
| **Placeholder** | Threshold / valor temporário até empirical calibration. Não é substituição de data; é valor de parâmetro. | E1 band threshold = `±1.0σ placeholder — recalibrate after 24m production data` (ver `calibration-tasks.md`). |

**Rule of thumb:**
- Se pergunta é "de onde vem esta série?" → fallback hierarchy (Pattern 2).
- Se pergunta é "esta série diferente substitui aquela que não temos?" → proxy (registado aqui).
- Se pergunta é "este número é empirical ou placeholder?" → placeholder (registado em `calibration-tasks.md`).

## Registry table

Cada proxy adicionado requer: (a) theoretical justification, (b) empirical evidence se aplicável (D-block findings), (c) flag emitted, (d) review horizon.

| Proxy | Original concept | Countries affected | Overlay/Index affected | Methodology adjustment | Flag emitted | Evidence D-block | Review horizon |
|-------|-----------------|-------------------|------------------------|----------------------|--------------|------------------|----------------|
| Eurostat PT mirror | INE PT nacional indicadores (GDP, IP, retail, unemployment, consumer confidence) | PT | E1-activity, E3-labor, E4-sentiment, expected-inflation | Eurostat usa EU harmonized definitions (e.g. HICP vs CPI); vintage pode divergir marginalmente de INE PT. Unemployment definition ILO harmonized = INE method equivalent | `PROXY_APPLIED`, `INE_MIRROR_EUROSTAT` | D2 §7 (INE endpoint returns empty `Dados`) + CAL-022 | Phase 1 post-connector; CAL-022 resolves |
| `USPHCI` OR ECRI WLI OR Conference Board scrape | Conference Board LEI (US E2) | US | E2-leading | Methodology depende de proxy escolhido em CAL-023. USPHCI é coincident-leading business conditions; ECRI WLI é weekly leading; CB scrape paid é LEI canonical. Decision pending | `PROXY_APPLIED`, `LEI_US_PROXY` (specific suffix per escolha) | D2 §3 (USSLIND descontinued 2020) + CAL-023 | Phase 1 pre-connector choice |
| `DFEDTARU` + `DFEDTARL` pair | `DFEDTAR` single-rate (discontinued 2008-12) | US | M1-effective-rates | `DFEDTAR_midpoint = (DFEDTARU + DFEDTARL) / 2`. FEDFUNDS effective rate é dual-reported separate. Methodology identical (Fed target rate concept preserved; just adapted para target range regime pós-2008). **NOT a proxy strictly** — it's upgrade of discontinued series to current regime; listed here para clarity | `FED_TARGET_RANGE` (informational) | D2 §3 (DFEDTAR last 2008-12-15) + CAL-024 | Never (permanent — Fed regime is stable) |
| OECD direct SDMX-JSON 2.0 | FRED `OECDLOLITOAASTSAM` mirror | All T1 + T2 partial | E2-leading (`oecd_cli`) | **NOT a proxy** — same OECD MEI_CLI series; different access (direct vs FRED mirror). Catalogado aqui para clarity que é source swap, não proxy swap. FRED mirror stale 2022-11 (D2) → OECD direct fresh 2025-12 | `OECD_CLI_DIRECT` (informational) | D2 §8 | Never (OECD is canonical); FRED mirror deprecated |
| Policy rate observed + ZLB flag | Shadow rate (Krippner, Wu-Xia) | All non-(US, EA, UK, JP) T1 countries | M1-effective-rates, M2-taylor-gaps | Quando shadow rate academic não disponível (4 países only), M1 usa `effective_rate = policy_rate` com flag `ZLB_UNADJUSTED` se `policy_rate ≤ 0.25%`. Methodology note: assume no unconventional policy stance (simplification aceite per ROADMAP) | `ZLB_UNADJUSTED` (per flags.md) | D1 §4.3 + CAL-015 | Phase 2+ shadow rate expansion |
| Rating-implied spread via CRP Pattern 2 | Sovereign CDS 5Y (worldgovernmentbonds.com scrape) | ~160 T3+T4 countries (CDS illiquid) | overlays/crp | Registado via `overlays/crp.md` hierarchy (Pattern 2 best-of). Documentado aqui para clarity que rating-implied é proxy, não fallback (rating é different concept from CDS — rating é categorical/slow-moving; CDS é market-implied instantaneous) | `CDS_LIQUIDITY_LOW`, `CRP_RATING_IMPLIED` | — (concept-level) | Phase 2+ if CDS coverage improves |
| SPF / UMich expectations + term premium decomposition | Breakevens (nominal yield − TIPS real yield) | Countries without liquid linker markets (most T2+, some T1 exceptions) | overlays/expected-inflation, M3-market-expectations | `expected_inflation_proxy = SPF_or_survey − risk_premium_estimate`. Methodology: substitute professional forecasts; residual term premium per academic decomposition (Kim-Wright, ACM). Flag communicates degraded confidence | `BREAKEVEN_PROXY_SURVEY` | — (spec-level) | Phase 2+ BEI decomposition |

## Flag emission convention

Todo o proxy em uso emite:

1. **Flag canónica `PROXY_APPLIED`** (genérica, catalogada em `flags.md`).
2. **Flag específica** por proxy ID (e.g. `INE_MIRROR_EUROSTAT`, `LEI_US_PROXY`, `ZLB_UNADJUSTED`, `BREAKEVEN_PROXY_SURVEY`).

Consumer specs propagate flag per `flags.md` §Convenção de propagação; confidence cap ajustment está documentado em `composite-aggregation.md`:

- **1 proxy em uso**: confidence cap −0.10 (multiplicativo no Policy 1 confidence).
- **≥ 2 proxies** em cadeia (e.g. ECS consume breakeven proxy + INE mirror): cap −0.20 (compoundable mas bounded).

## Justification requirement

Cada proxy novo à registry exige PR contendo:

1. **Theoretical justification**: qual o mesmo conceito económico que o proxy substitui. 2-4 frases em prose. Deve citar academic reference OR industry standard se aplicável.
2. **Empirical evidence**: D-block finding, D1/D2 test result, OR spec-level analysis quando proxy surge em desenho.
3. **Methodology adjustment**: o que difere entre original e proxy (unit, semântica, vintage, perimeter).
4. **Review horizon**: quando re-visitar (Phase 2, ongoing, specific CAL item, never).
5. **Flag specific name** proposta + adição a `flags.md`.

**Anti-pattern**: adicionar proxy "by convenience" sem theoretical grounding. Se rationale é "série X não existe, usemos série Y" sem argument of same economic concept, isto é **proxy abuse** — rejected.

## Escalation path

Quando proxy em uso degrada empiricamente (e.g. divergência crescente vs canonical):

1. Spec owner observes divergence (monitoring / xval).
2. Flag emission frequency > threshold → issue backlog item.
3. Re-avaliar proxy: (a) try different proxy, (b) accept gap (mark `COVERAGE_INSUFFICIENT`), (c) invest in canonical path (Phase 2+).

## FROZEN status

Alterações a esta registry (add/remove/modify proxy entries) requerem PR dedicado. Scope includes:

- Nova proxy entry → PR contendo justification §4 items + flag addition em `flags.md`.
- Proxy retirement (quando canonical path resolved) → PR removendo entry + mudança em affected specs + flag deprecation em `flags.md`.
- Methodology adjustment em proxy existente → PR com rationale + backtest se disponível.

## Cross-references

- [`patterns.md`](patterns.md) — Pattern 2 (Hierarchy best-of — fallbacks) vs Pattern 4 (TE primary + native overrides). Proxies são ortogonais a ambos — podem coexistir dentro de qualquer pattern.
- [`flags.md`](flags.md) — `PROXY_APPLIED` genérica + flags específicas por proxy ID. Catálogo updates per PR dedicado.
- [`composite-aggregation.md`](composite-aggregation.md) — Policy 1 re-weight + confidence cap interaction com flags proxy.
- [`methodology-versions.md`](methodology-versions.md) — methodology bump quando proxy introduzido em spec (MAJOR ou MINOR consoante).
- [`../../adr/ADR-0005-country-tiers-classification.md`](../../adr/ADR-0005-country-tiers-classification.md) — tiers affect proxy applicability (T1 raramente usa proxies; T3+ depende).
- [`../../backlog/calibration-tasks.md`](../../backlog/calibration-tasks.md) — CAL items (CAL-015, CAL-022, CAL-023, CAL-024) relacionados a proxy decisions.
- [`../../data_sources/D2_empirical_validation.md`](../../data_sources/D2_empirical_validation.md) — evidence base para proxies catalogados.

## Referências externas

- Nelson, C. & Siegel, A. (1987) — proxy concept em yield curve fitting (single factor proxying curve shape).
- Kim, D. & Wright, J. (2005) — term premium decomposition para breakeven proxies.
- Conference Board — LEI methodology (original series proxied para US E2).
