# 08 — Roadmap

As fases são independentes de propósito: dados, motor, fontes e página podem avançar em
prompts paralelos sem colidir, desde que os contratos dos docs 02 e 06 sejam respeitados.

## Fase 0 — Esqueleto ✅ concluída

Estrutura, documentação, backend com motor completo, página funcional, CDI ao vivo.

## Fase 1 — Catálogo de verdade

Sair dos 10 ativos-semente para algo que reflita o que você realmente considera.

- Cadastrar os ativos que você de fato usa ou avalia.
- Integrar o **Tesouro Transparente** para puxar taxa real de cada título público em vez
  do valor fixo no catálogo — hoje `tesouro-prefixado-2029` diz 12,50% porque alguém
  digitou isso.
- Preço de BTC em BRL por API pública de mercado.
- Campo de vencimento nos títulos, com o prazo da simulação limitado por ele.

*Toca em:* `dados/catalogo/`, `backend/fontes/`. Não mexe no motor.

## Fase 2 — Fidelidade do cálculo

- **Come-cotas** em fundos (doc 05 tem o desenho da implementação).
- **Marcação a mercado** de prefixados e IPCA+ para resgate antes do vencimento.
- Calendário real em vez de mês comercial de 30 dias no IR.
- Carência e liquidez afetando o resgate: hoje `liquidez` é texto decorativo.
- Aporte com periodicidade diferente de mensal.

*Toca em:* `backend/engine/`. Reconfira a tabela de casos do doc 03 a cada mudança.

## Fase 3 — Histórico como simulação

Hoje o histórico é uma aba separada. A ideia é responder *"e se eu tivesse investido
R$ 100 em janeiro de 2020?"* rodando o motor sobre as séries reais em vez de uma taxa
constante.

- Backtest com série real do BCB mês a mês.
- Comparar projeção contra realizado no mesmo gráfico.
- Séries diárias de preço para renda variável (aqui pode valer SQLite — ver doc 01).

*Toca em:* `backend/engine/motor.py` (aceitar vetor de taxas), `backend/dados.py`.

## Fase 4 — Carteira

- Simular combinação de ativos com pesos, não só um contra o outro.
- Rebalanceamento periódico.
- Salvar e recarregar cenários.
- Aporte distribuído por percentual entre ativos.

## Fase 5 — Incerteza

- Monte Carlo usando `volatilidade_aa`, que já está no JSON sem uso.
- Faixa de confiança no gráfico em vez de linha única para ativos estimados.
- Correlação entre ativos (a essa altura, provavelmente vale aceitar numpy — discuta
  antes, a regra 5 do `CLAUDE.md` proíbe dependência sem conversa).

## Dívidas conhecidas

| Dívida | Impacto | Onde |
|---|---|---|
| Come-cotas não modelado | fundo renderia mais do que renderia de verdade | `tributos.py` |
| Sem marcação a mercado | prefixado e IPCA+ só fazem sentido até o vencimento | `motor.py` |
| Mês comercial de 30 dias | casos de fronteira de IR podem cair na faixa errada | `motor.py` |
| Isenção mensal assume venda única | ações e cripto podem ficar mais isentos na prática | `tributos.py` |
| `liquidez` e `fgc` são decorativos | não afetam nada no cálculo | `ativos.json` |
| Sem testes automatizados | a tabela do doc 03 é conferida à mão | — |
| Taxa de prefixado fixa no JSON | envelhece sem avisar | `ativos.json`, fase 1 |

## Como escolher a próxima tarefa

Pergunte primeiro: *isso muda a resposta de "onde coloco R$ 100 hoje"?* Se a resposta
for não, provavelmente é polimento e pode esperar.

Pelo peso sobre a fidelidade dos números, a ordem mais útil é: integrar o Tesouro
Transparente (fase 1), depois come-cotas (fase 2), depois backtest (fase 3).
