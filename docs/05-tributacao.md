# 05 — Tributação

Arquivo: `app/nucleo/tributos.js`. Tabelas em `premissas.json`, bloco `tributacao`.

> Reflete a legislação geral para pessoa física residente no Brasil. Não é orientação
> tributária. Reconfira antes de usar para qualquer decisão real — e especialmente
> antes de declarar qualquer coisa.

## Regimes implementados

### `isento`
LCI, LCA, CRI, CRA, poupança, debênture incentivada. IR zero para pessoa física. É por
isso que uma LCI a 95% do CDI bate um CDB a 100% do CDI em quase todo prazo.

### `rf_regressivo`
CDB, RDB, LC, Tesouro Direto, debênture comum. Dois tributos, nesta ordem:

**IOF** — só nos 30 primeiros dias, sobre o rendimento, em tabela regressiva de 96% no
primeiro dia a 0% no trigésimo. Na prática só aparece em simulações de 1 mês.

**IR** — sobre o rendimento já descontado o IOF:

| Prazo da aplicação | Alíquota |
|---|---|
| até 180 dias | 22,5% |
| 181 a 360 dias | 20% |
| 361 a 720 dias | 17,5% |
| acima de 720 dias | 15% |

Aplicado **por lote**: cada aporte tem seu prazo próprio (ver doc 03).

### `etf_renda_variavel`
ETFs de ações negociados na B3 (BOVA11, IVVB11). 15% sobre o ganho de capital, **sem**
a isenção mensal — ela não vale para ETF. Diferença que costuma surpreender quem
compara ETF com ação.

### `fundo_acoes`
Fundo de ações (FIA) sem ticker de bolsa (ex.: Itaú Index Vale Ações). Mesma conta de
`etf_renda_variavel` — 15% sobre o ganho, sem isenção mensal — porque a lei trata os
dois igual: FIA não tem come-cotas, mas também não tem a isenção de R$ 20.000/mês que
vale só pra venda direta de ação por pessoa física. Regime separado de
`etf_renda_variavel` só por clareza de leitura no catálogo (um FIA não é ETF), a conta
em `tributos.js` é a mesma linha de código.

### `acoes`
15% sobre o ganho, isento se o total vendido no mês ficar até R$ 20.000. O simulador
compara o limite com o valor total resgatado ao fim do prazo, assumindo venda única.
Vendas parceladas ao longo de meses poderiam ficar isentas e o simulador não modela isso.

Também usado por **BDR** (recibo de ação estrangeira negociado na B3, ex.: MSFT34):
a Receita equipara BDR a ação para fins de IR, isenção mensal incluída — diferente de
ETF, que não tem essa isenção (ver `etf_renda_variavel` acima).

### `cripto`
15% sobre o ganho, isento se o total alienado no mês ficar até R$ 35.000. Mesma
simplificação de venda única.

### `fii`
FII (fundo imobiliário) negociado em bolsa. Dois tributos bem separados, ao contrário
de todo regime acima:

- **Dividendo mensal — isento** de IR para pessoa física (fundo com +50 cotistas,
  cotas só negociadas em bolsa — todo FII cadastrado hoje se qualifica). O motor já
  tira essa parte do capital tributável antes de chamar `tributar()` (ver doc 03,
  `componente_isento_am`); por isso `tributar()` só vê o que sobrou.
- **Ganho de capital na venda de cotas — 20%**, `ir_fii_aliquota` em `premissas.json`,
  **sem** a isenção mensal de R$ 20.000 que vale para ação.

`tributar('fii', ...)` recebe só a parte patrimonial dos lotes (o dividendo nunca
entrou neles) — se a cota não valorizou na projeção, `rendimento_total <= 0` e o
regime devolve zero, exatamente como qualquer outro regime nesse caso.

Sem come-cotas: diferente de um fundo comum, FII não antecipa IR semestral — por isso
ele entrou no catálogo antes de `fundo_longo_prazo` estar completo.

### `fundo_longo_prazo`
Fundo multimercado ou renda-fixa-longo-prazo sem ticker de bolsa (ex.: Itaú Global
Dinâmico Plus). **Tem come-cotas**: a Receita antecipa 15% em maio e novembro sobre o
ganho acumulado desde a última cobrança, "comendo" cotas — não é imposto extra, é
adiantamento do que seria devido no resgate. `tributos.tributar()` credita o que já
foi retido contra a mesma tabela regressiva da renda fixa (22,5% a 15% por prazo) na
hora do resgate, cobrando só a diferença. O algoritmo completo, com a fórmula
lote a lote, está no doc 03.

Ligado por `premissas.tributacao.come_cotas_habilitado` (hoje `true`) — só entra em
vigor pra ativos com este regime, o resto do catálogo não é afetado. Efeito líquido:
o resultado sai **menor** que "tributar 15% só no resgate", porque o imposto antecipado
reduz a base que compõe juros depois. É por causa desse efeito que o projeto recusou
cadastrar fundo comum enquanto isso não estava implementado — cadastrar sem come-cotas
geraria um número otimista demais (dívida que constava no doc 08 até 2026-09-11).

## Outras simplificações conscientes

- **Sem compensação de prejuízo.** Perda em renda variável pode abater ganho futuro; o
  simulador trata cada ativo isoladamente.
- **Sem IR sobre dividendos e JCP.** O modelo projeta retorno total, sem separar
  dividendo de valorização. JCP tem 15% na fonte e ficaria de fora.
- **Sem taxa de corretagem e emolumentos.** `taxas` cobre administração e custódia; o
  custo de cada operação não entra.
- **Sem IR mensal via DARF em renda variável.** O imposto sai todo no resgate final.
- **ETF (`etf_historico`) não separa distribuição de preço.** O retorno vem só do
  fechamento na B3 (COTAHIST); se o ETF distribuir algum provento, ele já está
  embutido no preço (ou não está sendo capturado) — não há um dado equivalente ao
  informe mensal de FII para ETF. Ver doc 04.

## Ao mexer aqui

1. Tabela nova vai em `premissas.json`, não no código — assim uma mudança de lei é
   edição de dado.
2. Todo regime devolve o mesmo formato: `iof`, `ir`, `total`, `aliquota_efetiva`,
   `detalhe`. O campo `detalhe` aparece na tela sob cada linha e precisa explicar em
   uma frase o que foi cobrado e por quê.
3. Regime desconhecido levanta `ValueError`. Não adicione um `else` que devolve zero:
   silêncio aqui vira número errado na tela.
4. Atualize a tabela de casos conferidos do doc 03.
