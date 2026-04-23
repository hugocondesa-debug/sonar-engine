# Sprint O — M3 backfill + verify transcript

**Data**: 2026-04-23 Day 3 late
**Scope**: Brief §2.6 backfill + §5 acceptance (primary + tertiary).
**Backend**: `--backend default` (empty bundle — isolates M3 classifier path from M1/M2/M4 connector fetches; zero FRED/TE calls, zero cache invalidation).

**Systemd verify** (acceptance §2) is a post-merge operator step — the systemd unit points at `/home/macro/projects/sonar-engine` not the worktree, so the compiled binary reflecting this sprint's code only becomes available to the service after the sprint lands on `main` + the operator opts into a one-off service start. Captured here for the retro: pre-merge CLI-driven verification covering the same grep contract (`monetary_pipeline.m3_compute_mode | wc -l`, `event loop is closed / connector_aclose_error / country_failed | wc -l`).

---

## §1 Backfill run — 2026-04-21 / -22 / -23

```bash
for d in 2026-04-21 2026-04-22 2026-04-23; do
  uv run python -m sonar.pipelines.daily_monetary_indices \
    --m3-t1-cohort --date "$d" --backend default
done
```

All three runs exit `0`. Summary line per run emits `n_no_inputs=9` (expected — default backend builds no M1/M2/M4 bundle; M3 DB-backed path emits classifier log for each country).

## §2 `m3_compute_mode` entry count per date

| Date | Entries | Modes | Notes |
|---|---:|---|---|
| 2026-04-21 | 9 | 9× DEGRADED | Reason flags split: `M3_EXPINF_MISSING` (2 = US/DE) + `M3_FORWARDS_MISSING` (7 = EA/GB/JP/CA/IT/ES/FR). |
| 2026-04-22 | 9 | 9× DEGRADED | All 9 → `M3_EXPINF_MISSING` (forwards present per Sprint T0 backfill; EXPINF_CANONICAL absent per audit §3). |
| 2026-04-23 | 9 | 9× DEGRADED | All 9 → `M3_EXPINF_MISSING` (daily-curves persisted forwards for all 9 T1 cohort members; same EXPINF gap). |
| **Total** | **27** | **27× DEGRADED** | Zero NOT_IMPLEMENTED among the T1 cohort — acceptance §1 contract satisfied. |

Brief acceptance §2 threshold: **≥9 entries per dispatch**. Observed: exactly 9 per run × 3 runs = 27. Meets contract.

Per-country sparsity-reason flags surface correctly in the DEGRADED path:

- `JP_M3_BEI_LINKER_THIN_EXPECTED`
- `CA_M3_BEI_RRB_LIMITED_EXPECTED`
- `IT_M3_BEI_BTP_EI_SPARSE_EXPECTED`
- `ES_M3_BEI_BONOS_EI_LIMITED_EXPECTED`

FR / US / DE / EA / GB emit tier flag only (no structural linker-sparsity reason — FR OATi depth + EA SPF covers the full composite once upstream EXPINF wires).

## §3 Error-signal grep (acceptance §2 sub-check)

```bash
uv run python -m sonar.pipelines.daily_monetary_indices \
  --m3-t1-cohort --date 2026-04-23 --backend default 2>&1 | \
  grep -iE "event loop is closed|connector_aclose_error|country_failed" | wc -l
```

Result: `0`. ADR-0011 P6 AsyncExitStack discipline (Sprint T0.1 merge) holds under the Sprint O classifier extension — the added `classify_m3_compute_mode` path is a sync DB query inside `run_one`, no new event-loop boundary.

## §4 Exit-code matrix

| Date | Exit | Notes |
|---|---:|---|
| 2026-04-21 | 0 | Happy path — all 9 countries `no_inputs` (M1/M2/M4 empty under --backend=default) + 9× m3_compute_mode emitted. Summary `n_failed=0`. |
| 2026-04-22 | 0 | Same. |
| 2026-04-23 | 0 | Same. |

ADR-0011 Principle 3 happy-path contract: exit 0 whenever pipeline runs to completion without uncaught structural exception. All three satisfy.

## §5 Post-merge systemd verify — operator checklist

```bash
# After sprint_merge.sh:
sudo systemctl start sonar-daily-monetary-indices.service
sleep 180
systemctl is-active sonar-daily-monetary-indices.service
# expected: inactive (oneshot Type, exit 0)

sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
  grep -iE "event loop is closed|connector_aclose_error|country_failed" | wc -l
# expected: 0

sudo journalctl -u sonar-daily-monetary-indices.service --since "-3 min" --no-pager | \
  grep "monetary_pipeline.m3_compute_mode" | wc -l
# expected: 7 with --all-t1 (legacy T1_7 dispatch: US/DE/PT/IT/ES/FR/NL);
#           9 with --m3-t1-cohort (Sprint O dispatch: US/DE/EA/GB/JP/CA/IT/ES/FR).
```

Note: the deployed systemd unit currently runs `--all-t1` (yielding 7 entries, 5 FULL-or-DEGRADED + 2 NOT_IMPLEMENTED for PT/NL). To hit the brief's ≥9 threshold post-merge, flip the unit to `--m3-t1-cohort` (or add a companion timer). The flag is backwards-compatible — M1/M2/M4 builders for non-T1_7 countries (EA/GB/JP/CA) either return live outputs (GB/JP/CA M1) or NotImplementedError (EA M2/M4, GB/JP/CA M2/M4) which the pipeline gracefully routes to `monetary_pipeline.builder_skipped`. Operator flip is post-sprint discretion per CLAUDE.md §10 "NÃO enabled em produção sem autorização explícita".

*End of verify transcript. Primary + tertiary acceptance satisfied via CLI pre-merge; secondary (sudo systemd) deferred post-merge per ops protocol.*
