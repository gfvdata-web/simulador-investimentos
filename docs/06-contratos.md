# 06 — Contratos entre as partes

Não existe API HTTP neste projeto: o coletor e a página conversam por **arquivos
versionados**. Estes são os formatos que as duas pontas precisam respeitar.

Mudou um formato aqui? Atualize o coletor, a página e este documento no mesmo commit.

---

## `dados/mercado/indicadores.json`

Escrito por `coletor/atualizar.py`, lido por `app/dados.js`. É o **manifesto do
retrato**: diz quais indicadores existem, quanto valem, como se chamam e onde ficam as
séries. A página não tem lista própria — ela se monta a partir deste arquivo.

```jsonc
{
  "coletado_em": "2026-09-11T00:56:22+00:00",   // UTC, ISO 8601
  "completo": true,                              // todos os campos e séries ok?
  "campos": {
    "cdi_aa": {
      "rotulo": "CDI",                           // texto exibido, com acento
      "unidade": "% a.a.",                       // define a formatação na tela
      "fonte": "Banco Central do Brasil - SGS",
      "referencia_fonte": 4389,                  // identificador na fonte (série SGS)
      "valor": 13.9,
      "origem": "fonte oficial",
      "referencia": "2026-09-09"                 // data do dado NA FONTE
    }
  },
  "series": [
    {
      "id": "cdi",
      "rotulo": "CDI acumulado no mês",
      "rotulo_curto": "CDI",                     // usado no seletor da aba histórico
      "arquivo": "series/cdi.json",              // relativo a dados/mercado/
      "fonte": "Banco Central do Brasil - SGS",
      "referencia_fonte": 4391,
      "pontos": 124, "primeiro": "2016-06-01", "ultimo": "2026-09-01"
    }
  ]
}
```

**`unidade` não é decoração.** A página formata por ela: `"% a.a."` vira `13,90% a.a.`,
`"R$"` vira `R$ 5,42`, `"pontos"` vira `104,3 pontos`. Um indicador de preço declara
`"R$"` e aparece certo sem tocar em código.

**Valores de `origem`**, em ordem de confiança:

| `origem` | Significa |
|---|---|
| `fonte oficial` | coletado agora, valor bom |
| `retrato anterior (fonte indisponivel na ultima coleta)` | herdado; vale, mas não é de hoje. A página marca o cartão |
| `indisponivel` | `valor: null`. A página tenta o fallback de `premissas.json`; se não houver, o campo simplesmente não aparece |

`referencia` é a data do dado na fonte, não a data da coleta. As duas diferem — o IPCA
sai com um a dois meses de atraso, por natureza do índice.

## `dados/mercado/series/*.json`

Mesmos metadados da entrada no manifesto, mais os pontos:

```jsonc
{
  "id": "cdi", "rotulo": "CDI acumulado no mês", "rotulo_curto": "CDI",
  "arquivo": "series/cdi.json",
  "fonte": "Banco Central do Brasil - SGS", "referencia_fonte": 4391,
  "coletado_em": "2026-09-11T00:56:22+00:00",
  "pontos": [ { "data": "2016-06-01", "valor": 1.16 } ]   // % no mês
}
```

`pontos` vem **sempre em ordem cronológica crescente** e inclui o mês corrente, que é
parcial. Quem consome descarta o mês corrente — `app/dados.js` faz isso. O acumulado e
o índice base 100 são calculados na página: dependem da janela escolhida.

## `dados/mercado/fundos/{TICKER}.json`

Um arquivo por FII/ETF coletado, escrito por `coletor/atualizar.py` (`coletar_fundos`),
lido por `app/dados.js` (`fundos(tickers)`) só para os tickers que o usuário marcou —
não é pré-carregado como indicadores. O manifesto entra em `indicadores.json` como
`fundos: [...]`, no mesmo espírito de `series`.

FII (fonte CVM, fato):

```jsonc
{
  "ticker": "VILG11", "tipo": "fii", "cnpj": "24.853.044/0001-22",
  "rotulo": "VILG11 (Vinci Logística FII)", "segmento": "Logística",
  "fonte": "CVM - Dados Abertos (Informe Mensal FII)",
  "coletado_em": "2026-09-11T01:34:11+00:00",
  "pontos": [
    { "data": "2026-07-01", "dividend_yield_pct": 0.75,
      "valorizacao_patrimonial_pct": -0.0006, "rentabilidade_efetiva_pct": 0.7495 }
  ],
  "resumo": {
    "janela_meses": 36,
    "dividend_yield_am_medio_pct": 0.5971,
    "valorizacao_patrimonial_am_media_pct": -0.063,
    "valorizacao_patrimonial_am_desvio_pct": 0.6247,
    "referencia": "2026-07-01",
    "metodo": "Média simples dos meses fechados publicados pela CVM."
  }
}
```

ETF (fonte B3, preço — a valorização é calculada por este projeto, ver doc 04):

```jsonc
{
  "ticker": "GOLD11", "tipo": "etf", "rotulo": "GOLD11 (Trend Ouro)",
  "indice": "ouro (commodity)", "fonte": "B3 - Séries Históricas (COTAHIST)",
  "coletado_em": "2026-09-11T01:34:11+00:00",
  "pontos": [ { "data": "2026-08-31", "fechamento": 23.98, "variacao_mes_pct": 12.2659 } ],
  "resumo": {
    "janela_meses": 43, "retorno_am_medio_pct": 2.0886,
    "retorno_aa": { "pessimista": 10.78, "base": 28.15, "otimista": 45.53 },
    "volatilidade_aa": 17.38, "referencia": "2026-08-31",
    "metodo": "CAGR mensal composto do fechamento (B3 COTAHIST)..."
  }
}
```

`resumo` é o que `app/nucleo/indexadores.js` de fato lê (tipos `fundo_fii` e
`etf_historico`, doc 02); `pontos` é o histórico bruto, guardado por transparência.
Falha na coleta preserva o arquivo anterior, igual às séries.

## Protocolo de uma fonte

Um módulo em `coletor/fontes/` precisa expor exatamente isto:

```python
NOME                    # str, nome legível que aparece na tela
FalhaFonte              # exceção quando a fonte não responde
ultimo(nome)            # -> {'data': 'YYYY-MM-DD', 'valor': float}
serie(nome, meses)      # -> [{'data': ..., 'valor': ...}], crescente por data
acumulado_12m(nome)     # -> {'valor': float, 'referencia': 'YYYY-MM-DD'}  (se usado)
```

Nunca devolva valor inventado: levante `FalhaFonte` e deixe `atualizar.py` decidir a
degradação. Registre o módulo em `FONTES` e acrescente as entradas em `INDICADORES`
e/ou `SERIES` — é a única edição necessária.

## `dados/catalogo/ativos.json` e `dados/premissas/premissas.json`

Editados à mão, lidos pela página. Schema completo no doc 02.

---

## Contrato interno: `app/nucleo/`

As três funções que o resto da página usa. São puras — nada de rede, nada de DOM.

```js
import { resolver } from './nucleo/indexadores.js';
// -> { taxa_aa, taxa_aa_antes_taxas, taxa_am, custo_aa, explicacao, natureza,
//      componente_isento_am?, componente_tributavel_am? }   // só 'fundo_fii' preenche os dois últimos
resolver(ativo, indicadores, premissas, cenario, fundos, considerarValorizacaoProjetada);

import { tributar } from './nucleo/tributos.js';
// -> { iof, ir, total, aliquota_efetiva, detalhe }
tributar(regime, lotes, valorVendaTotal, premissas.tributacao);

import { projetar, comparar } from './nucleo/motor.js';
// -> { resultados: [...], erros: [{ativo_id, erro}] }
comparar(ativos, indicadores, premissas, parametros, fundos);
```

`parametros` aceita `valor_inicial`, `aporte_mensal`, `meses`, `cenario`,
`considerar_ir`, `considerar_inflacao` e `considerar_valorizacao_projetada`.

`fundos` é opcional (default `{}`) e só precisa existir quando algum ativo escolhido
tem `rendimento.tipo` `fundo_fii` ou `etf_historico` — é o mapa
`{TICKER: conteúdo de dados/mercado/fundos/TICKER.json}` que `app/dados.js` monta sob
demanda (ver seção acima). Ativo do tipo fundo sem entrada em `fundos` cai em `erros`
com mensagem clara, nunca em zero.

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
  "dividendos_isentos": 0,       // > 0 só em 'fundo_fii': dividendo já recebido, isento, fora do capital tributável
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

`indicadores()` devolve os valores por nome (`ind.cdi_aa`), mais metadados com `_`:

| Campo | Significa |
|---|---|
| `_meta` | por indicador: `rotulo`, `unidade`, `origem`, `heranca`, `referencia`, `referencia_fonte` |
| `_degradado` | algum indicador veio do fallback de `premissas.json` |
| `_coletado_em` | quando o retrato foi tirado (ISO, UTC) |
| `_idade_dias` | dias desde a coleta |
| `_vencido` | idade acima de `DIAS_ATE_VENCER` (10 dias) |

`seriesDisponiveis()` devolve o manifesto de séries; é o que preenche o seletor da aba
de histórico. A página nunca lista séries à mão.

`fundos(tickers)` devolve `{TICKER: conteúdo do arquivo}` só para os tickers pedidos
(deduplicados) — quem decide quais tickers pedir é `app.js`, a partir dos ativos
marcados na tela. Ticker sem arquivo coletado sai do mapa (não vira `null` nem erro
aqui); `resolver()` é quem acusa a falta, com mensagem.

A página é obrigada a mostrar `_degradado` e `_vencido` ao usuário. Não são detalhes
de implementação: são a diferença entre um número confiável e um número velho.
