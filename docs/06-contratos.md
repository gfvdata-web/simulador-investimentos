# 06 — Contratos entre as partes

Não existe API HTTP neste projeto: o coletor e a página conversam por **arquivos
versionados**. Estes são os formatos que as duas pontas precisam respeitar.

Mudou um formato aqui? Atualize o coletor, a página e este documento no mesmo commit.

---

## `dados/mercado/indicadores.json`

Escrito por `coletor/atualizar.py`, lido por `app/dados.js`.

```jsonc
{
  "coletado_em": "2026-09-11T00:56:22+00:00",   // UTC, ISO 8601
  "fonte": "Banco Central do Brasil - API SGS",
  "completo": true,                              // todos os campos com valor?
  "campos": {
    "cdi_aa":        { "valor": 13.9,   "origem": "Banco Central (SGS)", "serie_sgs": 4389, "referencia": "2026-09-09" },
    "selic_meta_aa": { "valor": 14.0,   "origem": "Banco Central (SGS)", "serie_sgs": 432,  "referencia": "2026-09-16" },
    "poupanca_am":   { "valor": 0.6698, "origem": "Banco Central (SGS)", "serie_sgs": 196,  "referencia": "2026-09-01" },
    "ipca_12m":      { "valor": 4.443,  "origem": "Banco Central (SGS)", "serie_sgs": 433,  "referencia": "2026-07-01" }
  }
}
```

- `valor: null` + `origem: "indisponivel"` quando a fonte falhou **e** não havia
  retrato anterior de onde herdar.
- Quando herda do retrato anterior, `origem` vira
  `"retrato anterior (fonte indisponivel na ultima coleta)"` e ganha `coletado_em`
  com a data do retrato de origem. A página trata isso como valor válido, mas a
  idade continua visível.
- `referencia` é a data do dado na fonte, não a data da coleta. As duas diferem — o
  IPCA sai com um a dois meses de atraso, por natureza do índice.

## `dados/mercado/series/{cdi,selic,ipca,poupanca}.json`

```jsonc
{
  "serie": "cdi",
  "rotulo": "CDI acumulado no mes",
  "fonte": "Banco Central do Brasil - SGS",
  "serie_sgs": 4391,
  "coletado_em": "2026-09-11T00:56:22+00:00",
  "pontos": [ { "data": "2016-06-01", "valor": 1.16 } ]   // % no mês
}
```

`pontos` vem **sempre em ordem cronológica crescente** e inclui o mês corrente, que
é parcial. Quem consome descarta o mês corrente — `app/dados.js` faz isso. O
acumulado e o índice base 100 são calculados na página, não gravados no arquivo:
dependem da janela que o usuário escolheu.

## `dados/catalogo/ativos.json` e `dados/premissas/premissas.json`

Editados à mão, lidos pela página. Schema completo no doc 02.

---

## Contrato interno: `app/nucleo/`

As três funções que o resto da página usa. São puras — nada de rede, nada de DOM.

```js
import { resolver } from './nucleo/indexadores.js';
// -> { taxa_aa, taxa_aa_antes_taxas, taxa_am, custo_aa, explicacao, natureza }
resolver(ativo, indicadores, premissas, cenario);

import { tributar } from './nucleo/tributos.js';
// -> { iof, ir, total, aliquota_efetiva, detalhe }
tributar(regime, lotes, valorVendaTotal, premissas.tributacao);

import { projetar, comparar } from './nucleo/motor.js';
// -> { resultados: [...], erros: [{ativo_id, erro}] }
comparar(ativos, indicadores, premissas, parametros);
```

`parametros` aceita `valor_inicial`, `aporte_mensal`, `meses`, `cenario`,
`considerar_ir` e `considerar_inflacao`.

### Um resultado de `projetar()`

```jsonc
{
  "ativo_id": "cdb-100-cdi",
  "nome": "CDB 100% do CDI",
  "classe": "renda_fixa",
  "risco": 2,
  "ranking": 1,
  "diferenca_para_1o": 0,

  "taxa": {
    "taxa_aa": 13.9,              // efetiva, já sem taxas de adm/custódia
    "taxa_aa_antes_taxas": 13.9,
    "taxa_am": 0.010906,          // FRAÇÃO ao mês, não percentual
    "custo_aa": 0,
    "explicacao": "100% do CDI (13,90% a.a.)",
    "natureza": "contratada"      // contratada | hibrida | estimada
  },

  "meses": 12,
  "investido": 100,
  "bruto": 113.9,
  "rendimento_bruto": 13.9,
  "impostos": { "iof": 0, "ir": 2.78, "total": 2.78, "aliquota_efetiva": 20, "detalhe": "IR regressivo: 20%" },
  "liquido": 111.12,
  "rendimento_liquido": 11.12,
  "liquido_real": 106.39,
  "ganho_real": 6.39,
  "rentabilidade_bruta_pct": 13.9,
  "rentabilidade_liquida_pct": 11.12,
  "rentabilidade_real_pct": 6.39,

  "inflacao": { "ipca_aa_projetado": 4.443, "fator": 1.04443, "perda_poder_compra_pct": 4.25, "cenario": "base" },

  "serie": [ { "mes": 0, "bruto": 100, "investido": 100 } ],   // meses + 1 pontos
  "lotes": 1
}
```

`taxa.natureza` é o que a página usa para marcar o selo "estimado" — trate `estimada`
visualmente diferente de `contratada`, sempre.

Um ativo que falha no cálculo não derruba a comparação: ele sai em `erros` e os
demais são comparados normalmente.

## Contrato de `app/dados.js` para a página

`indicadores()` devolve os quatro valores mais metadados com `_`:

| Campo | Significa |
|---|---|
| `_origem` | por indicador: origem, série SGS, data de referência |
| `_degradado` | algum indicador veio do fallback de `premissas.json` |
| `_coletado_em` | quando o retrato foi tirado (ISO, UTC) |
| `_idade_dias` | dias desde a coleta |
| `_vencido` | idade acima de `DIAS_ATE_VENCER` (10 dias) |

A página é obrigada a mostrar `_degradado` e `_vencido` ao usuário. Não são detalhes
de implementação: são a diferença entre um número confiável e um número velho.
