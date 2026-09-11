# 03 — Motor de cálculo

Arquivo: `backend/engine/motor.py`. Funções puras: recebem dicionários, devolvem
dicionários, não tocam rede nem disco.

## Convenções de tempo

- O **mês 1** é o primeiro mês cheio de rendimento. O mês 0 existe só no gráfico, para
  marcar o ponto de partida.
- O capital inicial entra no começo do mês 1 e rende os N meses inteiros.
- Cada aporte mensal entra no começo do seu mês e rende **daquele mês em diante**. Uma
  simulação de 12 meses com aporte mensal tem 12 aportes, e o último rende 1 mês.
- Prazo para fins de IR usa **mês comercial de 30 dias**. 12 meses = 360 dias, que cai
  na faixa de 20%. É uma simplificação consciente: a alternativa (calendário real)
  moveria alguns casos de fronteira sem mudar a ordem do ranking.

## Lotes

Cada entrada de dinheiro vira um lote independente:

```python
{"mes_entrada": 7, "principal": 500.0, "valor_final": 612.34, "dias": 1620}
```

Todos os lotes rendem à mesma taxa mensal, mas cada um carrega seu próprio prazo — e é
o prazo que define a alíquota de IR. Por isso a explicação na tela pode dizer
*"IR regressivo: 15% a 22,5% (aportes com prazos diferentes)"*.

Sem isso, uma simulação de 60 meses com aporte mensal aplicaria 15% sobre tudo e
superestimaria o líquido.

## Fórmulas

**Anual para mensal** (`indexadores.aa_para_am`):

```
taxa_mensal = (1 + taxa_anual/100)^(1/12) − 1
```

Juro composto, não divisão por 12. Com CDI a 13,90% a.a., o mês dá 1,0906% — dividir
por 12 daria 1,158% e inflaria a projeção de 5 anos em vários pontos percentuais.

**Composição de duas taxas** (`compor`) — usada em IPCA+ e em Selic + spread:

```
resultado = ((1 + a/100) × (1 + b/100) − 1) × 100
```

IPCA de 4,30% com juro real de 6% dá 10,56% a.a., não 10,30%.

**Desconto de custo** (`descontar`) — taxa de administração e custódia:

```
líquida = ((1 + bruta/100) ÷ (1 + custo/100) − 1) × 100
```

**Valor real** — poder de compra em reais de hoje:

```
fator_inflação = (1 + ipca_projetado/100)^(meses/12)
valor_real = valor_líquido ÷ fator_inflação
```

## Casos conferidos à mão

Com CDI em 13,90% a.a. e IPCA projetado em 4,443% a.a. (cenário base):

| Caso | Esperado | Confere |
|---|---|---|
| R$ 100, CDB 100% CDI, 12 meses | bruto R$ 113,90 · IR 20% sobre R$ 13,90 = R$ 2,78 · líquido R$ 111,12 | sim |
| R$ 100, LCI 95% CDI, 12 meses | taxa 13,205% · bruto R$ 113,20 · isento · líquido R$ 113,20 | sim |
| R$ 100, CDB 100% CDI, 12 meses, real | R$ 111,12 ÷ 1,04443 = R$ 106,39 | sim |
| R$ 1.000 + R$ 200/mês, CDB 100% CDI, 24 meses | investido R$ 5.800 · bruto R$ 6.809,75 · IR R$ 182,30 (faixas 17,5% a 22,5%) | sim |

**Ao mexer no motor, reconfira esta tabela.** Se um número mudar, ou você achou um bug
antigo ou introduziu um novo — descubra qual antes de atualizar a tabela. Os dois
primeiros casos dependem do CDI vigente; o que precisa se manter é a relação, não o
valor absoluto.

## Limites e validações

- Prazo entre 1 e 600 meses (`MAX_MESES`).
- Aportes não podem ser negativos; pelo menos um dos dois (inicial ou mensal) > 0.
- Ativo que falha no cálculo não derruba a simulação: ele sai na lista `erros` da
  resposta e os demais são comparados normalmente.

## O que o motor ainda não modela

Ver doc 08 para a lista completa de dívidas. As três que mais afetam a fidelidade:

1. **Marcação a mercado.** Prefixado e IPCA+ são projetados como se fossem levados ao
   vencimento. Resgate antecipado pode dar resultado bem diferente.
2. **Come-cotas.** Fundos pagariam IR semestral, o que reduz o efeito de juros
   compostos. Por isso não há fundo no catálogo semente.
3. **Volatilidade.** Renda variável rende hoje uma linha reta com a taxa do cenário.
   `volatilidade_aa` já está no JSON esperando o Monte Carlo.
