# 02 — Modelo de dados

Dois arquivos, dois papéis bem separados.

| Arquivo | Contém | Quem edita |
|---|---|---|
| `dados/catalogo/ativos.json` | **o que existe** para simular e como cada coisa rende | você, à mão |
| `dados/premissas/premissas.json` | **quanto vale** o que não é contratado + regras fiscais | você, à mão |

O catálogo nunca guarda valor de mercado ou palpite de retorno. Um ativo diz *"rendo
110% do CDI"* (característica contratada, estável) — quanto é o CDI hoje vem do Banco
Central, e quanto o Bitcoin vai render vem de `premissas.json`.

## Schema de um ativo

```jsonc
{
  "id": "tesouro-ipca-2035",        // kebab-case, único, é a chave usada pela API
  "nome": "Tesouro IPCA+ 2035",     // texto exibido
  "classe": "renda_fixa",           // renda_fixa | renda_variavel | cripto | fundos
  "subclasse": "tesouro_direto",    // livre, serve para agrupar e filtrar
  "emissor_tipo": "governo",        // governo | banco | empresa | gestora | nenhum
  "liquidez": "diaria_com_marcacao",// texto livre; ainda não afeta o cálculo
  "risco": 3,                       // 1 (mais seguro) a 6 (mais arriscado), escala própria
  "fgc": false,                     // coberto pelo Fundo Garantidor de Créditos?
  "rendimento": { },                // ver abaixo
  "tributacao": { "regime": "rf_regressivo", "iof_ate_30d": true },
  "taxas": { "administracao_aa": 0.0, "custodia_aa": 0.20 },
  "descricao": "uma frase, aparece no tooltip da página"
}
```

### Tipos de rendimento

Implementados em `backend/engine/indexadores.py`, função `resolver`.

| `tipo` | Campos | Significa | Natureza |
|---|---|---|---|
| `pos_cdi` | `percentual_cdi` | X% do CDI vigente | contratada |
| `pos_selic` | `spread_aa` (opcional) | Selic meta, mais um spread | contratada |
| `prefixado` | `taxa_aa` | taxa travada na compra | contratada |
| `ipca_mais` | `spread_aa` | IPCA projetado composto com juro real | híbrida |
| `poupanca` | — | regra vigente da poupança, via série do BCB | contratada |
| `estimado` | `chave_premissa` | aponta para um bloco de `estimativas` | **estimada** |

A `natureza` volta na resposta da API e é o que faz a página marcar o selo
"estimado". É o mecanismo que impede fato e palpite de se confundirem na tela.

**Para criar um tipo novo** (ex.: `cdi_mais`, para "CDI + 2%"): adicione um ramo em
`resolver()`, devolva `taxa_aa` + `explicacao` + `natureza`, documente a linha na
tabela acima e só então cadastre ativos usando ele.

### Regimes tributários

Valores aceitos em `tributacao.regime`, implementados em `tributos.py`:
`isento`, `rf_regressivo`, `etf_renda_variavel`, `acoes`, `cripto`,
`fundo_longo_prazo`. Detalhes de cada um no doc 05.

## Schema das premissas

```jsonc
{
  "indicadores": { },   // FALLBACK. Só é usado se o BCB estiver fora do ar.
  "estimativas": { },   // PALPITES. Sempre por cenário, sempre com fonte.
  "tributacao": { },    // tabelas de IR, IOF e limites de isenção
  "defaults_simulacao": { }  // valores iniciais dos campos da página
}
```

### `indicadores` — só reserva

Os quatro campos (`cdi_aa`, `selic_meta_aa`, `ipca_12m`, `poupanca_am`) são
sobrescritos pelos dados do Banco Central sempre que a API responde. Eles existem para
o simulador continuar funcionando offline — e quando isso acontece, a página mostra um
aviso amarelo. Vale mantê-los razoavelmente atualizados mesmo assim.

### `estimativas` — palpite com etiqueta

```jsonc
"bova11": {
  "retorno_aa": { "pessimista": -8.0, "base": 11.0, "otimista": 24.0 },
  "volatilidade_aa": 24.0,
  "fonte": "Média histórica de longo prazo do Ibovespa; NÃO é previsão."
}
```

Todo bloco de estimativa precisa dos três cenários e de `fonte` preenchida. O campo
`fonte` não é decoração: é o que permite reconferir o palpite meses depois e o que
lembra, na revisão, que aquele número foi escolhido e não medido. `volatilidade_aa`
ainda não é usada — está reservada para o Monte Carlo da fase 5.

`ipca_projetado_aa` segue o mesmo formato e é usado em dois lugares: no cálculo de
`ipca_mais` e na conversão de valor nominal para valor real.

## Invariantes

- Todo `id` é único no catálogo.
- Todo `chave_premissa` de um ativo `estimado` existe em `estimativas`. Se não existir,
  `resolver()` levanta erro e o ativo aparece na lista `erros` da resposta, em vez de
  render zero silenciosamente.
- Taxas estão sempre em **pontos percentuais ao ano** (`0.20` significa 0,20% a.a.,
  não 20%).
- `risco` é uma escala editorial sua, não uma medida estatística — não use para cálculo.
