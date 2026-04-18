# AI collaboration — operacional

Operacionaliza ADR-0004 (AI collaboration model). ADR-0004 decide **quem faz o quê**; este documento documenta **como** — prompt patterns, QC workflow, failure modes, exemplos concretos de Phase 0.

## Três papéis (recap)

Canonical source: ADR-0004. Recap curto:

1. **Claude chat** (claude.ai) — decisões, desenho de prompts, QC review, contexto alargado (`SESSION_CONTEXT.md`).
2. **Claude Code** (CLI no VPS) — execução: edit files, `grep`/`find`/`git` ops sem commit, `str_replace`, verificação.
3. **Hugo** — commit gate, taste editorial, scope decisions, autoriza push.

## Workflow canónico

Para cada bloco de trabalho:

```
1. Claude chat desenha prompt denso com:
   - Context (what to read first)
   - Task structure (estrutura obrigatória)
   - Constraints (PT-PT, no emojis, target N-M linhas)
   - Output format (onde escrever, no commit)
   - QC criteria (o que reportar)

2. Hugo cola prompt no Claude Code terminal

3. Claude Code executa e reporta:
   - Files touched + paths absolutos
   - Line counts
   - git status
   - Snippets verificáveis quando apropriado

4. Hugo decide: scp + upload para Claude chat, OU confia em reporting

5. Claude chat QC contra checklist específica do bloco

6. Se edits: round-trip 3-5. Se clean: autoriza commit

7. Hugo executa commit com mensagem pré-preparada por Claude chat

8. Claude Code confirma commit + git log
```

## Prompt patterns

### Ficheiro novo (criação)

```text
Task: criar <path>.

Ler primeiro:
- <fontes de verdade relevantes>

Estrutura obrigatória:
1. <sections>
2. ...

Constraints:
- PT-PT prose, EN identifiers
- Target N-M linhas
- Zero emojis
- Links relativos

Output:
- Escrever <path>. NÃO commit. Unstaged.
- Reportar linhas, git status.
- Cola ficheiro aqui para QC.
```

### Edit cirúrgico

```text
str_replace em <path>:
  old_str: "<texto exacto>"
  new_str: "<substituição>"
```

**Sempre verificar texto exacto** antes (via `grep -n` ou `sed -n`) quando conteúdo tem caracteres especiais, acentos ou ambiguidade de whitespace. `cat -A` revela whitespace invisível.

### Rewrite de ficheiro existente

Mesmo padrão de "ficheiro novo" com nota adicional:

- Ler ficheiro actual primeiro (Read tool requirement).
- Reportar tamanho antes/depois.
- Stale refs removidas (grep cleanup pós-edit).

## QC workflow

### Amostra vs integral

- **Ficheiro novo standalone** (< 150L): leitura integral antes de commit.
- **Rewrite de ficheiro existente**: leitura integral pós-edit.
- **Edit cirúrgico em ficheiro grande**: grep sanity + verificação focada das linhas tocadas.
- **Múltiplos ficheiros em bloco** (ex: 6 ADRs, 6 governance): amostragem selectiva (1-2 integrais, resto headers + sections-chave).

### Checklist base QC

- [ ] Aplicação de edit correcta (o que foi pedido, não mais nem menos).
- [ ] Zero resíduos stale (termos banidos, paths antigos, ficheiros já arquivados).
- [ ] Links relativos funcionais (não URLs absolutos salvo external justificado).
- [ ] Coerência cross-doc (refs a `ARCHITECTURE §N` existem; SHAs reais; fases correctas).
- [ ] Consistência linguagem (PT-PT prose, EN identifiers).
- [ ] Zero emojis.
- [ ] Zero conteúdo inventado (afirmações sobre v1, comandos, versions, colunas → verificar ou remover).

## Failure modes + remediação

### FM-1 — Claude Code reporta sucesso mas scp mostra pré-edits

**Sintoma**: Claude Code diz "edits aplicados"; Hugo faz scp; ficheiro aparece igual ao anterior.

**Causa provável**: cache do `~/Downloads/` do Mac. Hugo fez scp antes dos edits serem aplicados, ou cache do Finder.

**Remediação**: novo scp (opcionalmente com `-O` para forçar legacy SCP protocol). Grep sanity check antes de upload:

```bash
grep -c "<termo esperado novo>" ~/Downloads/<file>
grep -c "<termo esperado removido>" ~/Downloads/<file>
```

### FM-2 — Claude Code inventa facts sobre v1 / sistema externo

**Sintoma**: ficheiro contém afirmações específicas (nomes de colunas, comandos, versions, SHAs) que Claude Code não pode ter verificado sem ler fonte canónica.

**Remediação**: flag no QC. Opções: remover afirmação específica, pedir verificação real (grep em `reference/`, git log, wc -l), ou substituir por frase genérica.

**Precedente Phase 0**: `MIGRATION_PLAN.md §2.2` inicialmente tinha "column naming divergente (`score`, `value`, `composite`, `idx`)" — 4 nomes concretos inventados. Removidos; ficou "column naming divergente entre tabelas" (genérico, defensável).

### FM-3 — ASCII art desalinhado após edit

**Sintoma**: após `str_replace` em diagrama, caracteres box-drawing (`├`, `│`, `└`, `─`) desalinham porque labels mudaram de tamanho.

**Remediação**: cosmético, não bloqueia commit (monospaced renderers continuam legíveis). Registar como micro-débito se significativo acumulou cross-commit.

### FM-4 — Overlap de edits entre blocos paralelos

**Sintoma**: Bloco N+1 reverte ou duplica conteúdo de Bloco N.

**Remediação**: verificar `git status` antes de cada novo bloco. Se pending changes de bloco anterior, fechar primeiro (commit ou discard explícito).

### FM-5 — Target numérico por inflação

**Sintoma**: prompt especifica "target 200-300L", Claude Code produz 506L inflando prose water para atingir densidade aparente.

**Remediação**: targets são orientação, não contrato. Qualidade de densidade (vs bloat) é critério real. Se conteúdo legítimo pede 500L, aceitar; se é water, cortar.

**Precedente Phase 0**: `GLOSSARY.md` criação (Bloco 4b) — target 220-300L, final 506L aceitas como estruturalmente legítimas (índice alfabético 100L é core do valor).

## Exemplos concretos (Phase 0 Blocos 1-5)

### Exemplo 1 — `ARCHITECTURE.md` rewrite (Bloco 1)

**Padrão**: prompt denso com 10 sections obrigatórias → Claude Code produz 385L → Hugo scp + upload → Claude chat QC identifica 2 bloqueadores (SHAs inventados, stale ref) → round-trip edits → re-upload → QC passa → commit.

**Lição**: SHAs específicos e nomes concretos são alto-risco (FM-2). Verificar sempre com `git log` ou `grep` na fonte canónica antes de aceitar.

### Exemplo 2 — `REPOSITORY_STRUCTURE.md` + cleanup v1 (Bloco 4a)

**Padrão**: QC revelou `sonar/submodels/` mencionado no draft → grep revelou dir vazio + ficheiros v1 residuais → cluster de commits atómicos pré-rewrite: C1 archive v1 code, C2 fix pre-commit path stale, C2c fix ref stale em spec frozen, C2b abortado (nada a commitar porque rmdir de dirs vazios não produz delta git), C3 rewrite final.

**Lição**: limpar o repo antes de escrever o mapa. Mapa escrito sobre estado transitório obriga rewrite. Commits atómicos por natureza de mudança (cleanup vs rewrite vs fix).

### Exemplo 3 — `GLOSSARY.md` criação (Bloco 4b)

**Padrão**: target 220-300L definido, Claude Code produz 506L → Hugo escala decisão para Claude chat → QC revela target mal calibrado para escopo "completo" aprovado → 506L aceitas.

**Lição**: ver FM-5. Target numérico é orientação.

## Anti-patterns

- **Aceitar reporting do Claude Code sem verificação** quando edits são críticos (frozen contracts, ADRs, ficheiros referenciados extensivamente).
- **Scp prematuro** antes de confirmar que edits foram aplicados em disco (ver FM-1).
- **Prompts vagos** ("melhora este ficheiro"). Denso + estruturado é mais barato que round-trips.
- **Commit sem QC final** em ficheiros > 100L.
- **Atingir target numérico por inflação** (prose water). Preferir denso + abaixo do target a bloated + dentro do target.

## Cadence de review

Trimestral (placeholder — Phase 1+ activa). Hugo + Claude chat revêem este documento contra friction observada. Adicionar novos FMs e exemplos à medida que aprendizagem acumula.

## Referências

- ADR-0004 — canonical source do modelo de colaboração.
- [`../../CLAUDE.md`](../../CLAUDE.md) §5 (git rules), §6 (tools VPS), §7 (don'ts).
- `SESSION_CONTEXT.md` (external, Claude.ai project knowledge) — log operacional Phase 0 Blocos 1-5.
- [`WORKFLOW.md`](WORKFLOW.md) — git + commits + PRs.
- [`DECISIONS.md`](DECISIONS.md) — lifecycle decisional.
