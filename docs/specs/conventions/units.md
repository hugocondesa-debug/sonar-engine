# Units · Convenções

Aplica-se a **toda** a stack: storage, compute, API interna, test fixtures. Display layer (editorial, dashboard) é a única boundary onde se converte para formatos humanos.

## Yields, returns, risk premia, inflation

**Storage + compute**: decimal puro.

| Valor | Decimal (storage/compute) | Display (editorial/UI) |
|---|---|---|
| US 10Y Treasury | `0.0415` | `4.15%` |
| EA ERP | `0.0525` | `5.25%` |
| PT CRP | `0.0054` | `54 bps` |
| 5y5y forward inflation | `0.0249` | `2.49%` |

Regra: se o valor tem natureza "fracção/percentagem", é `float` decimal em tudo o que é código. Conversão para `%` só no display boundary (`outputs/exporters/`, dashboards, editorial templates).

## Spreads & basis points

- **Sempre inteiros**: `spread_bps: int`.
- **Sufixo obrigatório no nome**: `_bps`.
- **Never mix** com decimal: `spread_bps = 54` (≠ `0.0054`).
- Conversão explícita: `bps = int(round(decimal * 10_000))` no display layer.

## Datas & tempo

- **Storage**: UTC sempre (`TIMESTAMP WITH TIME ZONE` ou equivalente).
- **Scheduling**: `Europe/Lisbon` (horário SONAR daily).
- **Format wire/JSON**: ISO 8601 (`2026-04-18`, `2026-04-18T09:00:00Z`).
- **Python types**: `date` para daily data time-agnostic; `datetime` com tzinfo para events.
- **Business day**: per-country calendar; `config/calendars.yaml` (a criar em Phase 1).

## Confidence

- `float ∈ [0.0, 1.0]` — sempre presente em outputs persistidos.
- `1.0` = nominal; degradação por flag em `conventions/flags.md`.
- Apply aditivo, clamp a `[0, 1]`, floor em `0.0`.
- **Nunca** usar confidence como proxy de probability (é qualidade de dados, não de modelo).

## Methodology version

- `str`, sempre presente em output persistido.
- Formato em `conventions/methodology-versions.md`.
- Permite rebackfill selectivo quando spec muda.

## Countries & currencies

- **Country**: ISO 3166-1 α-2 **upper** (`PT`, `DE`, `US`). `EA` = euro area aggregate. `WW` = world (reservado).
- **Currency**: ISO 4217 (`EUR`, `USD`, `GBP`, `JPY`, `BRL`).
- **Nunca** usar nomes por extenso em código/storage.

## Tenors

Grid canónico (string): `["1M","3M","6M","1Y","2Y","3Y","5Y","7Y","10Y","15Y","20Y","30Y"]`.

- Sempre `str` em JSON/API; conversão para `float years` (`1M = 1/12`) apenas inside compute.
- Forward tenors: `"1y1y"`, `"5y5y"`, `"10y10y"` (lowercase, sem separador).

## Proibições

- ❌ Armazenar `yield = 4.15` (ambíguo: 4.15% ou 4.15 decimal?).
- ❌ Misturar `spread_pct` e `spread_bps` na mesma tabela.
- ❌ Datas como string livre (`"17 Abr 2026"`).
- ❌ Country codes em minúsculas ou nomes (`"pt"`, `"Portugal"`).
- ❌ Timezone naive datetimes em storage.

## Display conversion contract

Single helper em `sonar/outputs/exporters/` (a implementar):

```python
def fmt_pct(x: float, decimals: int = 2) -> str:    # 0.0415 → "4.15%"
def fmt_bps(x: int) -> str:                         # 54 → "54 bps"
def fmt_date(d: date) -> str:                       # ISO 8601
```

Templates editoriais usam exclusivamente estes helpers. Specs não precisam preocupar-se com display.
