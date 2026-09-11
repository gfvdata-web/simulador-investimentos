# 06 — Contrato da API

Servidor: `backend/app.py`, em `http://127.0.0.1:8765` por padrão. Toda resposta é
JSON UTF-8. Erro vem como `{"erro": "mensagem legível", "detalhe": "opcional"}` com
status 400 (entrada inválida), 404 (rota), 503 (fonte oficial fora) ou 500.

**Este documento é o contrato entre a página e o backend.** Mudou aqui, atualize no
mesmo commit.

---

## `GET /api/saude`

```json
{ "status": "ok", "versao": "0.1.0", "web": true }
```

## `GET /api/indicadores`

Aceita `?atualizar=1` para ignorar o cache e reconsultar o Banco Central.

```json
{
  "cdi_aa": 13.9,
  "selic_meta_aa": 14.0,
  "ipca_12m": 4.443,
  "poupanca_am": 0.6698,
  "tr_am": 0.0,
  "_origem": {
    "cdi_aa": { "origem": "Banco Central (SGS)", "serie_sgs": 4389, "referencia": "2026-09-09" },
    "ipca_12m": { "origem": "fallback de premissas.json", "referencia": "2026-09-10", "detalhe": "..." }
  },
  "_degradado": false,
  "_consultado_em": "2026-09-10"
}
```

Campos com `_` são metadados. `_degradado: true` significa que ao menos um indicador
veio do fallback — a página mostra aviso amarelo nesse caso.

## `GET /api/ativos`

Devolve `dados/catalogo/ativos.json` inteiro. Schema no doc 02.

## `GET /api/premissas`

Devolve `dados/premissas/premissas.json` inteiro. Útil para a página mostrar a fonte
de uma estimativa sem ter que adivinhá-la.

## `GET /api/historico`

| Parâmetro | Padrão | Valores |
|---|---|---|
| `serie` | `cdi` | `cdi`, `selic`, `ipca`, `poupanca` |
| `meses` | `60` | 1 a 360 |

```json
{
  "serie": "cdi",
  "rotulo": "CDI acumulado no mês",
  "fonte": "Banco Central do Brasil - SGS",
  "serie_sgs": 4391,
  "acumulado_total_pct": 14.6274,
  "pontos": [
    { "data": "2025-09-01", "mensal_pct": 1.08, "acumulado_pct": 1.08, "indice_100": 101.08 }
  ]
}
```

`indice_100` é quanto valeriam R$ 100 aplicados no primeiro ponto — é o que o gráfico
histórico desenha. Pontos vêm em ordem cronológica e o mês corrente (parcial) é
descartado. Se a fonte estiver fora, responde 503.

## `POST /api/simular`

```json
{
  "ativos": ["cdb-100-cdi", "lci-95-cdi", "bova11"],
  "valor_inicial": 100.0,
  "aporte_mensal": 0.0,
  "meses": 12,
  "cenario": "base",
  "considerar_ir": true,
  "considerar_inflacao": true
}
```

Só `ativos` é obrigatório; o resto cai nos `defaults_simulacao` das premissas.
`cenario` é `pessimista`, `base` ou `otimista` e só afeta ativos de retorno estimado e
a inflação projetada.

### Resposta

```json
{
  "resultados": [ { } ],
  "erros": [ { "ativo_id": "x", "erro": "motivo" } ],
  "parametros": { },
  "indicadores": { },
  "procedencia": { },
  "dados_degradados": false
}
```

`resultados` já vem ordenado do maior para o menor valor líquido. Um ativo que falha
não derruba a chamada: ele sai em `erros` e os outros são comparados normalmente.

### Um resultado

```jsonc
{
  "ativo_id": "cdb-100-cdi",
  "nome": "CDB 100% do CDI",
  "classe": "renda_fixa",
  "risco": 2,
  "ranking": 1,
  "diferenca_para_1o": 0.0,

  "taxa": {
    "taxa_aa": 13.9,              // efetiva, já sem taxas de adm/custódia
    "taxa_aa_antes_taxas": 13.9,
    "taxa_am": 0.010906,          // FRAÇÃO ao mês, não percentual
    "custo_aa": 0.0,
    "explicacao": "100% do CDI (13,90% a.a.)",
    "natureza": "contratada"      // contratada | hibrida | estimada
  },

  "meses": 12,
  "investido": 100.0,
  "bruto": 113.9,
  "rendimento_bruto": 13.9,
  "impostos": {
    "iof": 0.0, "ir": 2.78, "total": 2.78,
    "aliquota_efetiva": 20.0,
    "detalhe": "IR regressivo: 20%"
  },
  "liquido": 111.12,
  "rendimento_liquido": 11.12,
  "liquido_real": 106.39,
  "ganho_real": 6.39,
  "rentabilidade_bruta_pct": 13.9,
  "rentabilidade_liquida_pct": 11.12,
  "rentabilidade_real_pct": 6.39,

  "inflacao": {
    "ipca_aa_projetado": 4.443,
    "fator": 1.04443,
    "perda_poder_compra_pct": 4.25,
    "cenario": "base"
  },

  "serie": [ { "mes": 0, "bruto": 100.0, "investido": 100.0 } ],
  "lotes": 1
}
```

`taxa.natureza` é o que a página usa para marcar o selo "estimado" — trate `estimada`
visualmente diferente de `contratada`, sempre.

`serie` tem `meses + 1` pontos (o mês 0 é o ponto de partida) e alimenta o gráfico.

---

## Ao criar um endpoint

- Rota nova entra no dicionário `rotas` de `_tratar_api_get`, ou num `if` de `do_POST`.
- Envolva o handler com `self._proteger(...)`: ele converte `ValueError` e `KeyError` em
  400 com mensagem legível, e qualquer outra exceção em 500 com stack no terminal.
- Valide a entrada antes de chegar no motor. O motor confia no que recebe.
- Documente aqui, com um exemplo de resposta real — não inventado.
