# Exceptions · Hierarquia Canónica

Todas as exceptions lançadas por código em `sonar/` herdam de `SonarError`. Specs referenciam nomes exactos; nunca redefinem. Aliases são proibidos — UMA exception por condição.

## Árvore

```
SonarError                              (abstract root)
├── DataError                           (abstract)
│   ├── InsufficientDataError           # obs < minimum threshold
│   ├── StaleDataError                  # data older than TTL
│   ├── DataUnavailableError            # source returned empty / 404
│   └── InvalidInputError               # type / range invariant violated
├── AlgorithmError                      (abstract)
│   ├── ConvergenceError                # optimizer / iterative method failed
│   └── OutOfBoundsError                # parameter outside declared bounds
├── MethodologyError                    (abstract)
│   ├── VersionMismatchError            # stored methodology_version ≠ runtime
│   └── CalibrationError                # calibration input missing / invalid
└── ConfigurationError                  (abstract)
    ├── MissingSecretError              # required env var / secret not set (e.g. API key)
    └── UnknownConnectorError           # connector slug not in registry
```

**10 leaves + 4 branches + 1 root = 15 classes.**

## Tabela operacional

| Exception | Raise when | Caller action típica | Flag emitida |
|---|---|---|---|
| `InsufficientDataError` | `len(observations) < minimum` | abort this `(country, date)`; no persist | — |
| `StaleDataError` | `max_age < now - fetched_at` | emit com `STALE` flag OU re-fetch | `STALE` |
| `DataUnavailableError` | connector returns empty/404 | fall back to secondary connector | `OVERLAY_MISS` |
| `InvalidInputError` | type, range, enum violado | fail loud — bug upstream | — |
| `ConvergenceError` | optimizer did not converge within `max_iter` | fall back to reduced-parameter fit + `NSS_FAIL` | `NSS_FAIL` |
| `OutOfBoundsError` | param fitted outside bounds | re-fit with wider bounds OR accept + flag | `HIGH_RMSE` / spec-specific |
| `VersionMismatchError` | `row.methodology_version != CURRENT` | recompute row, do not serve stale | — |
| `CalibrationError` | calibration table missing key | fall back to default OR refuse | `CALIBRATION_STALE` |
| `MissingSecretError` | required env var / secret missing — raised by connector base class on `__init__` | fail at startup; `ConfigurationError` exits the process | — |
| `UnknownConnectorError` | pipeline requested connector slug not present in registry | fail at startup; fix config | — |

## Exemplo de uso

```python
from sonar.exceptions import InsufficientDataError, ConvergenceError

def fit_nss(tenors, yields):
    if len(yields) < 6:
        raise InsufficientDataError(
            f"NSS requires ≥6 observations, got {len(yields)}"
        )
    try:
        result = scipy.optimize.minimize(...)
    except RuntimeError as e:
        raise ConvergenceError(
            f"L-BFGS-B did not converge after {MAX_ITER} iters"
        ) from e
    return result.x
```

## Regras

- **Raise specific**, nunca `raise Exception(...)` nem bare `except:`.
- **Chain context** com `raise X from e` para preservar traceback.
- **Log at boundary** (connector → module; module → pipeline), não em cada helper.
- **Don't catch** uma exception para a transformar noutra do mesmo ramo sem adicionar contexto.
- **Specs §6 Edge cases** listam exception + handling — nunca inventam nome novo.

## Adicionar uma exception

1. PR que toca este ficheiro primeiro: adiciona classe à árvore + linha na tabela operacional.
2. PR subsequente: implementação em `sonar/exceptions.py` + primeiro uso.
3. Specs que a usam: referenciam nome canónico em §6.
