# Testing strategy — SONAR v2

Estratégia de testes e convenções operacionais para o repo. Leitura
rápida para contribuidores + operador solo. Para detalhe arquitetural
ver `ARCHITECTURE.md` §Testing.

## 1. Tiers de teste

| Tier | Pasta | Marcador | Gate | Tempo típico | Uso |
|------|-------|----------|------|--------------|-----|
| Unit | `tests/unit/` | (default) | pre-push `-x -m "not slow"` | < 5s total (1387 tests) | Pure logic; no network; cassettes. |
| Unit slow | `tests/unit/` | `@pytest.mark.slow` | CI full-suite | ~30s | Heavy compute; still no network. |
| Integration | `tests/integration/` | `-m integration` opcional | Per-sprint canary | ~5-10s per country | Pipeline end-to-end (CLI → builder → compute → persist → readback). |
| Live canary | `tests/unit/test_connectors/*_live_*` | `@pytest.mark.live` | Manual pre-merge + weekly | 1-5s per connector | Real network call (skipped without API keys). |

## 2. Pre-push gate (local)

```bash
uv run ruff format --check
uv run ruff check
uv run mypy src/sonar
uv run pytest tests/unit -x -m "not slow"
```

Pass all before `git push`. No `--no-verify`. Hooks (pre-commit-config.yaml)
enforce ruff + mypy automatically on `git commit`; pytest is out of
scope for hook speed reasons — run manually.

## 3. Cassettes + network isolation

Unit tests **must not** hit real endpoints. Use
`tests/fixtures/<connector>/<scenario>.json` / `*.xml` cassettes for
deterministic I/O. Cassette refresh is per-sprint operator work (see
`docs/ops/cassette-refresh.md` if present; otherwise ad-hoc).

Live canaries live under `tests/unit/test_connectors/` with
`@pytest.mark.live` marker. They skip if API keys absent. CI runs them
on a weekly cadence (not per-push).

## 4. Known flaky tests

### `test_daily_overlays.py::test_default_builder_returns_empty_bundle`

- **Symptom**: passes in isolation, fails intermittently in full-suite
  run (observed Sprint V-CH through Sprint Y-DK retrospectives, Week 9
  Day 3-5).
- **Repro**: reproduces against `main` HEAD with any sprint's changes
  reverted (pre-existing, unrelated to country sprints).
- **Root cause**: unknown — test-ordering dependency suspected but not
  narrowed down.
- **Workaround**:
  - Pre-push gate uses `pytest -x` (exits on first failure); if this
    test surfaces, re-run full suite — stable on retry in practice.
  - Do NOT bypass with `--no-verify`.
- **Deferred**: investigative fix deferred to Phase 2.5 quality sprint.
  `pytest-rerunfailures` plugin + `@pytest.mark.flaky` not adopted (adds
  dependency; masks genuine regressions; brief §4 Commit 8 chose
  documentation path).

Report any new flake here with the same structure. If a test flakes
3+ times across different sprints, add to this section rather than
working around silently.

## 5. Coverage floor

- `src/sonar/` modules: 80% line coverage as minimum (not currently
  enforced in CI — informational target).
- Pipeline `run_<country>` functions: covered by per-country
  integration canary.
- Overlay fit functions: unit coverage + integration smoke with
  live-fetched fixtures.

Coverage regression checks surface in PR reviews; not a blocking gate
(discipline-driven).

## 6. Testing decisions archive

Cross-reference for bigger decisions:

- **ADR-0007** — ISO country codes canonical (alpha-2); tests sweep
  string expectations from `UK` → `GB`.
- **Week 7 Sprint G** — Sprint I-patch pattern (TE-primary cascade)
  documented in `docs/planning/sprint-i-patch-te-cascade-brief.md`.
  Tests under `tests/integration/test_daily_monetary_<country>.py`
  follow the 3-to-4-canary per-country shape.
- **Week 9 Sprint O** — UK alias surfaces preserved with deprecation
  warning. Test asserts `--country UK` emits structlog warning.
  Alias removal Week 10 Day 1.

## 7. Adding a new test

1. Placement: `tests/unit/` if no network; `tests/integration/` if
   pipeline end-to-end; `tests/unit/test_connectors/*_live_*` if live
   network required.
2. Fixture: prefer cassette unless live-canary explicitly needed.
3. Run locally: `uv run pytest <path> -x`.
4. Run pre-push gate: command block in §2.
5. Commit message: Conventional Commits `test(scope): ...`.

## 8. Canary cadence

Per-country live canaries (TE / native-CB / FRED fallback) run
manually per sprint. `daily_*` systemd timers run canonical pipeline
paths nightly UTC (see `docs/ops/systemd-deployment.md`). Detection
of silent outages (e.g., the BIS lookback-vs-publication-lag
incident Week 9 Sprint AA) surfaces via systemd journal inspection,
not pytest — tests stayed green through both production fires.

Weekly canary (`CAL-137` OPEN) wires the systemd scheduler to run a
BIS / curves smoke test weekly; pending CAL-138 multi-country
curves.
