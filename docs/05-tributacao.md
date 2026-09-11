# 05 — Tributação

Arquivo: `backend/engine/tributos.py`. Tabelas em `premissas.json`, bloco `tributacao`.

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

### `acoes`
15% sobre o ganho, isento se o total vendido no mês ficar até R$ 20.000. O simulador
compara o limite com o valor total resgatado ao fim do prazo, assumindo venda única.
Vendas parceladas ao longo de meses poderiam ficar isentas e o simulador não modela isso.

### `cripto`
15% sobre o ganho, isento se o total alienado no mês ficar até R$ 35.000. Mesma
simplificação de venda única.

### `fundo_longo_prazo`
Implementado de forma **incompleta**: hoje cobra 15% no resgate e ignora o come-cotas.
Por isso não há nenhum fundo no catálogo semente — cadastrar um agora produziria um
número otimista demais.

## Come-cotas — o que falta

Fundos de investimento (exceto ações) antecipam IR em maio e novembro, comendo cotas:
15% ao ano em fundos de longo prazo, 20% em curto prazo. O efeito é reduzir o montante
que segue rendendo, então o prejuízo cresce com o prazo — em 10 anos a diferença é
material, não cosmética.

Para implementar: em `motor.projetar()`, a cada 6 meses, tributar o rendimento
acumulado de cada lote desde a última cobrança e abater do `valor_final`, guardando o
imposto já pago para não cobrar de novo no resgate. Ligue por
`premissas.tributacao.come_cotas_habilitado`, hoje em `false`.

## Outras simplificações conscientes

- **Sem compensação de prejuízo.** Perda em renda variável pode abater ganho futuro; o
  simulador trata cada ativo isoladamente.
- **Sem IR sobre dividendos e JCP.** O modelo projeta retorno total, sem separar
  dividendo de valorização. JCP tem 15% na fonte e ficaria de fora.
- **Sem taxa de corretagem e emolumentos.** `taxas` cobre administração e custódia; o
  custo de cada operação não entra.
- **Sem IR mensal via DARF em renda variável.** O imposto sai todo no resgate final.

## Ao mexer aqui

1. Tabela nova vai em `premissas.json`, não no código — assim uma mudança de lei é
   edição de dado.
2. Todo regime devolve o mesmo formato: `iof`, `ir`, `total`, `aliquota_efetiva`,
   `detalhe`. O campo `detalhe` aparece na tela sob cada linha e precisa explicar em
   uma frase o que foi cobrado e por quê.
3. Regime desconhecido levanta `ValueError`. Não adicione um `else` que devolve zero:
   silêncio aqui vira número errado na tela.
4. Atualize a tabela de casos conferidos do doc 03.
