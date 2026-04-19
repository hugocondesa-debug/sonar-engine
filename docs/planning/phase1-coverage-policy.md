# Phase 1 Coverage Policy

## Scopes

| Scope | Target | Gate |
|---|---|---|
| Per-module (new code at commit) | ≥ 90% | Hard — commit blocked |
| `src/sonar/connectors` | ≥ 95% | Hard — regression blocks |
| `src/sonar` global | ≥ 70% Phase 1, climbing | Soft — warn only |

## Rationale

- **Per-module** is the only threshold actionable at commit time: new
  code lands tested.
- **Connectors hard gate** protects mature code (fred.py @ 100%,
  base.py + cache.py) from regression.
- **Global soft gate** is informational while breadth-first coverage
  grows with package expansion. Hard-gating global during greenfield
  expansion disincentivizes ambitious scaffolding commits.

## Measurement

```bash
# Per-module (manual on new code):
uv run pytest --cov=src/sonar/<package> --cov-report=term-missing tests/

# Connectors regression gate:
uv run pytest --cov=src/sonar/connectors --cov-report=term-missing tests/

# Global baseline tracking:
uv run pytest --cov=src/sonar --cov-report=term-missing tests/
```

## Phase 1 baselines

| Date | Scope | Coverage |
|---|---|---|
| Week 1 close (2026-04-19) | connectors | 96.59% |
| Week 1 close (2026-04-19) | src/sonar global | ~59.3% |
| Week 2 Day 1 PM (2026-04-19) | src/sonar global | 73.66% |
| Week 2 Day 1 PM (2026-04-19) | overlays (new) | 100% |

Updated at each Phase 1 weekly retrospective.
