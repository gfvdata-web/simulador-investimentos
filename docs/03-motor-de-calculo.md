# 03 — Motor de cálculo

Arquivo: `app/nucleo/motor.js`. Funções puras: recebem objetos, devolvem objetos,
não tocam rede nem disco.

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

**Anual para mensal** (`indexadores.aaParaAm`):

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

## Dividendo isento x valorização tributável (FII)

Todo ativo, exceto `fundo_fii`, faz o lote inteiro crescer pela mesma
`taxa_am` e tributa o rendimento inteiro no resgate. FII é diferente: o
dividendo mensal é isento de IR (pessoa física, fundo listado com +50
cotistas) e a valorização da cota só é tributada — a 20%, sem isenção mensal —
se e quando a posição é "vendida" no fim da simulação.

Por isso `resolver()` devolve, só para `fundo_fii`, dois componentes:

```
componente_isento_am        = dividend yield médio (fato, CVM)
componente_tributavel_am    = valorização patrimonial média, OU 0 se
                               "considerar_valorizacao_projetada" estiver desligado
```

E `projetar()` trata os dois separadamente, mês a mês:

```
dividendos_isentos  += lote.valor_final × componente_isento_am     (sai da posição, não compõe capital)
lote.valor_final    *= 1 + componente_tributavel_am                (fica na cota, sofre ganho de capital depois)
```

Para todo outro tipo, `componente_isento_am` é `0` e `componente_tributavel_am`
é a própria `taxa_am` — a conta se reduz exatamente ao que era antes de FII
existir (dividendos_isentos fica sempre `0`). Essa equivalência foi conferida
rodando o caso do CDB abaixo antes e depois da mudança: mesmo resultado, ao
centavo.

## Come-cotas (regime `fundo_longo_prazo`)

Fundo multimercado/renda-fixa-longo-prazo antecipa IR duas vezes por ano (maio e
novembro): a Receita tributa a 15% o ganho acumulado desde a última cobrança e
"come" a diferença em cotas. Não é imposto extra — é adiantamento do que seria
devido no resgate, creditado contra a mesma tabela regressiva da renda fixa
(doc 05) quando a posição é encerrada.

Ligado só quando `premissas.tributacao.come_cotas_habilitado` é `true` (é o
padrão) **e** o regime do ativo é `fundo_longo_prazo`. Maio/novembro reais são
aproximados por múltiplo de 6 do mês simulado (`mes % 6 === 0`), pulando o
próprio mês do resgate — essa é a mesma simplificação de mês comercial que já
existe pro IR, documentada, não escondida.

Em `projetar()`, a cada evento, por lote:

```
ganho = lote.valor_final − lote.base_come_cotas
imposto = ganho × 15% (se ganho > 0)
lote.valor_final    −= imposto
lote.come_cotas_pago += imposto
lote.base_come_cotas  = lote.valor_final
```

No resgate, `tributos.tributar()` reconstrói o ganho **bruto** do período
inteiro (somando de volta o que já foi retido), aplica a alíquota regressiva
final sobre esse bruto, e cobra só a diferença:

```
ganho_bruto = (lote.valor_final − lote.principal) + lote.come_cotas_pago
ir_devido   = ganho_bruto × alíquota_final(lote.dias) / 100
ir_a_pagar  = max(0, ir_devido − lote.come_cotas_pago)
```

Se o prazo passar de 720 dias, a alíquota final também é 15% e `ir_a_pagar`
fecha em ~0 — o come-cotas já cobriu tudo. Prazo menor (ex.: resgate aos 18
meses, alíquota final 17,5%) ainda deve a diferença. Efeito líquido: o
resultado **cai** em relação a "tributar 15% só no fim", porque o imposto sai
mais cedo e reduz a base que compõe juros depois — é isso que fazia o projeto
recusar fundo comum no catálogo antes desta implementação (ver doc 08).

## Dividendo isento x valorização tributável (FII)

Com CDI em 13,90% a.a. e IPCA projetado em 4,443% a.a. (cenário base):

| Caso | Esperado | Confere |
|---|---|---|
| R$ 100, CDB 100% CDI, 12 meses | bruto R$ 113,90 · IR 20% sobre R$ 13,90 = R$ 2,78 · líquido R$ 111,12 | sim |
| R$ 100, LCI 95% CDI, 12 meses | taxa 13,205% · bruto R$ 113,20 · isento · líquido R$ 113,20 | sim |
| R$ 100, CDB 100% CDI, 12 meses, real | R$ 111,12 ÷ 1,04443 = R$ 106,39 | sim |
| R$ 1.000 + R$ 200/mês, CDB 100% CDI, 24 meses | investido R$ 5.800 · bruto R$ 6.809,75 · IR R$ 182,30 (faixas 17,5% a 22,5%) | sim |
| R$ 100, FII sintético (regime `fii`, dividend yield 0%, valorização 1%/mês), 12 meses, projeção ligada | cota: 100 × 1,01¹² = R$ 112,68 · ganho R$ 12,68 · IR 20% = R$ 2,54 · líquido R$ 110,14 · dividendos_isentos R$ 0 | sim |
| R$ 100, VILG11 (FII real), 12 meses, projeção de valorização desligada | dividendos_isentos = Σ DY mensal medido pela CVM (~R$ 7,17 com o DY médio coletado em 2026-09) · sem ganho de capital (cota não se moveu na projeção) · IR R$ 0 · líquido = 100 + dividendos_isentos | sim, refeito em 2026-09-10 |
| R$ 100, fundo sintético 1%/mês (regime `fundo_longo_prazo`, come-cotas ligado), 6 meses (sem cruzar maio/novembro simulado) | igual a não ter come-cotas: bruto R$ 106,15 · IR 22,5% sobre R$ 6,15 = R$ 1,38 · líquido R$ 104,77 | sim |
| Mesmo fundo sintético, 24 meses | come-cotas em 6/12/18 meses (R$ 2,92 retidos no total) · bruto final R$ 123,69 · IR no resgate R$ 1,74 (17,5% do ganho bruto menos o já retido) · líquido R$ 121,95 — **menor** que sem come-cotas (R$ 122,25 líquido), como devia ser | sim |

O segundo caso é o que importa manter estável — não depende de dado coletado,
só da fórmula (ver seção anterior). O terceiro depende do DY vigente do fundo:
o que precisa continuar valendo é `impostos.ir === 0` (cota não valorizou) e
`dividendos_isentos > 0`, não o valor exato em reais.

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
2. **Volatilidade.** Renda variável rende hoje uma linha reta com a taxa do cenário.
   `volatilidade_aa` já está no JSON esperando o Monte Carlo.
3. **Come-cotas por múltiplo fixo de 6 meses, não maio/novembro reais.** Uma posição
   aberta em fevereiro tem seu primeiro come-cotas simulado em agosto, não maio — a
   diferença de meses é pequena o bastante para não mudar a ordem do ranking, mas o
   valor exato de um resgate perto de um desses eventos pode variar um pouco do real.
