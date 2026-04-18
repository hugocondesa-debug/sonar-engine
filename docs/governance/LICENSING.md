# Data licensing

> Audit formal de licensing / ToS para todos os sources catalogados em `docs/data_sources/*.md`.
> **Scope:** complementar a [`DATA.md`](DATA.md) (data handling: secrets, retention, backup, PII). Este doc foca exclusivamente em licensing, attribution e use case permissions.
> **Status:** not FROZEN — evolui com operational learning + novos sources.
> **Última revisão:** 2026-04-18 (Phase 0 Bloco D4).

---

## 1. Overview

SONAR v2 ingere data de 15+ sources com licensing profiles distintos. Cada uso (internal compute, dashboard, client report, published article, API redistribution) tem permissions diferentes per source. Este doc consolida:

- License type e attribution requirement per source.
- Use case matrix: o que cada source permite em cada output type.
- Compliance flags + publication checklist.

Relationship com `DATA.md`: separado porque licensing audit cresce com cada novo source + tem review trigger próprio (ToS updates, legal events); `DATA.md` foca policies operacionais intra-org (secrets, backup, PII) que mudam por razões diferentes.

**D-block evidence base:** [`../data_sources/D0_audit_report.md`](../data_sources/D0_audit_report.md), [`D1_coverage_matrix.csv`](../data_sources/D1_coverage_matrix.csv), [`D2_empirical_validation.md`](../data_sources/D2_empirical_validation.md) documentam operational findings por source.

---

## 2. Source licensing table

Legend: ✓ verified per ToS; ~ assumption baseada em domain knowledge + recommended Phase 2+ verification; ? unclear.

| # | Source | Auth | License type | Attribution req. | Source of determination |
|---|--------|------|--------------|------------------|-------------------------|
| 1 | **Trading Economics (TE)** | API key (Premium trial) | Commercial ToS | Recommended (best practice) | TE Enterprise Terms; Hugo confirmou 2026-04-18 (Override 1) — full liberty para 7365 Capital outputs |
| 2 | **FRED** (St. Louis Fed) | API key | Public domain | Required ✓ | Federal Reserve public data mandate (U.S. Code Title 17 §105: US government works public domain) |
| 3 | **FMP** (Financial Modeling Prep) | API key (legacy, lapsed) | Commercial ToS | Required ✓ | FMP ToS; subscription lapsed D1 — **parked Phase 2+** |
| 4 | **TCMB EVDS** | API key (endpoint broken D1) | Academic free ~ | Required ~ | EVDS terms page (not verified per D1 endpoint issue); **parked CAL-018** |
| 5 | **BIS Statistics** | none (public) | CC-BY-4.0 ✓ | Required ✓ | BIS website disclaimer: "BIS data may be freely used, subject to attribution" |
| 6 | **OECD** (SDMX + MEI_CLI) | none | CC-BY-4.0 ✓ | Required ✓ | OECD Terms and Conditions: Creative Commons Attribution 4.0 International |
| 7 | **ECB SDW** | none | ECB re-use (≈ CC-BY) ✓ | Required ✓ | ECB re-use conditions: free re-use with source acknowledgement |
| 8 | **Eurostat** | none | Eurostat re-use (≈ CC-BY-4.0) ✓ | Required ✓ | Eurostat free-re-use-policy page |
| 9 | **INE Portugal** | none (endpoint broken D2) | Open Data PT (CC-BY compatível) ~ | Required ✓ | dados.gov.pt policy (assumption baseada em padrão portugués; Phase 2+ verify) |
| 10 | **Bundesbank / BoE / BoJ / SNB / Riksbank / MoF JP / ONS / StatCan / ABS / INSEE / Destatis / ISTAT / INE ES / CBS** | none | Open government data (varies per CB) | Required ~ (per-CB attribution string) | Most central banks + stat offices têm open data licenses (Open Government Licence UK, similar others); **Phase 2+ per-CB verify**. Default: attribution required. |
| 11 | **Shiller Yale** (ie_data.xls) | none (static file) | Academic free-use ✓ | Required ✓ | Shiller webpage: "Freely available for academic use; please cite" |
| 12 | **Damodaran NYU** (datasets) | none (static files) | Academic free-use ✓ | Required ✓ | Damodaran website: "Data available for teaching + research use; attribution requested" |
| 13 | **worldgovernmentbonds.com** (CDS scrape) | none (scrape) | Ethical scrape ~ | Preferred ~ | Website TOS: data shown publicly; respect robots.txt + polite rate. Hugo Override 2: audit-internal only |
| 14 | **AAII** (sentiment survey) | none (scrape) | Public survey + ToS ~ | Preferred ~ | AAII ToS: survey results free to display with attribution; redistribution as data product restricted. Override 2: composites-only output |
| 15 | **CFTC COT** | none | Public domain ✓ | Required ✓ | U.S. Government work (Title 17 §105); public disclosure per CFTC statutes |
| 16 | **FINRA margin debt** | none | Public disclosure ✓ | Required ✓ | FINRA free public data via finra.org |
| 17 | **Agency press releases** (S&P / Moody's / Fitch / DBRS) | none (scrape) | Copyright agency; factual citation permitted ✓ | Required ✓ | Agency copyright on commentary text; factual rating values (e.g. "BB-") are public facts — citing OK. Historical rating database commercial product — NOT redistributable |
| 18 | **Conference Board LEI** | paywall | Proprietary (commercial membership) | — | Rejected D2 ($1 000+/year membership); **not in use** — proxy path via CAL-023 |

**Totals:** 15 in-use sources (excluding FMP parked, TCMB parked, Conference Board rejected) com licensing clear. 3 marked assumption (~) requiring Phase 2+ legal verification.

---

## 3. Attribution strings canónicas

Padrão para outputs que cite data directamente (client reports, published articles, dashboard footer).

| Source | Canonical attribution string |
|--------|------------------------------|
| TE | "Data: Trading Economics" (recommended, best practice) |
| FRED | "Data: Federal Reserve Economic Data (FRED), Federal Reserve Bank of St. Louis" |
| BIS | "Source: Bank for International Settlements (CC-BY 4.0)" |
| OECD | "Source: OECD (CC-BY 4.0)" |
| ECB SDW | "Source: European Central Bank" |
| Eurostat | "Source: Eurostat (CC-BY 4.0)" |
| INE Portugal | "Fonte: INE Portugal" |
| Bundesbank / BoE / BoJ / central banks nativos | "Source: <Central Bank name>" (per-CB specific) |
| Shiller | "Shiller, R. J., Yale University" |
| Damodaran | "Damodaran, A., NYU Stern School of Business" |
| CFTC | "Source: U.S. Commodity Futures Trading Commission (CFTC)" |
| FINRA | "Source: FINRA" |
| Agency rating actions | "<Agency name>" (e.g. "S&P Global Ratings", "Moody's Investors Service", "Fitch Ratings", "DBRS Morningstar") |
| Scrape sources (worldgovernmentbonds.com, AAII) | **N/A** — raw data não aparece em outputs (composites-only per Override 2) |

**Rule of thumb:** outputs que carrying data de múltiplos sources listam attribution em section "Sources" no footer ou anexo. String canónica per source acima é mandatory format; no paraphrasing.

---

## 4. Use case matrix

Cross-table source × output type. Cell values: ✓ permitted, ⚠ permitted with caveat, ✗ not permitted, ? verify.

| Source | Internal compute | Internal dashboard | Client reports | Published articles | API redistribute |
|--------|:----------------:|:------------------:|:--------------:|:------------------:|:----------------:|
| TE | ✓ | ✓ | ✓ | ✓ | ⚠ (raw data as product: revisit Phase 2+ ToS) |
| FRED | ✓ | ✓ | ✓ | ✓ | ✓ |
| BIS | ✓ | ✓ | ✓ | ✓ | ✓ (with attribution per CC-BY) |
| OECD | ✓ | ✓ | ✓ | ✓ | ✓ (with attribution per CC-BY) |
| ECB SDW | ✓ | ✓ | ✓ | ✓ | ✓ (with attribution) |
| Eurostat | ✓ | ✓ | ✓ | ✓ | ✓ (with attribution) |
| INE PT | ✓ | ✓ | ✓ | ✓ | ~ (Phase 2+ verify Open Data PT terms) |
| Native CBs (Bundesbank, BoE, etc.) | ✓ | ✓ | ✓ | ✓ | ~ (per-CB) |
| Shiller | ✓ | ✓ | ✓ | ✓ | ⚠ (academic license; redistribution as commercial data product unclear) |
| Damodaran | ✓ | ✓ | ✓ | ✓ | ⚠ (idem) |
| CFTC | ✓ | ✓ | ✓ (composites) | ✓ (composites) | ✗ (raw data as product) |
| FINRA | ✓ | ✓ | ✓ (composites) | ✓ (composites) | ✗ (raw data as product) |
| worldgovernmentbonds.com (scrape) | ✓ | ✓ | ✓ (composites) | ✓ (composites) | ✗ (raw data) |
| AAII (scrape) | ✓ | ✓ | ✓ (composites) | ✓ (composites) | ✗ (raw data) |
| Agency press releases | ✓ | ✓ | ✓ (factual cite) | ✓ (factual cite; paraphrase rationale) | ✗ (historical DB as product) |

**Notes:**
- **TE (Override 1 Hugo 2026-04-18):** internal/client/published OK sem restrições; API redistribution as data product é edge case — Phase 1 não expõe API; revisitar Phase 2+ se roadmap incluir.
- **Scrape sources (Override 2 Hugo):** output layer consome apenas composites/derived (e.g. F4 score), não raw scraped values (e.g. "AAII bull 42%"). Raw data retained in internal tables para audit. Attribution não necessária em outputs porque raw não aparece.
- **Agency press releases (Override 3 Hugo):** rating value ("BB-") é factual public fact — citable. Agency rationale commentary — paraphrase only, no verbatim. Historical rating database — audit-internal only, not distributable.
- **CFTC/FINRA:** public data mas redistribuindo raw series as API product é commercial territory; composites (F4 sub-index) OK.

---

## 5. Compliance flags

### 5.1 Catalogued em `conventions/flags.md`

- **`ATTRIBUTION_REQUIRED`** — output cita data from source com mandatory attribution. Consumer spec emits when propagating data to output layer. Per §3 canonical strings acima.

### 5.2 Audit-internal only (não catalogued)

- **`SCRAPE_SOURCE`** (per Override 2) — audit-internal flag em raw table metadata / connector logs. Track data lineage sem propagation para consumer specs ou output layer. Não em `flags.md` catalog.

### 5.3 Deprecated (D4 closure)

- **`LICENSE_REVIEW_NEEDED`** — referenced em `DATA.md:77` pre-D4 como marker de per-source adjudication pending. **Resolvido em D4 per-source em §2 desta tabela.** Não catalogued em `flags.md` (era placeholder conceptual, nunca emit em production). Marker migrates para `flags.md` §Futuras como deprecated.

---

## 6. Operational rules per output type

### 6.1 Internal compute (connector + overlay + index layers L0-L3)

- All sources permitted.
- Attribution não tracked per-computation; tracked per-output when aggregation reaches L7 outputs.

### 6.2 Internal dashboard (Streamlit MVP, team-facing)

- All sources permitted.
- Footer disclaimer: "Internal dashboard — data per sources catalogued em `docs/governance/LICENSING.md`".

### 6.3 Client-facing reports (PDF / email briefings)

- All sources permitted (post-Override 1).
- Attribution per §3 em "Sources" section no footer do report.
- Scrape sources: composites only (per Override 2).
- Agency ratings: factual cite + agency attribution; paraphrase rationale.

### 6.4 Published articles (Substack, LinkedIn, blog)

- All sources permitted (post-Override 1).
- Attribution per §3 mandatory.
- TE: attribution recommended best practice.
- Scrape composites OK; raw data não aparece.

### 6.5 API redistribution (Phase 2+ conditional)

- **Default:** exclude commercial/scrape sources unless re-computed from public-domain primaries.
- **Phase 2+ decision:** revisit TE ToS if API publicly exposed; revisit scrape ToS per site.
- Public-domain primaries (FRED, CFTC, FINRA, CC-BY sources) redistributable.

---

## 7. Scraping ethics codification

Per Override 2 (Hugo 2026-04-18) scraping é upstream analytical input. Ethical norms:

1. **Respect robots.txt** — every scrape connector fetches `/robots.txt` first; honours `Disallow` directives.
2. **Rate limit polite** — ≤ 1 req/min default; ≤ 1 req/5min para non-industrial sites (worldgovernmentbonds.com, AAII). No aggressive crawl.
3. **Não bypass authentication** — só data publicly displayed; no login automation.
4. **Não paywall circumvention** — se site tem paywall, not scraped. Conference Board LEI paywall é example rejected D2.
5. **User-Agent identifies research** — string: `SONAR-Research/1.0 (macro cycles research; contact hugocondesa@pm.me)`.
6. **Monitor quarterly** — connector metadata includes last-verified-robots-txt date; quarterly re-verify.

**Violation triggers connector halt:** if site returns 403/429 with ToS mention, OR robots.txt change detected → abort connector, flag operator review.

---

## 8. Publication checklist

Pre-publish (client report, Substack article, dashboard section with external visibility):

- [ ] Every data element has source attribution traceable to §3 canonical strings.
- [ ] Scrape sources: only composites/derived values; zero raw scraped values in output.
- [ ] Academic sources cited per §3 (Shiller, Damodaran).
- [ ] Agency ratings: factual values only; rationale paraphrased not verbatim.
- [ ] Attribution section in footer lists all sources used.
- [ ] TE: "Data: Trading Economics" attribution when TE data directly cited (recommended).
- [ ] No verbatim large blocks of ToS-restricted text (agency commentary, proprietary research).

---

## 9. Known gaps / verifications pending

Items marked assumption (~) em §2 que requerem Phase 2+ legal verification:

| # | Source | Assumption | Verification path |
|---|--------|------------|-------------------|
| 4 | TCMB EVDS | Academic free-use commercial unclear | Endpoint recovery (CAL-018) + TCMB support inquiry |
| 9 | INE Portugal | Open Data PT CC-BY compatível | dados.gov.pt terms review + INE contact |
| 10 | Native CBs (≥ 10) | Open government data per-CB varies | Per-CB ToS fetch — batch Phase 2+ |
| 13 | worldgovernmentbonds.com | ToS allows ethical scrape | Site terms page review + confirm per robots.txt |
| 14 | AAII | Survey redistribution as composite OK | AAII membership terms review (Phase 2+ se client demand) |

**Default posture pre-verification:** assume conservative (attribution required; redistribute raw data only when explicit permission).

---

## 10. Review triggers

Re-audit LICENSING.md quando:

1. **TE ToS update** — Premium subscription renewal triggers re-read; document any delta vs Override 1 interpretation.
2. **Novo source added** — connector ingests new source → add row to §2 + §3 + §4 before merging connector PR.
3. **Legal concern raised** — Hugo OR client questioning cite → re-verify per §9 gaps.
4. **Phase 2+ API exposure** — if SONAR exposes REST endpoint externally → revisit API redistribute column §4 por source.
5. **Scrape breakage** — site ToS change detected (robots.txt delta, cease-and-desist email, etc.) → abort connector + update §7.
6. **Agency rating source expansion** — se adicionamos sources beyond S&P/Moody's/Fitch/DBRS → revisit §2 row 17 rationale.

---

## 11. Cross-references

- [`DATA.md`](DATA.md) §Licensing — general tier-based policy (free+attribution / licensed / proprietary / scraping); superseded per-source em LICENSING.md §2.
- [`../data_sources/*.md`](../data_sources/) — source-level details per cycle (endpoints, series, licensing tables per ficheiro §7).
- [`../data_sources/D0_audit_report.md`](../data_sources/D0_audit_report.md), [`D1_coverage_matrix.csv`](../data_sources/D1_coverage_matrix.csv), [`D2_empirical_validation.md`](../data_sources/D2_empirical_validation.md) — D-block evidence for source findings.
- [`../specs/conventions/flags.md`](../specs/conventions/flags.md) — `ATTRIBUTION_REQUIRED` catalogued; `LICENSE_REVIEW_NEEDED` deprecated.
- [`../adr/ADR-0004-ai-collaboration-model.md`](../adr/ADR-0004-ai-collaboration-model.md) — AI attribution for authored outputs.
- [`../backlog/calibration-tasks.md`](../backlog/calibration-tasks.md) — CAL-018 (TCMB recovery), CAL-022 (INE endpoint), CAL-023 (LEI proxy).

---

*Bloco D4 — Phase 0 Data Discovery closure. D-block arquivado após commit.*
