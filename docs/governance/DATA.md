# Data governance

Secrets, rate limits, backup, licensing, PII, data retention. Policies aplicam-se Phase 1+ (Phase 0 tem zero dados persistidos).

## Secrets

### Estratégia

- **Local dev**: `.env` file (gitignored) + `python-dotenv` + `pydantic-settings` para typed config.
- **CI**: GitHub Actions secrets (encrypted).
- **Produção Phase 2+**: cloud provider secrets manager OR encrypted file com key management (decisão futura — ADR-00NN).

### `.env` rules

- **Nunca committar**. `.gitignore` protege; pre-commit `detect-secrets` + `gitleaks` são safety net.
- `.env.example` é template público — keys presentes, values placeholders.
- Nunca `cat .env` em output visível (logs, outputs CLI, PRs, chat).
- Rotação: API keys sem uso recente (> 90 dias) rotacionadas opportunisticamente.

### Incidente histórico

Ver [`../security/incidents/2026-04-17-pat-leak.md`](../security/incidents/2026-04-17-pat-leak.md) — PAT GitHub vazado em chat durante bootstrap. Revoked + rotated; HIGH severity resolved. **Lição**: PATs não trazem benefício operacional em Claude chat (`web_fetch` só aceita URLs explicitamente partilhados pelo user).

## Rate limits — APIs externas

Phase 1 ingere de múltiplas APIs com rate limits distintos. Rules:

- Cache local SQLite (`data/cache/`) primeiro, API fallback.
- Retries exponential backoff: 1s, 2s, 4s, 8s, 16s, depois abort + flag.
- Rate limit headers (ex: FRED `X-RateLimit-Remaining`) → log `WARN` quando remaining < 20%.
- Batch requests onde API suporta (ex: FRED supports multi-series).
- Connector emite flag `RATE_LIMIT_HIT` quando excedido; pipeline retry dia seguinte.

Limits conhecidos (inventário completo em [`../data_sources/`](../data_sources/) após Bloco D Phase 0):

| API | Limit | Window | Auth |
|---|---|---|---|
| FRED | 120 req/min | rolling | API key |
| ECB SDW | (generoso, não documentado) | rolling | none |
| BIS | (não documentado) | rolling | none |
| IGCP | scrape, ~1 req/sec ethical | — | none |
| World Bank | 100 req/10s | rolling | none |
| Yahoo Finance | scraping (unreliable) | — | none |

Tabela completa extensa em `docs/data_sources/` após Bloco D.

## Data retention

- **Raw connector outputs**: cache local 30 dias; após isso, re-fetch ou invalidate.
- **Computed overlays/indices/cycles**: persistência permanente em SQLite via Alembic migrations — history completa é valor analítico.
- **Methodology versions obsoletas** (pós bump MAJOR): retained até Phase 2 completa; após isso, decisão ADR sobre archive vs delete.
- **Logs**: 90 dias rotação automática; error logs (CRITICAL/ERROR) permanentes.
- **Backups**: ver §Backup abaixo.

## Backup strategy

### SQLite (Phase 0-1 MVP)

- **Diário**: `sqlite3 sonar.db .backup data/backups/daily-YYYY-MM-DD.db` via cron ou pipeline post-`daily-cycles`.
- **Retention local**: 7 dias daily, 4 weeks weekly (sexta-feira), 12 months monthly (primeira sexta do mês).
- **Offsite mirror**: S3 / Backblaze B2 weekly — bucket dedicado, versioning enabled, 90 dias retention.
- Restore test trimestral: fetch latest backup, restore, verificar integridade.

### Postgres (Phase 2+, conditional)

Decisão ADR quando migração disparar (ADR-0003 gates). `pg_dump` daily + WAL archiving para point-in-time recovery. Policies refinadas nesse ADR.

## Licensing — data sources

**Full audit per-source:** [`LICENSING.md`](LICENSING.md) (Bloco D4, 2026-04-18). Source licensing table, attribution strings canónicas, use case matrix (internal/dashboard/client/published/API) e publication checklist vivem lá.

Tiers de alto nível (superseded per-source em LICENSING.md §2):

- **Free + attribution** (FRED, ECB SDW, BIS, OECD, Eurostat, INE): OK para uso SONAR internal e editorial. Attribution per canonical strings em LICENSING.md §3.
- **Commercial ToS** (TE Premium): full liberty para 7365 Capital outputs per ToS interpretation (LICENSING.md §2 row 1).
- **Licensed** (Bloomberg, Refinitiv, LSEG): **NÃO usar sem licença explícita**. Se spec referir, flag para Hugo decidir.
- **Academic free-use** (Shiller Yale, Damodaran NYU): attribution required per LICENSING.md §3.
- **Scraping** (worldgovernmentbonds.com, AAII, CFTC, FINRA, agency press releases): ethical rate + robots.txt compliance per LICENSING.md §7. Output layer só consome composites (raw data audit-internal).

Flag `ATTRIBUTION_REQUIRED` catalogado em [`../specs/conventions/flags.md`](../specs/conventions/flags.md) (era `LICENSE_REVIEW_NEEDED` — resolved D4, deprecated).

## PII & compliance

SONAR trabalha com agregados macro. **Zero PII esperado**. Se algum connector começar a devolver PII (improvável mas possível, ex: Eurostat micro-data, alguns endpoints ECB):

- Abort connector imediatamente.
- Flag `PII_DETECTED`.
- Hugo review + decisão.

**GDPR**: aplica-se a dados em backups S3/B2 se incluírem logs com IP addresses ou identifiers. Mitigação: logs redigem IPs antes de backup (Phase 1 implementation).

## Data discovery — Bloco D Phase 0

Inventário exaustivo de fontes em [`../data_sources/`](../data_sources/). Pré-requisito para Phase 1 arrancar. Cada source catalogada com:

- Endpoint (URL, método, autenticação).
- Séries necessárias para L2 + L3 + L4.
- Rate limit, freshness (latência), histórico disponível.
- Coverage por país.
- Licensing flag.

Ver [`../ROADMAP.md`](../ROADMAP.md) §Phase 0 Bloco D + [`../data_sources/`](../data_sources/).

## Referências

- [`../security/incidents/`](../security/incidents/) — post-mortems históricos.
- [`../data_sources/`](../data_sources/) — inventário fontes (Bloco D).
- [`../../CLAUDE.md`](../../CLAUDE.md) §7 — "não partilhar secrets" não-negociável.
- ADR-0003 — DB path (SQLite backup strategy depende daqui).
- [`WORKFLOW.md`](WORKFLOW.md) — pre-commit hooks (secret scanning).
