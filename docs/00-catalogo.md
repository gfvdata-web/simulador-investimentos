# Catálogo de documentação

Índice de toda a documentação do projeto. Cada arquivo cobre uma fatia que pode
evoluir sozinha, para você poder tocar frentes diferentes em prompts paralelos.

| # | Arquivo | Cobre | Leia quando for… |
|---|---|---|---|
| 01 | [`01-arquitetura.md`](01-arquitetura.md) | Camadas, fluxo de uma simulação, decisões e seus porquês | entender o todo, ou questionar uma decisão estrutural |
| 02 | [`02-modelo-de-dados.md`](02-modelo-de-dados.md) | Schema de `ativos.json` e `premissas.json`, tipos de rendimento | cadastrar ativo ou criar tipo de rendimento novo |
| 03 | [`03-motor-de-calculo.md`](03-motor-de-calculo.md) | Convenções de tempo, lotes de aporte, fórmulas, exemplos conferidos | mexer na projeção ou desconfiar de um número |
| 04 | [`04-fontes-de-dados.md`](04-fontes-de-dados.md) | APIs oficiais, séries usadas, cache, armadilhas conhecidas | plugar uma fonte nova ou investigar dado estranho |
| 05 | [`05-tributacao.md`](05-tributacao.md) | IR, IOF, isenções, come-cotas, o que ainda não é modelado | mexer em imposto |
| 06 | [`06-api.md`](06-api.md) | Contrato dos endpoints, formatos de requisição e resposta | trabalhar na página ou criar endpoint |
| 07 | [`07-frontend.md`](07-frontend.md) | Estrutura da página, estado, gráfico em canvas, tokens de tema | mexer na interface |
| 08 | [`08-roadmap.md`](08-roadmap.md) | Fases, o que está pronto, o que falta, dívidas conhecidas | escolher a próxima tarefa |

Fora de `docs/`:

- [`../README.md`](../README.md) — como rodar e o que já funciona.
- [`../CLAUDE.md`](../CLAUDE.md) — contrato de trabalho, regras invioláveis, convenções.

## Mapa de arquivos do projeto

```
SimuladorInvestimentos/
├── CLAUDE.md                      contrato de trabalho (leia primeiro)
├── README.md                      como rodar
├── backend/
│   ├── app.py                     servidor HTTP + roteamento da API
│   ├── dados.py                   leitura dos JSON + fusão com indicadores vivos
│   ├── engine/
│   │   ├── indexadores.py         rendimento do ativo -> taxa mensal efetiva
│   │   ├── tributos.py            IR, IOF, isenções
│   │   └── motor.py               projeção mês a mês por lote de aporte
│   └── fontes/
│       ├── bcb_sgs.py             cliente da API do Banco Central
│       └── cache.py               cache em arquivo com TTL
├── dados/
│   ├── catalogo/ativos.json       o que existe para simular
│   ├── premissas/premissas.json   indicadores de reserva, estimativas, regras fiscais
│   └── cache/                     respostas das fontes (descartável)
├── web/
│   ├── index.html                 estrutura da página
│   ├── estilo.css                 tokens de tema claro/escuro
│   └── app.js                     estado, chamadas à API, tabela e gráfico
├── scripts/iniciar.cmd            atalho de inicialização no Windows
└── docs/                          esta documentação
```

## Fronteiras entre as frentes

As quatro frentes conversam só por contrato, então dá para evoluir cada uma sem
quebrar as outras:

```
dados/*.json  ──schema do doc 02──>  backend/engine  ──contrato do doc 06──>  web/
                                            ^
                       backend/fontes ───────┘  (indicadores com procedência)
```

- Mexer em `web/` nunca exige mexer no motor: consuma o que o doc 06 promete.
- Mexer no catálogo nunca exige mexer em código, desde que o tipo de rendimento já exista.
- Adicionar fonte não muda o motor: ela só precisa entregar indicadores no formato do doc 04.
