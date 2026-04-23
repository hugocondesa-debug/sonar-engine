# ADR-0009: National-CB connectors for EA periphery curves — pattern inversion + probe discipline

**Status**: Accepted
**Data**: 2026-04-22
**Decisores**: Hugo Condesa
**Consultados**: —

## Contexto

Week 10 Sprint A (`docs/planning/week10-sprint-a-ea-periphery-brief.md`)
estabeleceu o padrão "national-CB connector per country" como
caminho pós-ECB-SDW para cobrir PT / IT / ES / FR / NL no
`daily_curves` pipeline. A expectativa de design — capturada no Sprint
A retro + no template da Sprint D brief — era de que cada CB nacional
(Bundesbank precedente para DE; Banque de France, Banca d'Italia,
Banco de España, Banco de Portugal, De Nederlandsche Bank para
periphery) exporia uma API pública comparável ao `BBSIS.D.I.ZAR.ZI`
do Bundesbank: SDMX-JSON ou CSV, per-tenor, cadência diária,
histórico multi-década, sem autenticação. O umbrella
`CAL-CURVES-EA-PERIPHERY` foi decomposto em cinco CAL items
per-country com budgets de 3-4h CC cada, totalizando ~15-20h CC
Week 11 para cobrir toda a periphery.

Week 10 Sprint D pilot (2026-04-22, `docs/planning/week10-sprint-d-fr-bdf-brief.md`)
executou o primeiro dos cinco — Banque de France via webstat — e
invertou a assunção do padrão. O pre-flight empírico enumerado no
§9 do brief (BdF primary → AFT → TE → FRED) falhou em todos os quatro
níveis:

1. **BdF legacy SDMX-JSON REST** (`https://webstat.banque-france.fr/ws_wsfr/rest/data/`)
   devolveu HTTP 404 em todas as combinações dataflow/série. A Banque
   de France decomissionou o endpoint quando migrou `webstat` para a
   plataforma OpenDatasoft em meados de 2024 (a publicação final do
   ficheiro `Taux_indicatifs_et_OAT_Archive.csv` data de 2024-07-11,
   coincidente com a janela de migração).
2. **BdF OpenDatasoft explore API** (`https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets`)
   devolveu `total_count=1` — o único dataset exposto
   (`tableaux_rapports_preetablis`) contém um ficheiro
   yield-adjacent (`Taux_indicatifs_et_OAT_Archive.csv`) com 8 tenores
   {1M, 3M, 6M, 9M, 12M, 2Y, 5Y, 30Y}, **sem 10Y benchmark**, cadência
   end-of-period mensal, marcado "Archive" com publicação congelada em
   2024-07-11. Insuficiente para `daily_curves` tanto em frequência
   (mensal vs diária) como em completeness de tenor (10Y benchmark
   ausente).
3. **Agence France Trésor (AFT)** (`https://www.aft.gouv.fr/`)
   devolveu HTTP 403 atrás de Cloudflare managed-challenge
   (`cf-mitigated: challenge`). Fetch programático bloqueado sem
   browser-automation shim — não viável para pipelines headless.
4. **TE `fetch_fr_yield_curve_nominal`** — nunca shipped Sprint CAL-138
   (o probe CAL-138 confirmou que FR expõe apenas `GFRN10:IND` = 10Y
   single-tenor via `/markets/historical`, abaixo do
   `MIN_OBSERVATIONS=6` requerido para NSS fit).
5. **FRED OECD mirror** (`IRLTLT01FRM156N`) — 10Y mensal, single-tenor.
   Insuficiente.

HALT trigger 0 do brief §5 disparou. O padrão "Bundesbank analog per
country" **não é extrapolável sem probe empírico** — a Banque de
France ilustrou que um CB da zona euro pode decomissionar a sua API
pública histórica num intervalo de 12-24 meses sem sinalização
pública clara no canal do SONAR. As quatro sprints successoras
(`CAL-CURVES-IT-BDI` / `CAL-CURVES-ES-BDE` / `CAL-CURVES-PT-BPSTAT` /
`CAL-CURVES-NL-DNB`) partilham o mesmo risco de migração/
decommission; a NL-DNB em particular migrou já para a mesma
plataforma OpenDatasoft que revelou a falha BdF, sendo portanto o
risco mais elevado dos quatro successors.

A decisão tem de formalizar o que aprendemos para:

- proteger as quatro sprints successoras de uma falsa partida
  idêntica à Sprint D;
- documentar o estado da Sprint D para que um operator futuro
  retomando FR tenha o probe matrix completo sem precisar de
  re-executar os cinco probes;
- re-framar o budget total Week 11+ para EA periphery a partir do
  pressuposto de que zero a quatro dos successors vão atingir
  HALT-0 no pre-flight (o que invalida o cálculo 4 × 3-4h do plano
  Week 11).

## Decisão

Adoptamos **"probe antes de scaffolding"** como disciplina
operacional para os quatro CAL items per-country successors:

1. Cada sprint national-CB começa obrigatoriamente com um **pre-flight
   CB-API state probe em Commit 1** que verifica empiricamente se a
   API histórica da CB continua a servir per-tenor daily yields, antes
   de qualquer scaffolding de connector. O probe inclui: (a) URL da
   API documentada (SDMX / REST / CSV); (b) reachability HTTP 200/404;
   (c) dataset discovery via catálogo / index; (d) per-tenor series
   code discovery; (e) frequência + histórico + licensing.
2. Se o probe **confirma viabilidade** (HTTP 200 + ≥ 6 tenores + daily +
   público), a sprint procede com o padrão Bundesbank analog — connector
   completo, pipeline dispatch, cassettes, canary, retro.
3. Se o probe **falha** (HALT-0), a sprint procede com o padrão
   Sprint D pilot — **documentation-first scaffold** (`sonar/connectors/{cb_slug}.py`
   com docstring recording probe findings, `InsufficientDataError`
   stub, constants pointer para CAL), CAL entry BLOCKED, addendum a
   este ADR com o novo probe matrix, retro v3.
4. Budget cada sprint **4-5h CC** (vs os 3-4h originais) para cobrir
   o probe + buffer de migration-risk + scaffold-OR-full-impl
   bifurcação.
5. A expectativa Week 11+ muda de "4 sprints × 3-4h = 12-16h" para
   "4 sprints × 4-5h = 16-20h com probability P(HALT-0 per sprint)
   ≈ 0.3-0.5", consistente com o facto empírico 1-of-5 da Sprint D
   pilot e o elevado risco do migration-shared cluster NL-DNB.

## Alternativas consideradas

- **Opção A** ← escolhida. Probe-first discipline + Sprint D scaffold
  template para HALT-0 outcomes. Preserva progresso incremental
  (cada sprint fecha com artefactos tangíveis mesmo se HALT-0
  dispara); mantém o interface `BaseConnector` frozen para a
  future methods-only swap-in; aceita que alguns national-CB
  connectors ship BLOCKED até alternative-source research track
  resolver.
- **Opção B** — HALT umbrella: pausar todas as quatro sprints
  successoras até que um alternative-data-source track (Bloomberg
  licensed / Refinitiv / FactSet) resolva o problema de raiz.
  Rejeitada: cria dependência Phase 2+ (licensed feeds) num
  workstream que pode ser parcialmente destrancado sem budget de
  licensing — IT e ES têm probability razoável de ship sem HALT-0
  se a Banca d'Italia / Banco de España não migraram.
- **Opção C** — EA-aggregate uniform: abandonar per-country
  periphery curves definitivamente, acceptando `EA_AAA_PROXY_FALLBACK`
  para PT/IT/ES/FR/NL permanente. Rejeitada: IT tem o maior
  sovereign-spread range da periphery (2011 crisis, 2018 Lega,
  2022 energy-war) e fixá-lo no EA-aggregate perde o sinal mais
  informativo do rating-spread overlay. Só seria aceitável se
  todos os quatro successors ship BLOCKED.
- **Opção D** — Browser-automation shim first: implementar um
  shim Playwright / Cloudflare-solver para bypass AFT + outras
  fontes bot-bloqueadas antes de qualquer CAL item per-country.
  Rejeitada: scope creep significativo (ops + maintenance de um
  browser stack) para resolver apenas 1-of-5 países (AFT
  especifica FR; IT/ES/PT/NL não passam pelo mesmo block). Fica
  disponível como opção (c) do unblock criteria em `CAL-CURVES-FR-BDF`
  — não é o caminho primário.

## Consequências

### Positivas

- Cada sprint successor fecha com artefactos concretos (scaffold OR
  full impl + CAL update + ADR addendum + retro) mesmo no HALT-0 path
  — evita o anti-pattern "sprint cancelada sem entrega" que Sprint A
  já contornou via CAL decomposition.
- O interface `BaseConnector` + constructor signature ficam frozen
  pelos scaffolds Sprint-D-pattern, permitindo methods-only swap-in
  quando (se) um alternative source resolve o gap — reduz o custo de
  retomar cada CAL blocked.
- O probe-first discipline força a documentação empírica do estado
  das APIs de CBs EA num momento único (Week 10-11), criando uma
  baseline reutilizável para qualquer audit futura do pipeline.
- Operator-facing error messages consistentes entre os cinco países
  (todos citam CAL pointer + probe date + findings summary), reduzindo
  o overhead de triage no pipeline log.

### Negativas / trade-offs aceites

- Budget total EA-periphery Week 11+ inflaciona 30-50 % vs o plano
  original (12-16h → 16-20h), incluindo o caso em que zero successors
  ship full-impl.
- FR curve fica em proxy EA-aggregate indefinidamente até que alguma
  das três condições de unblock (BdF restauração / licensed feed /
  browser shim) se materialize — o spread FR-específico não aparece
  no rating-spread overlay.
- Accept-ship scaffold pattern requer que downstream consumers
  (daily_overlays, daily_cost_of_capital) continuem a tratar FR
  como proxy-fallback path sem warnings adicionais — o EA_AAA_PROXY
  flag existente já cobre isto, mas significa que um audit futuro
  pode confundir o "scaffold existe" com "connector works".
- Se dois ou mais successors HALT-0, o sinal rating-spread per-country
  na periphery fica permanentemente gated em proxy-fallback, reduzindo
  o valor do ERP cascade em FR/IT/ES/PT/NL para níveis próximos do
  `MATURE_ERP_PROXY_US` que Sprint B shipou.

### Follow-ups requeridos

1. Executar os quatro successor sprints em Week 11+ com probe-first
   discipline. Ordenar por migration-risk:
   - **IT-BDI**: probe Banca d'Italia BDS + `infostat.bancaditalia.it`
     SDMX 2.1. Risco moderado (histórico estável).
   - **ES-BDE**: probe Banco de España `SeriesTemporales`. Risco
     moderado (portal migrado múltiplas vezes mas não para OpenDatasoft).
   - **PT-BPSTAT**: probe `bpstat.bportugal.pt/data/v1`. Risco
     baixo-moderado (BPstat é native REST, não migração conhecida).
   - **NL-DNB**: probe DNB Statistics portal. **Risco elevado** —
     DNB migrou para OpenDatasoft mid-2024 (mesma plataforma que
     revelou a gap BdF); probability ≥ 0.5 de HALT-0.
2. Abrir um workstream Phase 2+ "alternative data sources for EA
   sovereign curves" cobrindo: licensed feeds (Bloomberg BVAL /
   Refinitiv Eikon / FactSet), browser-automation shim (AFT +
   outros bot-bloqueados), e cross-validation contra ECB IRS monthly
   single-tenor para calibração. Não bloqueia Week 11+ successor
   sprints mas delimita o unblock-criteria track.
3. Acrescentar uma §11-style "Pre-flight state probe" secção ao
   `docs/specs/template.md` para que specs de connectors L0 futuros
   (não só EA-periphery) levem disciplina probe-first baked-in.
4. O retro da Sprint D (`docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md`)
   deve incluir o probe matrix completo e o mapeamento 1-to-1 entre
   as 4 condições de unblock e os work-items Phase 2+ que as
   destravariam.

## Addendum Sprint G (2026-04-22) — EA periphery probe outcomes matrix

Sprint G (Week 10 Day 2 combined IT + ES pilot, 2026-04-22)
executou sprints 2 + 3 dos quatro successors ADR-0009 em paralelo
(worktree isolado, zero conflito de ficheiros com Sprint F / Sprint
E). Ambos os probes aterraram em HALT-0, mas por sub-casos
diferentes — o pattern library é agora ternário em vez de binário.

### Matriz de resultados probe-first empírica (acumulativa)

| País | Probe date | Sub-caso HALT-0 | Artefacto shipped | Unblock primário |
|---|---|---|---|---|
| **FR-BDF** | 2026-04-22 (Sprint D) | HTTP 4xx / deprecated (legacy SDMX decommissioned mid-2024 → OpenDatasoft monthly-archive-only) | `banque_de_france.py` scaffold + ADR-0009 original | BdF daily yield feed restore / licensed feed / browser shim |
| **IT-BDI** | 2026-04-22 (Sprint G) | HTTP "all paths dead" (ECB legacy SDMX decommissioned; BdI Infostat API subdomains NXDOMAIN; MEF HTML-only; ECB SDW FM + IRS EA-aggregate; FRED 10Y-monthly) | `banca_ditalia.py` scaffold + esta addendum | BdI publishes public SDMX/REST / licensed feed / Infostat SPA browser shim |
| **ES-BDE** | 2026-04-22 (Sprint G) | HTTP 200 + **non-daily** (BdE BIE REST `app.bde.es/bierest` live + publishes 11-tenor ES sovereign yields, but all at `codFrecuencia='M'` monthly) | `banco_espana.py` scaffold + esta addendum | BdE publishes daily Bono yields / `daily_curves` gains monthly-cadence path / parallel `monthly_curves` pipeline / licensed feed |
| **PT-BPSTAT** | Pending | — | — | — |
| **NL-DNB** | Pending | — | — | — |

### Pattern library — três sub-casos HALT-0 distintos

O Sprint D original codificou um binário "HTTP 200 + ≥ 6 tenores +
daily + public" → full impl; **caso contrário** → scaffold. Sprint
G revela que o segundo ramo tem estrutura interna relevante:

| Sub-caso | Sinal empírico | Evidência | Exemplo |
|---|---|---|---|
| **A. 4xx / deprecated** | Host legacy retornou 404 + plataforma successora existe mas com dataset incompleto | HTTP 404 no legacy + 200 no successor com tenor/frequência-gap | FR-BDF (BdF → OpenDatasoft) |
| **B. All paths dead** | Zero reachability + zero successor path | HTTP 000 / NXDOMAIN no legacy + nenhum REST público descoberto | IT-BDI (BdI Infostat SPA-only + subdomains NXDOMAIN) |
| **C. HTTP 200 + non-daily** | Endpoint vivo, público, retorna dados solicitados, mas frequência abaixo do pipeline | HTTP 200 + `codFrecuencia='M'` quando pipeline exige `'D'` | ES-BDE (BdE BIE REST monthly-only) |

O sub-caso **C** é o mais subtil porque "funciona" na superfície
(HTTP 200, JSON bem-formado, 11 tenores de coverage) — a discovery
exige verificação explícita da frequência em metadados da API, não
apenas presence checks. Esta é uma lição directa para specs Week 11+
de pipelines L8: todo probe tem de verificar **{reachability,
auth, tenor-count, frequency, historical-depth}** separadamente, não
colapsar em "endpoint responds 200".

### Regra operacional actualizada

ADR-0009 v2 (Sprint G addendum):

1. **Probe matrix expandida** — cada probe tem de medir as cinco
   dimensões acima, não só reachability. Template actualizado para
   sprint briefs successores.
2. **Sub-caso C requer decisão arquitectural explícita** — se um
   probe devolve "HTTP 200 non-daily", o sprint tem de decidir se
   estende o pipeline para aceitar cadência monthly (mudança pipeline-
   wide com implicações de staleness) ou se scaffolds (Sprint G
   escolha). Não é defensável "scaffold porque HALT-0" sem nomear o
   sub-caso.
3. **Pattern inversion a re-confirmar em cada país** — o facto de
   Bundesbank (DE) ser o único successor `full impl` e três de
   cinco successors serem HALT-0 (sub-casos A / B / C) sustenta que
   o padrão DE **não generaliza** mesmo dentro da EU-19. O remaining
   set {PT, NL} deve ser considerado à partida risco ≥ 0.5 de HALT-0,
   com PT potencialmente mais baixo (BPstat é native REST não-migrado)
   e NL mais alto (OpenDatasoft-cluster per Sprint D precedent).

### Follow-ups (Sprint G addendum)

Re-ordenação da §Consequências "Follow-ups requeridos" à luz dos
dois novos probes:

1. **Ordem de execução updated**:
   - **PT-BPSTAT** (próximo; risco baixo-moderado). BPstat é native
     REST `bpstat.bportugal.pt/data/v1` — nunca migrou; high-probabiity
     de **full impl**. Candidato para "primeira vitória no pattern"
     após 3-of-5 HALT-0.
   - **NL-DNB** (último; risco elevado confirmado). DNB migrou para
     OpenDatasoft mid-2024 — **mesma plataforma que revelou a gap
     BdF**. Probability ≥ 0.6 de sub-caso **A** (HTTP 4xx / deprecated
     ou dataset incompleto). Budget full 4-5h CC para scaffold path.
2. **Alternative-data-source workstream** (Phase 2+, unchanged)
   passa de "bloqueante potencial para todos os 5" para "bloqueante
   confirmado para ≥ 3-of-5" após Sprint G. O cost-benefit de
   licensed feed (Bloomberg BVAL / Refinitiv / FactSet) inclina-se
   positivo a partir do threshold 3+ HALT-0s — Sprint G atravessa-o.
3. **Frequency-tier architecture** — abrir ADR Phase 2+ sobre como
   `daily_curves` convive com cadência monthly (sub-caso C). O
   caminho mais provável: `monthly_curves` pipeline paralelo com
   tier-aware overlay cascade (overlays aceitam ambas as cadências
   com flag explícito de staleness).

### Post-Sprint G coverage state

T1 curves coverage unchanged 6/16 (US/DE/EA/GB/JP/CA). Três CAL items
BLOCKED com scaffolds + probe matrix + pattern library: FR / IT / ES.
Dois pendentes: PT / NL. Overlays cascade de FR + IT + ES continua
em EA-AAA proxy-fallback até que ≥ 1 dos {full impl / licensed feed
/ frequency-tier architecture} materialize.

## Addendum Sprint H (2026-04-22) — TE Path 1 canonical (correcção do Sprint G)

Sprint H (Week 10 Day 2 follow-up IT + ES via TE cascade, 2026-04-22)
reabriu as conclusões HALT-0 do Sprint G após descobrir empiricamente
que o brief §2 Sprint G **omitiu** TE (Trading Economics generic
indicator API + `/markets/historical` Bloomberg-symbol endpoint) da
lista de probes executados para IT + ES. Isto constituiu um erro
material de scope: TE já servia GB + JP + CA desde CAL-138
(2026-04-22) via a mesma mecânica `TE_YIELD_CURVE_SYMBOLS`, e a
probe Sprint H 2026-04-22 confirmou que TE expõe as famílias BTP
(`GBTPGR*`) e SPGB (`GSPG*`) com cobertura per-tenor suficiente
para um fit Svensson em ambos os países.

### Resultado empírico Sprint H probe (2026-04-22)

| País | Família Bloomberg | Tenores confirmados | RMSE NSS fit (2024-12-30) | Confiança |
|---|---|---|---|---|
| **IT** | `GBTPGR` (BTP) | **12** (1M-30Y full spectrum; 10Y drops Y suffix: `GBTPGR10`) | **5.23 bps** | **1.0** |
| **ES** | `GSPG` (SPGB) | **9** (missing 1M / 2Y / 20Y; YR-uniform suffix) | **4.41 bps** | **1.0** |

Ambos os fits clearam o acceptance Sprint H §6 (RMSE ≤ 10 bps +
confiança ≥ 0.9) com headroom material (~50 % em RMSE), reproduzível
via `tests/integration/test_daily_curves_multi_country.py::test_daily_curves_it_end_to_end` +
`test_daily_curves_es_end_to_end`.

### Regra operacional Sprint H amendment (ADR-0009 v2)

Consolidação da regra operacional já implícita em CAL-138 + formalizada
aqui como consequência do Sprint G omission:

**Qualquer sprint de country-data probe tem de incluir TE generic
indicator API como Path 1 na matriz §2 pre-flight**, antes dos
national-CB paths (BdF / BdI / BdE / BPstat / DNB / …). A razão é
operacional: TE é o único feed unified-contract que já cobre
simultaneamente 16 países T1, tem rate-limit generoso (Pro tier),
ships per-tenor symbols via `/markets/historical`, e tem source-drift
guards reutilizáveis (HistoricalDataSymbol validation). National-CB
probes só devem ser invocados **após** TE exhaustion empiricamente
confirmada (i.e. TE devolve < MIN_OBSERVATIONS=6 tenores ou non-daily
frequency).

Consequência retroactiva: Sprint G HALT-0 decisions para IT + ES
ficam **corrigidas** — os probes Sprint G não eram "all 5 paths dead"
(IT) nem "HTTP 200 + non-daily" (ES) quando TE Path 1 existe e
funciona. O scaffold work (`banca_ditalia.py` + `banco_espana.py`)
permanece como documentation-first + future direct-CB placeholder
(unblock path se BdI / BdE publicarem daily feeds próprios), mas
o daily_curves pipeline usa TE em Sprint H + forward.

### Pattern library v2 — Path 1 canónico

| Path | Ordem | Implementação | Quando escolher |
|---|---|---|---|
| **Path 1: TE generic cascade** | **Sempre primeiro** | Extend `TE_YIELD_CURVE_SYMBOLS` dict + run per-tenor probe matrix (template scripts em Sprint H brief §2) | Qualquer país T1 que não seja already covered em FRED / Bundesbank / ECB SDW. Cobertura provada 2026-04-22 para IT + ES; GB / JP / CA shipped CAL-138. Não-ship para AU / NZ / CH / SE / NO / DK (< 2 tenors empiricamente) — para esses CAL-CURVES-T1-SPARSE é o tracker. |
| **Path 2: ECB SDW YC / IRS** | Segundo (EA members) | Existing `EcbSdwConnector.fetch_yield_curve_nominal` | EA aggregate (não por país) — já shipped CAL-138. |
| **Path 3: National-CB direct** | Último (post-TE-exhaustion) | Scaffold per ADR-0009 sub-casos A / B / C | Apenas se Path 1 + Path 2 empiricamente inadequados. Bundesbank DE é o único sucesso comprovado do Path 3 entre T1. |

### Updated EA periphery probe matrix (Path 1 canonical)

| País | Path 1 (TE) | Path 3 (National CB) | Status |
|---|---|---|---|
| **DE-Bundesbank** | N/A (Path 3 pre-existing) | ✓ SUCCESS via `BBSIS` (CAL-138) | **SHIPPED** |
| **FR-BDF** | Pending re-probe (`GFRN10` only 10Y per CAL-138 probe; mas CAL-138 não varreu per-tenor) — `CAL-CURVES-FR-TE-PROBE` abre Sprint H | HALT-0 sub-caso A (Sprint D) | BLOCKED pendente TE re-probe |
| **IT-BDI** | ✓ **SUCCESS** 12 tenors (Sprint H 2026-04-22) | HALT-0 sub-caso B (Sprint G — corrigido por Sprint H) | **SHIPPED** via Path 1 (TE cascade) |
| **ES-BDE** | ✓ **SUCCESS** 9 tenors (Sprint H 2026-04-22) | HALT-0 sub-caso C (Sprint G — corrigido por Sprint H) | **SHIPPED** via Path 1 (TE cascade) |
| **PT-BPSTAT** | Pending probe (TE Path 1 obrigatório per amendment) | Pending probe | Pending |
| **NL-DNB** | Pending probe (TE Path 1 obrigatório per amendment) | Pending probe | Pending |

### Follow-ups (Sprint H addendum)

1. **`CAL-CURVES-FR-TE-PROBE`** — aberto Sprint H. CAL-138 probe para
   FR mostrou "TE single-tenor `GFRN10` only", mas essa probe **não
   varreu per-tenor** o spectrum `GFRN1M / GFRN3M / … / GFRN30Y`. Sprint
   H amendment requer varredura per-tenor completa antes de classificar
   FR como "TE inadequate"; Week 11 candidate sprint para executar a
   re-probe per ADR-0009 v2 disciplina.
2. **PT + NL probes** devem começar com TE Path 1 per amendment.
   Budget ajustado para ~2h CC cada se Path 1 sucede (pattern
   replication); 4-5h CC se falha e cai para Path 3 (scaffold per
   pre-existing sub-casos A / B / C).
3. **Scaffolds Sprint G retidos** — `banca_ditalia.py` +
   `banco_espana.py` permanecem in-repo como documentation-first +
   future direct-CB placeholder. Não deleted; referenced explicitly
   nos updated `CAL-CURVES-IT-BDI` + `CAL-CURVES-ES-BDE` entries como
   histórico da tentativa Sprint G + unblock-path future (licensed
   feed / BdI-BdE daily SDMX publication / browser-automation shim).

### Post-Sprint H coverage state

**T1 curves coverage 8/16** (US/DE/EA/GB/JP/CA **+ IT + ES**). Dois
CAL items CLOSED via TE cascade (IT-BDI + ES-BDE). Um BLOCKED
pendente TE re-probe (FR-BDF → `CAL-CURVES-FR-TE-PROBE`). Dois
pendentes (PT-BPSTAT / NL-DNB). Overlays cascade de IT + ES em
produção a partir de 2026-04-23 07:30 WEST (primeira execução
post-merge); FR + PT + NL continuam em EA-AAA proxy-fallback.

Pattern library v2 (CAL-138 TE canonical + Sprint H Path 1
formalization) é a regra active para Week 11+ country-data probes.

## Addendum Sprint I (2026-04-22) — FR via TE Path 1 cascade (closes CAL-CURVES-FR-TE-PROBE)

Sprint I (Week 10 Day 2 follow-up FR via TE per-tenor cascade,
2026-04-22) executou a re-probe Path 1 mandatada pelo amendment v2 do
Sprint H. Resultado: SUCCESS. FR ships via TE cascade — sétimo uso
do pattern (CAL-138 GB / JP / CA + Sprint H IT / ES + Sprint I FR).

### Resultado empírico Sprint I probe (2026-04-22)

Per-tenor sweep da família `GFRN` em `/markets/historical`:

| Tenor | Symbol | Status | Close 2024-12-31 |
|---|---|---|---|
| 1M  | `GFRN1M:IND`  | ✓ daily | 2.69800 |
| 3M  | `GFRN3M:IND`  | ✓ daily | 2.68100 |
| 6M  | `GFRN6M:IND`  | ✓ daily | 2.51050 |
| 1Y  | `GFRN1Y:IND`  | ✓ daily | 2.34180 |
| 2Y  | `GFRN2Y:IND`  | ✓ daily | 2.25750 |
| 3Y  | —             | ✗ all variants empty | — |
| 5Y  | `GFRN5Y:IND`  | ✓ daily | 2.65500 |
| 7Y  | `GFRN7Y:IND`  | ✓ daily | 2.86750 |
| 10Y | `GFRN10:IND`  | ✓ daily | 3.19350 |
| 15Y | —             | ✗ all variants empty | — |
| 20Y | `GFRN20Y:IND` | ✓ daily | 3.49850 |
| 30Y | `GFRN30Y:IND` | ✓ daily | 3.72500 |

**FR total: 10 tenors** — clears `MIN_OBSERVATIONS_FOR_SVENSSON=9`.
Quirk: bare `Y` suffix uniformly em 1Y+ tenores disponíveis (vs ES
`YR` ou IT mixed `Y` / no-suffix); 10Y drops o suffix como `GFRN10`
(matching IT `GBTPGR10` / GB `GUKG10` / JP `GJGB10` precedent).
Missing 3Y + 15Y empiricamente — não-uniformidade do TE Bloomberg
mirror, não defeito da fonte.

NSS fit live canary 2026-04-22 (TE_API_KEY-bearing env, 2024-12-30
target): n=10 tenors · RMSE = **2.005 bps** · confidence = **1.000**
· flags = `()`. Cleaner que IT (5.23) ou ES (4.41) na mesma
pipeline — FR tem cobertura limpa do mid-curve via TE, sem o noise
de 1Y-3Y benchmark-roll que afecta IT.

### Sprint D HALT-0 reframe

A Sprint D (Banque de France pilot, 2026-04-22) tinha concluído
HALT-0 nos quatro paths probed (BdF SDMX legacy 404 + BdF
OpenDatasoft monthly-archive only + AFT Cloudflare-challenged + TE
"GFRN10 10Y-only"). **A entry "TE GFRN10 10Y-only" era ela própria um
artifact de single-symbol probe** — `CAL-138` tinha catalogado FR
apenas como 10Y-disponível porque o probe Bloomberg-symbol assumiu
uniformidade family-wise; a Sprint D inheritou essa entry sem
varrer per-tenor. Sprint H amendment v2 mandatou a re-probe
(`CAL-CURVES-FR-TE-PROBE`); Sprint I executou e empiricamente
confirmou 10 tenores daily. O direct-CB path (BdF SDMX legacy / BdF
OpenDatasoft / AFT) continua dead conforme Sprint D — só a
characterização "TE inadequate" foi corrigida.

`CAL-CURVES-FR-BDF` (Sprint D pilot) **permanece BLOCKED** como
direct-CB upgrade path; a Sprint I closure aplica-se apenas a
`CAL-CURVES-FR-TE-PROBE`. Sprint I C4 sharpens o `CAL-CURVES-FR-BDF`
description para registar a separação canónica entre os dois paths
(Path 1 TE = production-serving; Path 3 national-CB = future
direct-feed upgrade).

### Per-country probe outcomes table (Sprint H + Sprint I)

| País | Probe Path 1 (TE) | Probe Path 3 (national-CB) | Status produção |
|---|---|---|---|
| **GB** | ✓ 12 tenors (CAL-138) | n/a (não EA periphery) | ✓ shipped via TE |
| **JP** | ✓ 9 tenors (CAL-138) | n/a (não EA periphery) | ✓ shipped via TE |
| **CA** | ✓ 6 tenors (CAL-138 NS-reduced) | n/a (não EA periphery) | ✓ shipped via TE |
| **IT** | ✓ 12 tenors (Sprint H) | HALT-0 sub-caso B (Sprint G — corrigido por Sprint H) | ✓ shipped via TE |
| **ES** | ✓ 9 tenors (Sprint H) | HALT-0 sub-caso C (Sprint G — corrigido por Sprint H) | ✓ shipped via TE |
| **FR** | ✓ **10 tenors (Sprint I)** | HALT-0 sub-caso A (Sprint D) | ✓ **shipped via TE** |
| **PT** | Pending probe (TE Path 1 obrigatório per amendment) | Pending probe | Pending |
| **NL** | Pending probe (TE Path 1 obrigatório per amendment) | Pending probe | Pending |

### Pattern library v2.1 — Sprint I empirical reinforcement

A Sprint I é a 7ª aplicação do TE Path 1 cascade pattern e o 3º
caso onde TE Path 1 success **inverteu** uma conclusão prévia de
HALT-0 baseada em probe incompleto (Sprint G IT + ES + Sprint D FR).
Reforço empírico da regra v2 (TE primeiro sempre): **single-symbol
ou single-path probes são insuficientes para concluir HALT-0**;
apenas a varredura per-tenor + per-path completa autoriza essa
conclusão. ADR-0009 v2.1 mantém a regra v2 (sem alteração textual);
addendum v2.1 documenta apenas o probe outcome FR + reframe Sprint D.

### Follow-ups (Sprint I addendum)

1. **`CAL-CURVES-FR-TE-PROBE` CLOSED** — outcome SUCCESS, shipped
   via TE cascade (Sprint I commits ``db8fe82`` C1 + ``93564bc`` C2 +
   ``8e2f6c4`` C3 + C4-TBD).
2. **`CAL-CURVES-FR-BDF` SHARPENED** — direct-CB national path
   continua BLOCKED conforme Sprint D probe matrix; description
   gains Sprint I addendum registando que daily-pipeline surface já
   não depende deste CAL (TE cascade serve), só o future direct-feed
   upgrade path.
3. **PT + NL ADR-0009 successor sprints** — TE Path 1 probe
   obrigatório per amendment v2 (regra inalterada Sprint I).

### Post-Sprint I coverage state

**T1 curves coverage 9/16** (US/DE/EA/GB/JP/CA **+ IT + ES + FR**).
Três CAL items CLOSED via TE cascade (IT-BDI + ES-BDE Sprint H +
FR-TE-PROBE Sprint I). Um BLOCKED conserved (FR-BDF — direct-CB
upgrade path; daily pipeline já não depende). Dois pendentes
(PT-BPSTAT / NL-DNB). Overlays cascade de FR em produção a partir
de 2026-04-23 07:30 WEST (primeira execução post-merge); PT + NL
continuam em EA-AAA proxy-fallback.

Pattern library v2 mantém-se canonical para Week 11+; Sprint I é
puro empirical reinforcement.

## Addendum Sprint M (2026-04-23) — PT via TE Path 1 cascade + NL Path 1 HALT-0 (1ª não-inversão)

Sprint M re-probou **PT + NL** sob a disciplina ADR-0009 v2 (TE Path 1
canonical). O resultado é **assimétrico** — primeira vez em 5
successor sprints que os dois países sob o mesmo brief caem em estados
diferentes:

- **PT**: TE Path 1 PASS 10 tenors (1M + 15Y struct-gap confirmed).
  Cohorts cleanly com IT/ES/FR — a "4ª inversão" da ADR-0009 v1
  framing, reforçando a v2.
- **NL**: TE Path 1 **FAIL** 4 tenors (3M / 6M / 2Y / 10Y). Primeira
  **não-inversão** do ledger v2 — ou seja, primeira vez que a Path 1
  canonical não serve. Requer Path 2 (DNB native cascade) Week 11 per
  a ordem de cascade v2 já estabelecida.

### Resultado empírico Sprint M probe (2026-04-23)

Pass criterion: `length >= 500` observations + `latest <= 7 days`
stale + ≥ 6 tenors por país (MIN_OBSERVATIONS_FOR_SVENSSON floor).

**PT (GSPT family) — 10/12 tenors PASS:**

| Tenor | Symbol | n obs | Latest |
|---|---|---|---|
| 3M | `GSPT3M:IND` | 588 | 2026-04-22 |
| 6M | `GSPT6M:IND` | 589 | 2026-04-22 |
| 1Y | `GSPT1Y:IND` | 586 | 2026-04-22 |
| 2Y | `GSPT2YR:IND` | 596 | 2026-04-22 |
| 3Y | `GSPT3Y:IND` | 603 | 2026-04-22 |
| 5Y | `GSPT5Y:IND` | 601 | 2026-04-22 |
| 7Y | `GSPT7Y:IND` | 588 | 2026-04-22 |
| 10Y | `GSPT10YR:IND` | 601 | 2026-04-22 |
| 20Y | `GSPT20Y:IND` | 594 | 2026-04-22 |
| 30Y | `GSPT30Y:IND` | 591 | 2026-04-22 |
| 1M | — (probe-empty all variants) | 0 | — |
| 15Y | — (probe-empty all variants) | 0 | — |

PT naming quirk: mixed-suffix. `M` em 3M/6M; `YR` em 2Y + 10Y apenas;
bare `Y` em 1Y / 3Y / 5Y / 7Y / 20Y / 30Y. TE `/search/portugal%20government%20bond`
confirmou as 10 acima como lista completa do catálogo — 1M + 15Y
são gaps estruturais de cobertura TE, não probe-naming miss. Live
canary (2026-04-21/22/23) retornou `rmse_bps ∈ [7.24, 7.53]`,
confidence=1.0 em todos os 3 dias.

**NL (GNTH family) — 4/12 tenors PASS:**

| Tenor | Symbol | n obs | Latest |
|---|---|---|---|
| 3M | `GNTH3M:IND` | 597 | 2026-04-22 |
| 6M | `GNTH6M:IND` | 595 | 2026-04-22 |
| 2Y | `GNTH2YR:GOV` (note `:GOV` suffix — único NL quirk) | 598 | 2026-04-22 |
| 10Y | `GNTH10YR:IND` | 600 | 2026-04-22 |
| 1M / 1Y / 3Y / 5Y / 7Y / 15Y / 20Y / 30Y | — (probe-empty em todas as variantes `:IND` e `:GOV`) | 0 | — |

NL `/search/netherlands%20government%20bond` confirmou as 4 acima
como lista completa — outros 8 tenors são TE-coverage gaps
estruturais, não probe-naming miss. O `:GOV` suffix quirk no 2Y é
único em todo o registry (nenhum outro T1 tem `:GOV` — toda a gente
usa `:IND`). O `Symbol` campo na response payload continua `GNTH2YR:GOV`,
pelo que downstream guards são consistentes, mas o quirk merece
nota para qualquer re-probe futuro.

**Total NL = 4 tenors < MIN_OBSERVATIONS_FOR_SVENSSON=6 → HALT-0.**

### Primeira não-inversão ADR-0009 v2 — implicações

Ledger de inversões ADR-0009 v1→v2 ao fecho Sprint M:

| # | Sprint | País | TE tenors | Outcome | Path 2 needed? |
|---|---|---|---|---|---|
| 1 | H | IT | 12 | PASS | No |
| 2 | H | ES | 9 | PASS | No |
| 3 | I | FR | 10 | PASS | No |
| 4 | M | PT | 10 | PASS | No |
| **5** | **M** | **NL** | **4** | **HALT-0** | **YES — Path 2 DNB** |

NL é a primeira **não-inversão** — empiricamente prova que TE Path 1
não é universal para EA periphery, validando a v2 framing "probe TE
first, escalate to Path 2/3 only on empirical Path 1 failure". Sem
esta observação, a v2 regra ficaria indistinguível de "TE sempre
resolve" (tautologicamente verdadeira nos primeiros 4 sprints).

### Regra operacional v2 mantém-se — Sprint M é primeira validação negativa

A regra "probe TE Path 1 first" não muda. O que Sprint M adiciona:

1. **Empirical scope TE**: TE cobre **maioria** dos EA periphery
   (IT/ES/FR/PT = 100 % dos probed) mas **não todos** (NL = 0 %
   Svensson-capable). Per-country probe continua obrigatório.
2. **"4 tenors + 1 major missing"** (NL's shape: 3M/6M + single
   2Y + 10Y, nada entre 2Y e 10Y e nada fora de 10Y) é um sinal
   distinto de "≥6 tenors + small gaps" (IT/ES/FR/PT shape). Pattern
   library v2.2: quando probe retorna <50 % Svensson-minimum, o
   Path 2 fallback é **alta prioridade** para Week 11, não
   deferral.
3. **Symbol-namespace quirks**: NL expõe `:GOV` no 2Y (único entre
   T1). Qualquer sweep futuro deve incluir `:GOV` variant na
   grelha de probe.

### Pattern library v2.2 — Sprint M shape distinction

Sprint M formaliza dois sub-shapes de TE periphery coverage:

- **Shape S1 — Svensson-rich** (IT/ES/FR/PT): ≥ 9 tenors spread
  across 3M-30Y, full-spectrum curve-fit viable. TE Path 1 ships
  as-is.
- **Shape S2 — Point-estimates-only** (NL): 3-4 tenors covering
  isolated maturities (tipicamente 3M/6M + 2Y + 10Y), insuficiente
  para Svensson. TE Path 1 HALT-0 → Path 2 required. Shape S2 é
  provável cohort para outros EA members não-probed (BE/AT/IE/FI —
  T2+; AU/NZ T1 já sob CAL-CURVES-T1-SPARSE).

### Per-country probe outcomes table (Sprint H + Sprint I + Sprint M)

| Country | TE tenors | Svensson? | Outcome | CAL closed | Shape |
|---|---|---|---|---|---|
| IT | 12 | Y | Sprint H PASS | IT-BDI | S1 |
| ES | 9 | Y | Sprint H PASS | ES-BDE | S1 |
| FR | 10 | Y | Sprint I PASS | FR-TE-PROBE (FR-BDF stays BLOCKED) | S1 |
| PT | 10 | Y | Sprint M PASS | PT-BPSTAT (pre-open) | S1 |
| NL | 4 | N | Sprint M HALT-0 | — (NL-DNB-PROBE **opens** Week 11) | S2 |

### Follow-ups (Sprint M addendum)

1. **CAL-CURVES-NL-DNB-PROBE** open para Week 11 — probe De
   Nederlandsche Bank nativo (statline.dnb.nl SDMX) para o 8-tenor
   gap. Expected outcome hypothesis: DNB publica yield curves
   sovereign diárias como EA periphery conventional; se HTTP 200 +
   daily + ≥6 tenors → ship via DNB cascade (sub-case "native works",
   pattern precedent: Bundesbank DE). Se HTTP 200 + monthly only →
   sub-case C (replication ES-BDE pre-Sprint-H).
2. **Pattern library v2.2 update** em `docs/adr/ADR-0009-...` — Shape
   S1 vs S2 distinction codificada aqui mesmo; replication nos
   próximos briefs periphery.
3. **NL overlays cascade** continua EA-AAA proxy-fallback até
   CAL-CURVES-NL-DNB-PROBE close Week 11.

### Post-Sprint M coverage state

**T1 curves coverage 10/16** (US/DE/EA/GB/JP/CA + IT + ES + FR **+ PT**).
Quatro CAL items CLOSED via TE cascade (IT-BDI + ES-BDE Sprint H +
FR-TE-PROBE Sprint I + PT-BPSTAT pre-open Sprint M). Um BLOCKED
conserved (FR-BDF — direct-CB upgrade path; daily pipeline já não
depende). Um pendente (**NL-DNB-PROBE** — Week 11, via sub-sprint
dedicado ADR-0009 v2 Path 2). Overlays cascade de PT em produção a
partir de 2026-04-24 07:30 WEST (primeira execução post-merge);
NL continua em EA-AAA proxy-fallback até CAL-CURVES-NL-DNB-PROBE
close.

Pattern library v2.2 codifica Shape S1 (Svensson-rich, TE Path 1
PASS) vs Shape S2 (point-estimates only, TE Path 1 HALT-0). Sprint M
é primeira observação S2 + primeira **não-inversão** do ledger v2.

## Referências

- `docs/planning/week10-sprint-d-fr-bdf-brief.md` §9 fallback
  hierarchy, §5 HALT-0 trigger, §7 report-back.
- `docs/planning/week10-sprint-g-it-es-curves-brief.md` §2 pre-flight,
  §5 HALT-0 triggers, §7 report-back — Sprint G combined IT + ES pilot.
- `docs/planning/week10-sprint-h-it-es-te-cascade-brief.md` §4 commits
  1-5 — Sprint H IT + ES TE cascade (Sprint G amendment).
- `docs/planning/week10-sprint-i-fr-te-probe-brief.md` §4 commits
  1-4 — Sprint I FR TE cascade (Sprint H amendment v2 successor).
- `docs/planning/retrospectives/week10-sprint-curves-fr-bdf-report.md`
  — pilot retro (v3 format).
- `docs/planning/retrospectives/week10-sprint-curves-fr-te-probe-report.md`
  — Sprint I FR TE-cascade retro (v3 format; closes
  `CAL-CURVES-FR-TE-PROBE` via Path 1 canonical; sharpens
  `CAL-CURVES-FR-BDF` per direct-CB / TE-cascade orthogonality).
- `docs/planning/retrospectives/week10-sprint-curves-it-es-report.md`
  — Sprint G combined retro (v3 format).
- `docs/planning/retrospectives/week10-sprint-curves-it-es-te-report.md`
  — Sprint H TE-cascade retro (v3 format; closes IT-BDI + ES-BDE via
  Path 1 canonical).
- `docs/planning/week10-sprint-m-curves-pt-nl-brief.md` §2 pre-flight
  probe matrix, §4 HALT triggers, §5 acceptance — Sprint M PT/NL
  successor sprint brief (v3.1 format).
- `docs/planning/retrospectives/week10-sprint-m-report.md` — Sprint M
  partial-PASS retro (v3 format; closes PT-BPSTAT pre-open via Path 1
  canonical; opens NL-DNB-PROBE Week 11 as first Path 1 non-inversion).
- `docs/backlog/probe-results/sprint-m-pt-nl-te-probe.md` — raw
  per-tenor probe matrix + /search cross-validation for PT + NL
  (2026-04-23).
- `docs/planning/retrospectives/week10-sprint-ea-periphery-report.md`
  — Sprint A precedent (ECB SDW periphery HALT).
- `docs/planning/retrospectives/week10-sprint-cal138-report.md` —
  CAL-138 precedent (TE periphery HALT).
- `src/sonar/connectors/banque_de_france.py` — documentation-first
  scaffold (sub-caso A: 4xx / deprecated).
- `src/sonar/connectors/banca_ditalia.py` — sub-caso B scaffold
  (all paths dead).
- `src/sonar/connectors/banco_espana.py` — sub-caso C scaffold
  (HTTP 200 + non-daily).
- `src/sonar/connectors/bundesbank.py` — functional national-CB
  reference (DE, pattern that did not generalize to periphery).
- `src/sonar/connectors/ecb_sdw.py` `PERIPHERY_CAL_POINTERS` —
  per-country CAL routing (shared across all five periphery members).
- `docs/backlog/calibration-tasks.md` — `CAL-CURVES-FR-BDF` +
  `CAL-CURVES-IT-BDI` + `CAL-CURVES-ES-BDE` (BLOCKED) + two
  successors annotated with ADR-0009 probe discipline.
- ADR-0005 (country-tiers) + ADR-0007 (ISO country codes) — enforce
  consistent country-code handling across the stack.
- ADR-0008 (per-country ERP data constraints) — adjacent precedent
  of narrow-scope + CAL decomposition under data-availability
  constraints.
- ADR-0010 (T1 complete product before T2 expansion) — Sprint G
  work explicitly constrained to T1 scope; IT + ES are T1 per
  ADR-0005 + `country_tiers.yaml`.
