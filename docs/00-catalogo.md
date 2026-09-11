# Catálogo de documentação

Índice de toda a documentação do projeto. Cada arquivo cobre uma fatia que pode
evoluir sozinha, para você poder tocar frentes diferentes em prompts paralelos.

| # | Arquivo | Cobre | Leia quando for… |
|---|---|---|---|
| 01 | [`01-arquitetura.md`](01-arquitetura.md) | Camadas, fluxo de uma simulação, decisões e seus porquês | entender o todo, ou questionar uma decisão estrutural |
| 02 | [`02-modelo-de-dados.md`](02-modelo-de-dados.md) | Schema de `ativos.json` e `premissas.json`, tipos de rendimento | cadastrar ativo ou criar tipo de rendimento novo |
| 03 | [`03-motor-de-calculo.md`](03-motor-de-calculo.md) | Convenções de tempo, lotes de aporte, fórmulas, exemplos conferidos | mexer na projeção ou desconfiar de um número |
| 04 | [`04-fontes-de-dados.md`](04-fontes-de-dados.md) | APIs oficiais, séries usadas, coleta agendada, armadilhas | plugar uma fonte nova ou investigar dado estranho |
| 05 | [`05-tributacao.md`](05-tributacao.md) | IR, IOF, isenções, come-cotas, o que ainda não é modelado | mexer em imposto |
| 06 | [`06-contratos.md`](06-contratos.md) | Formato dos arquivos de dados e das funções do núcleo | trabalhar na página ou no coletor |
| 07 | [`07-frontend.md`](07-frontend.md) | Estrutura da página, estado, gráfico em canvas, tokens de tema | mexer na interface |
| 08 | [`08-roadmap.md`](08-roadmap.md) | Fases, o que está pronto, o que falta, dívidas conhecidas | escolher a próxima tarefa |

Fora de `docs/`:

- [`../README.md`](../README.md) — como rodar e o que já funciona.
- [`../CLAUDE.md`](../CLAUDE.md) — contrato de trabalho, regras invioláveis, convenções.

## Mapa de arquivos do projeto

```
SimuladorInvestimentos/
├── index.html                     a pagina (raiz, porque o Pages serve daqui)
├── CLAUDE.md                      contrato de trabalho (leia primeiro)
├── README.md                      como rodar
├── app/
│   ├── estilo.css                 tokens de tema claro/escuro
│   ├── app.js                     estado, render, grafico, tema
│   ├── dados.js                   le os JSON do repositorio, carimba procedencia
│   └── nucleo/                    funcoes puras, sem I/O
│       ├── indexadores.js         rendimento do ativo -> taxa mensal efetiva
│       ├── tributos.js            IR, IOF, isencoes
│       └── motor.js               projecao mes a mes por lote de aporte
├── coletor/                       o unico que fala com a internet
│   ├── atualizar.py               roda no Actions, grava dados/mercado/
│   └── fontes/
│       ├── bcb_sgs.py             cliente da API do Banco Central
│       ├── cvm_fii.py             cliente do informe mensal de FII (CVM)
│       └── b3_precos.py           cliente das series historicas (B3 COTAHIST)
├── dados/
│   ├── catalogo/ativos.json       o que existe para simular      (edicao humana)
│   ├── premissas/premissas.json   estimativas e regras fiscais   (edicao humana)
│   └── mercado/                   retrato do mercado             (gerado, versionado)
│       ├── indicadores.json
│       ├── series/{cdi,selic,ipca,poupanca}.json
│       └── fundos/{TICKER}.json   um por FII/ETF cadastrado
├── .github/workflows/
│   ├── atualizar-dados.yml        coleta agendada
│   └── publicar.yml               publicacao no GitHub Pages
├── scripts/
│   ├── validar.py                 confere catalogo e premissas contra o codigo
│   ├── iniciar.cmd                sobe servidor estatico e abre a pagina
│   └── atualizar-dados.cmd        roda o coletor na mao
└── docs/                          esta documentacao
```

## Fronteiras entre as frentes

As quatro frentes conversam só por contrato, então dá para evoluir cada uma sem
quebrar as outras:

```
coletor/  ──formato do doc 06──>  dados/mercado/  ──┐
                                                    ├──> app/nucleo/  ──>  app/app.js
dados/catalogo + dados/premissas  ──doc 02──────────┘
```

- Mexer na página nunca exige mexer no motor: consuma o que o doc 06 promete.
- Mexer no catálogo nunca exige mexer em código, desde que o tipo de rendimento já exista.
- Adicionar fonte não muda a página: basta gravar no formato do doc 06.
- O coletor não sabe calcular rendimento; o motor não sabe falar com a internet.
