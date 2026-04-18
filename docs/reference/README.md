# SONAR · Methodology

Raiz da documentação metodológica. Fonte única de verdade (*source of truth*) para toda a computação que o motor executa. O código em `sonar/` **implementa** estas metodologias; sem estes documentos, o código perde o "porquê".

Origem: manuais v1 (`Manual_Ciclo_*_COMPLETO.docx` + `Manual_Submodelos_COMPLETO.docx`) convertidos com pandoc e splitados pela estrutura atual v2 (9 camadas, overlays renomeados).

## Estrutura

```
docs/methodology/
├── README.md          # este ficheiro
├── cycles/            # L4 — 4 classificadores de regime
│   ├── economic.md
│   ├── credit-cccs.md
│   ├── monetary.md
│   └── financial.md
├── overlays/          # L2 — 5 calculadoras quantitativas universais
│   ├── README.md      # Fundações (Parte I) + Integração (Parte VI) do Manual
│   ├── nss-curves.md
│   ├── erp-daily.md
│   ├── crp.md
│   ├── rating-spread.md
│   └── expected-inflation.md
└── indices/           # L3 — sub-índices de cada ciclo (Parte III dos manuais)
    ├── README.md
    ├── economic/      # E1..E4
    ├── credit/        # L1..L4
    ├── monetary/      # M1..M4
    └── financial/     # F1..F4
```

## Mapeamento manual → ficheiros

Cada Manual de Ciclo tem 20 capítulos em 6 Partes. Foi splitado assim:

| Parte original | Conteúdo | Destino v2 |
|---|---|---|
| Parte I — Fundações teóricas (caps 1-3) | Porque existe o ciclo, genealogia, pós-2008/Covid | `cycles/<name>.md` |
| Parte II — Arquitetura / Anatomia (caps 4-6) | Fases operacionais, datação, heterogeneidade | `cycles/<name>.md` |
| **Parte III — Medição (caps 7-10)** | **4 sub-índices (E1-4 / L1-4 / M1-4 / F1-4)** | **`indices/<name>/` — 1 ficheiro por sub-índice** |
| Parte IV — Transmissão (caps 11-14) | Canais, amplificadores, spillovers | `cycles/<name>.md` |
| Parte V — Integração (caps 15-17) | Composite score, overlays (Stagflation/Boom/...), matriz 4-way | `cycles/<name>.md` |
| Parte VI — Aplicação (caps 18-20) | Playbook, portfólio, caveats, bibliografia | `cycles/<name>.md` |

Manual_Submodelos_COMPLETO (20 caps, 6 Partes) → 5 overlays:

| Parte original | Destino v2 |
|---|---|
| Parte I · Fundações (caps 1-3) | `overlays/README.md` |
| Parte II · Yield curves (caps 4-6) | `overlays/nss-curves.md` |
| Parte III · ERP (caps 7-9) | `overlays/erp-daily.md` |
| Parte IV · CRP (caps 10-12) | `overlays/crp.md` |
| Parte V caps 13-15 · Rating mapping | `overlays/rating-spread.md` |
| Parte V caps 16-17 · Expected inflation | `overlays/expected-inflation.md` |
| Parte VI · Integração (caps 18-20) | `overlays/README.md` |

## Regras de uso

- **Alterações à metodologia** → atualizar o ficheiro metodológico **antes** do código, incrementar `methodology_version` na DB.
- **Nova overlay / índice / ciclo** → criar ficheiro .md aqui **antes** de `sonar/...` correspondente.
- **Nota histórica**: os manuais originais falam em "sub-modelos" / "cycle overlays". Terminologia v2:
  - `submodelo` ou `sub-model` → **overlay** (L2)
  - `cycle overlay` (Stagflation, Boom, Dilemma, Bubble Warning) → **regime** (L5)

Ver `docs/architecture/adr/` para as decisões que renomearam esta terminologia.
