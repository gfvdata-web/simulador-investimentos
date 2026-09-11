# Simulador de Investimentos

Simulador pessoal para comparar o rendimento de investimentos disponíveis no Brasil
(renda fixa, renda variável, ETFs, cripto) ao longo de um prazo escolhido — 12, 60 ou
quantos meses você quiser — com projeção **bruta, líquida de impostos e em valor real**
(descontada a inflação).

> Ferramenta de estudo pessoal. Não é recomendação de investimento, não é consultoria
> financeira e não tem valor preditivo.

## Como funciona

O site é **estático e não acessa a internet**. Os dados oficiais são buscados por um
coletor que roda sozinho no GitHub Actions em dias úteis e commita o resultado no
repositório; a página lê esses arquivos e faz todo o cálculo no navegador.

Isso significa que o simulador funciona mesmo com a fonte fora do ar, que cada
simulação é auditável pelo histórico do git (dá para ver exatamente qual CDI foi usado
em qualquer data), e que a idade do dado é sempre visível na tela.

## Rodando local

A página usa módulos ES, então precisa de um servidor estático — abrir o `index.html`
por duplo clique não funciona. Com Python 3 (já vem no Windows via Store, ou instale):

```bash
python -m http.server 8765
```

Depois abra <http://127.0.0.1:8765>. No Windows dá para dar duplo clique em
`scripts/iniciar.cmd`, que faz as duas coisas.

Para atualizar os dados de mercado na mão, sem esperar a automação:

```bash
python coletor/atualizar.py
```

**Nenhuma dependência** — nem `pip install`, nem `npm install`, nem CDN.

## O que já funciona (v0.2)

- Indicadores do Banco Central (CDI, Selic, IPCA 12 meses, poupança), cada um com a
  série do SGS e a data de referência visíveis na tela.
- 10 anos de histórico mensal de CDI, Selic, IPCA e poupança.
- Catálogo de 10 ativos-semente em JSON editável à mão.
- Projeção com aporte único e/ou aportes mensais, prazo livre de 1 a 600 meses.
- IR regressivo por lote de aporte, IOF nos 30 primeiros dias, isenções de LCI/LCA,
  poupança e cripto, 15% em ETF/ações.
- Valor real descontando o IPCA projetado, em três cenários.
- Gráfico comparativo mês a mês e aba de histórico real.
- Tema claro/escuro/sistema.

## Mapa rápido

| Pasta | O que tem |
|---|---|
| `index.html`, `app/` | a página: interface, motor de cálculo, camada fiscal |
| `coletor/` | o único código que fala com a internet |
| `dados/` | catálogo e premissas (edição humana) + retrato do mercado (gerado) |
| `docs/` | documentação — comece por `docs/00-catalogo.md` |

## Para continuar o desenvolvimento

Leia [`CLAUDE.md`](CLAUDE.md) (contrato de trabalho e convenções) e
[`docs/00-catalogo.md`](docs/00-catalogo.md) (índice de toda a documentação).
