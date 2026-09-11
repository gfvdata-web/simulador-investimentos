# Simulador de Investimentos

Simulador pessoal para comparar o rendimento de investimentos disponíveis no Brasil
(renda fixa, renda variável, ETFs, cripto) ao longo de um prazo escolhido — 12, 60 ou
quantos meses você quiser — com projeção **bruta, líquida de impostos e em valor real**
(descontada a inflação).

> Ferramenta de estudo pessoal. Não é recomendação de investimento, não é consultoria
> financeira e não tem valor preditivo.

## Rodando

Só precisa de Python 3.10+. **Nenhuma dependência externa.**

```bash
python -m backend.app
```

A página abre em <http://127.0.0.1:8765>. O servidor escuta apenas em `127.0.0.1` —
nada fica exposto na rede local.

Opções:

```bash
python -m backend.app --porta 9000 --sem-navegador
```

No Windows também dá para dar duplo clique em `scripts/iniciar.cmd`.

## O que já funciona (v0.1)

- Indicadores ao vivo do Banco Central (CDI, Selic, IPCA 12 meses, poupança), com a
  procedência de cada número visível na tela.
- Catálogo de 10 ativos-semente em JSON editável à mão.
- Projeção com aporte único e/ou aportes mensais, prazo livre de 1 a 600 meses.
- IR regressivo por lote de aporte, IOF nos 30 primeiros dias, isenções de LCI/LCA,
  poupança e cripto, 15% em ETF/ações.
- Valor real descontando o IPCA projetado.
- Gráfico comparativo mês a mês e série histórica real do BCB (últimos 60 meses).

## Mapa rápido

| Pasta | O que tem |
|---|---|
| `backend/` | Servidor HTTP, motor de cálculo, camada fiscal, cliente do BCB |
| `dados/` | Catálogo de ativos e premissas em JSON + cache das consultas |
| `web/` | Página do simulador (HTML/CSS/JS puro, sem build) |
| `docs/` | Documentação de arquitetura — comece por `docs/00-catalogo.md` |

## Para continuar o desenvolvimento

Leia [`CLAUDE.md`](CLAUDE.md) (contrato de trabalho e convenções) e
[`docs/00-catalogo.md`](docs/00-catalogo.md) (índice de toda a documentação).
