# Brief Format v2 (active 2026-04-20 → 2026-04-22)

> **DEPRECATED (2026-04-22).** Superseded by
> [`brief-format-v3.md`](./brief-format-v3.md), which adds mandatory
> pre-merge checklist + merge execution + post-merge verification
> sections after the Week 9 / Day 0 Week 10 merge incident inventory.
>
> This file is kept for historical reference. Briefs already written
> in v2 (Week 4 → Week 9, Week 10 Day 0) complete their lifecycle on
> v2 and ship as-is — **migration to v3 is forward-only; no retrofit**.
> New sprints from Week 10 Day 1 onwards use v3.

## Purpose

Minimal execution briefs for Claude Code autonomous runs. Replace verbose
formats from Week 1 / Week 2 Day 1-3 (e.g. `p2-023`, `nss-scaffolding`,
`nss-fit-algorithm`, `nss-persistence-tips` briefs in `docs/planning/`).

## Structure (6 sections, fixed)

1. **Scope** — bullets, in/out
2. **Spec reference** — links to `docs/specs/*` authoritative; do NOT
   quote spec verbatim
3. **Commit structure** — N commits with short message templates
4. **HALT triggers** — atomic, max 5. "User authorized in principle"
   does NOT cover specific triggers.
5. **Acceptance** — testable checklist
6. **Report-back** — paste-back format

## What NOT to include

- Decision alternatives discussions
- Code examples CC will rewrite differently anyway
- Edge-case matrices already in the spec §6 equivalents
- Pre-brief decision trees (D-X-1, D-X-2, ...)
- Dataclass definitions verbatim
- Migration templates verbatim

## Sprint batching

1 brief covers a multi-day sprint (e.g. "Week 3 connector sprint:
ECB SDW + TE + Bundesbank") with N commits sequential. CC reports
sprint-end, not per commit.

Chat produces next sprint brief **during** CC execution of current
sprint (parallel work).

## Skeleton

````markdown
# [Sprint name] — Execution Brief

**Target**: [Phase X Week Y Days A-B]
**Priority**: [HIGH/MEDIUM]
**Budget**: [Xh CC autonomous]
**Commits**: [N]
**Base**: [commit SHA]

## 1. Scope

In:
- [bullet]
- [bullet]

Out (defer):
- [bullet]

## 2. Spec reference

- docs/specs/[path] @ vX.Y
- docs/specs/conventions/[path]

## 3. Commits

### Commit 1/N — [task name]
Msg template:
```
[type]([scope]): [summary]

[body]
```

### Commit 2/N — [task name]
...

## 4. HALT triggers

1. [atomic condition]
2. [atomic condition]
...

## 5. Acceptance

- [ ] [testable check]
- [ ] [testable check]
...

## 6. Report-back

1. [SHAs + log]
2. [coverage delta]
3. [timer vs budget]
4. [HALT fired?]
5. [out-of-scope surfaced]
````

## References

- SESSION_CONTEXT §Brief format (source of truth policy)
- SESSION_CONTEXT §Decision authority (autonomy scope)
- [`./phase1-coverage-policy.md`](./phase1-coverage-policy.md) (gate thresholds)
