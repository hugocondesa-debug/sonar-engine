# SONAR v1 → v2 — Lessons Document

**Status**: v2.0 · Phase 0 Bloco C em curso
**Última revisão**: 2026-04-18

Lessons document v1→v2. **Não é plano de migração operacional** — v2 é greenfield rewrite, não fork de v1. Este ficheiro explica o que v1 ensinou, o que v2 fez diferente, e o que de v1 foi preservado em [`docs/reference/`](reference/) como knowledge base. Destinado a Hugo (operator) em 12m, colaborador futuro, auditor. Secundária: Claude Code que encontra decisão "estranha" em v2 e precisa contexto histórico.

## 1. Porque v2 não é fork de v1

v1 (2024-2026) acumulou debt técnico incompatível com continuidade: 434 indicadores em 19 connectors sem spec formal; schema drift cross-ciclo onde cada classificador inventava seu próprio layout; confidence não uniforme entre componentes impossibilitando agregação coerente; naming collision onde "sub-modelos" significava três coisas diferentes em partes diferentes do código; copy-paste de outputs externos (Damodaran ERP mensal, Bundesbank Svensson fitted, Shiller CAPE published) em vez de computação própria.

Avaliação em 2026-04 concluiu: custo estimado de refactor in-place + introduzir specs post-facto para 434 indicadores existentes > custo de rewrite com specs-first discipline + número menor de indices bem delimitados (16 × 4-8 components). Decisão foi **greenfield v2** + preservação de v1 como knowledge base read-only. V1 original permanece em repo separado (`github.com/hugocondesa-debug/sonar`) arquivado; content conceptual relevante migrou para [`docs/reference/`](reference/) e [`docs/reference/archive/`](reference/archive/).

## 2. Diagnóstico v1 — 5 classes de debt

### 2.1 Spec-less indicators

434 indicadores sem definição formal: fórmulas copy-pasted cross-file; mudanças silenciosas quando um ficheiro evoluía e outros não; zero testes de regressão; confidence intervals ad-hoc.

**v2 response**: specs-first mandatory. Template canónico em [`docs/specs/template.md`](specs/template.md) (10 secções + §11 non-requirements). Código em `sonar/` só com spec mergeado. 25 specs merged em Phase 0 Bloco B.

### 2.2 Schema drift cross-ciclo

Cada cycle inventava o seu próprio schema: column naming divergente entre tabelas; UNIQUE constraints inconsistentes; alguns carregavam `methodology_version`, outros não; foreign keys ad-hoc.

**v2 response**: frozen contracts em [`docs/specs/conventions/`](specs/conventions/). `methodology_version TEXT NOT NULL` mandatory em toda row persistida. UNIQUE `(country_code, date, methodology_version)` como padrão. Bump rules MAJOR/MINOR formalizadas em [`methodology-versions.md`](specs/conventions/methodology-versions.md).

### 2.3 Confidence não uniforme

Cada indicador tinha semântica própria de confidence: alguns usavam float 0-1, outros 0-100, outros booleanos; missing data tratado diferente em cada lado; impossível agregar confidence cross-cycle de forma coerente.

**v2 response**: Policy 1 (fail-mode re-weighting) uniforme cross-cycle — sub-index missing dispara `{INDEX}_MISSING` flag + re-weight proporcional + confidence cap 0.75. `≥ 3 of 4 indices required`; menos raise `InsufficientDataError`. Flags catalog + propagation rules em [`flags.md`](specs/conventions/flags.md).

### 2.4 Naming collision

"Sub-modelos" significava simultaneamente: (a) calculadoras quantitativas reutilizáveis (NSS, ERP, CRP...), (b) componentes internos de um cycle score, (c) "cycle overlays" (Stagflation, Boom, etc.). Três conceitos ortogonais com mesmo nome.

**v2 response**: [`GLOSSARY.md`](GLOSSARY.md) canónico. Rename explícito **sub-modelos → Overlays (L2)**. Desambiguação formal: **Overlay (L2)** é calculadora quantitativa; **Overlay boolean** é coluna em `*_cycle_scores` (Stagflation/Boom/Dilemma/Bubble); **Regime (L5)** é cenário cruzado reificado (Phase 2+). Três termos distintos para três conceitos distintos.

### 2.5 Published sources as input

Damodaran ERP mensal copy-pasted como input diário; Bundesbank Svensson fitted curves consumidas sem recompute; Shiller CAPE downloaded e inserido directamente. Consequência: dependência de cadências externas (mensal → diário nem sempre válido); zero rastreabilidade; drift silencioso quando sources atualizavam metodologia.

**v2 response**: **compute-don't-consume** como princípio #1 ([`ARCHITECTURE.md §2.1`](ARCHITECTURE.md)). Overlays calculam localmente; fontes published servem como cross-validation contínua via `XVAL_DRIFT` flag quando deviation excede target. ERP em v2: 4 methods paralelos (DCF, Gordon, EY, CAPE) com canonical = median; Damodaran mensal é target de validação, não input.

## 3. Principais renames v1 → v2

| v1 terminology | v2 terminology | Justificação |
|---|---|---|
| sub-modelos | **Overlays (L2)** | Colisão com "cycle overlays"; "overlay" captura melhor "calculador universal reutilizável cross-cycle" |
| cycle overlays (Stagflation, Boom, Dilemma, Bubble) | **Overlay booleans (L4 columns)** / **Regimes (L5, Phase 2+)** | Desambiguação crítica; em v0.1 vivem como colunas booleanas em `*_cycle_scores`, migram para tabela L5 reificada em Phase 2+ |
| 5-layer architecture | **9-layer architecture (L0-L8)** | L3 indices + L5 regimes + L8 pipelines explicitados; v1 fundia L3+L4 em "cycles" genérico e L8 em ad-hoc scripts |
| `docs/methodology/` | **`docs/reference/`** | Knowledge base vs implementation plans separados; `reference/` é read-only histórico, `data_sources/` é operacional Phase 1+ |

## 4. O que foi preservado de v1

- **Knowledge base conceptual** — 4 manuais v1 convertidos para [`docs/reference/`](reference/) (cycles/, indices/, overlays/). **32.063 linhas** totais, read-only. Fonte canónica para definições metodológicas; specs v2 referenciam directamente onde aplicável.
- **Data source plans** — [`docs/data_sources/`](data_sources/) (4 ficheiros: economic, credit, monetary, financial). **4.312 linhas**. Catálogo de sources por ciclo com tier, endpoint, autenticação, rate limits, freshness. Revisão operacional em Bloco D Phase 0 antes de Phase 1 arrancar.
- **Fixtures historical PT** — 2007 CRP ~20 bps · 2012 CRP peak ~1500 bps · 2009 DSR peak · 2012 CCCS distress · 2019 normalização · 2026 CRP ~54 bps. Anchors canónicos em specs de cycles + overlays como validation targets.
- **Código v1 residual** (conceptual) — [`docs/reference/archive/v1-code/`](reference/archive/v1-code/) com `BaseConnector` v1 + `schema_v18.sql`. Read-only para inspecção de ideias reaproveitáveis durante Phase 1 (não como blueprint).
- **CODING_STANDARDS-v1** — arquivado em [`docs/reference/archive/CODING_STANDARDS-v1.md`](reference/archive/CODING_STANDARDS-v1.md). Content relevante migra para `docs/governance/WORKFLOW.md` em Bloco 6.

## 5. O que NÃO foi preservado

- **Listagem dos 434 indicadores v1** — não há inventário agregado. Cada spec v2 escolhe inputs do zero baseando-se em manuais conceptuais; resultado é ~50-80 input series concretos (16 indices × 4-8 components), não 434.
- **Schemas SQL v1** — `schema_v18.sql` preservado em archive mas v2 usa SQLAlchemy 2.0 + Alembic migrations, schema redesenhado com `methodology_version` + confidence + flags em toda row.
- **Confidence semantics v1** — v2 redefine confidence do zero (Policy 1 re-weight, cap 0.75, propagação formalizada).
- **Dashboard v1** — Phase 3+ reconstrói (Streamlit MVP; React production condicional Phase 4+).
- **Tests v1** — zero ported. Phase 1 requer pytest suite com fixtures historical PT desde o primeiro PR de código.
- **Orquestração v1** — scripts ad-hoc substituídos por [`docs/specs/pipelines/`](specs/pipelines/) (6 stubs: daily-curves, daily-overlays, daily-indices, daily-cycles, weekly-integration, backfill-strategy).

## 6. Princípios v2 como respostas ao debt v1

| Debt v1 | Princípio v2 |
|---|---|
| Spec-less indicators | **Specs-first** — template obrigatório; código só com spec aprovado |
| Schema drift | **Frozen contracts** em `docs/specs/conventions/`; PR dedicado para alterar |
| Confidence não uniforme | **Policy 1** — re-weight uniforme cross-cycle + confidence cap 0.75 |
| Naming collision | **GLOSSARY.md canónico** + desambiguações L2/L4/L5 explícitas |
| Published sources as input | **Compute-don't-consume** (princípio #1) |
| Calibração a olho | **Compute-before-calibrate** — placeholders declarados; recalibração empírica Phase 4 com ≥ 24m production data |
| 5-layer implicit | **9-layer explicit (L0-L8)** com I/O contracts formais por camada |
| Ad-hoc orchestration | **Specs-first for pipelines também** — 6 stubs pre-implementation |

## 7. Porque greenfield > refactor

Custo de mover 434 indicadores para specs formais post-facto — reverse-engineering de assumptions não documentadas, confidence semantics divergente, naming collisions entrelaçadas — estimado maior que custo de redefinir inputs de 16 indices bem delimitados desde zero. Rewrite permitiu ainda canonical approaches emergirem por convergência (median para ERP parallel methods, hierarchy best-of para CRP, `clip(50 + 16.67·z, 0, 100)` para normalização em 4 cycles independentes) em vez de cada componente inventar a sua — fenómeno impossível em refactor incremental onde conventions existentes constrangem escolhas.

V1 como **knowledge base** é materialmente mais útil que v1 como código legacy: manuais conceptuais são referência consultável; código é friction com assumptions enterradas, tests inexistentes e dependencies drift. `docs/reference/` (32k linhas conceptuais) presta o serviço de "porquê"; código v1 em `docs/reference/archive/v1-code/` fica por completude, não por utilidade operacional.

## 8. Arquivo v1 — localização operacional

| Tipo | Path v2 | Estado |
|---|---|---|
| Repo v1 original | `github.com/hugocondesa-debug/sonar` (separado) | read-only, arquivado |
| Manuais conceptuais | [`docs/reference/`](reference/) | read-only · 32.063 linhas |
| Código v1 conceptual | [`docs/reference/archive/v1-code/`](reference/archive/v1-code/) | read-only · BaseConnector + schema v18 |
| Standards v1 | [`docs/reference/archive/CODING_STANDARDS-v1.md`](reference/archive/CODING_STANDARDS-v1.md) | legacy · content migra para governance (Bloco 6) |
| Incidents históricos | [`docs/security/incidents/`](security/incidents/) | post-mortems preserved (ex: `2026-04-17-pat-leak.md`) |
| Data plans v1 (revistos) | [`docs/data_sources/`](data_sources/) | operacional Phase 1+ · 4.312 linhas |

Critério de remoção do archive: **Phase 2 completa** (lessons absorvidas, L2-L4 implementados). `docs/reference/` (knowledge base conceptual) permanece indefinidamente.

---

*Phase 0 Bloco 4c · live document — atualiza quando novas lessons ou preservações v1 emerjam.*
