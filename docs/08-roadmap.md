# 08 — Roadmap

As fases são independentes de propósito: dados, motor, fontes e página podem avançar em
prompts paralelos sem colidir, desde que os contratos dos docs 02 e 06 sejam respeitados.

## Fase 0 — Esqueleto ✅ concluída

Estrutura, documentação, motor completo, página funcional, dados do BCB.

## Fase 0.5 — Site estático publicado ✅ concluída

Backend removido, motor portado para o navegador, coletor rodando no GitHub Actions,
dados de mercado versionados, publicação no GitHub Pages.

## Fase 1 — Catálogo de verdade

Sair dos 10 ativos-semente para algo que reflita o que você realmente considera.

- ✅ **FII e ETF cadastrados** (2026-09): 8 FIIs (VILG11, ALZR11, BTLG11, GGRC11, RECR11,
  HGLG11, XPLG11, KNCR11) via CVM (Informe Mensal), 5 ETFs (DIVO11, GOLD11, WRLD11,
  XINA11, NASD11) via B3 (COTAHIST). Novo tipo de rendimento (`fundo_fii`,
  `etf_historico`), novo regime tributário (`fii`, dividendo isento separado de ganho
  de capital) — ver docs 02, 03, 04, 05.
- ✅ **BDR cadastrado** (2026-09): 8 BDRs de ações americanas (MSFT34, MELI34, AMZO34,
  TSLA34, M2ST34, S2EA34, NFLX34, NVDC34) via B3 (COTAHIST) — mesma fonte do ETF, regime
  `acoes` (isenção de R$20.000/mês, diferente de ETF).
- ✅ **Fundo comum sem ticker cadastrado** (2026-09): 8 fundos Itaú — 5 de ações
  (ITUSTECH, ITVALE, ITUNIBCO, ITELEBRAS, ITSABESP, regime `fundo_acoes`) e 3
  multimercado (ITGDPLUS, ITGOLDMM, ITMODMM, regime `fundo_longo_prazo`, com
  come-cotas). Nova fonte (`coletor/fontes/cvm_fi.py`, informe diário de FI da CVM) e
  novo tipo de rendimento (`fundo_cvm_historico`) — ver docs 02, 04.
- Cadastrar os demais ativos que você de fato usa ou avalia.
- Integrar o **Tesouro Transparente** para puxar taxa real de cada título público em vez
  do valor fixo no catálogo — hoje `tesouro-prefixado-2029` diz 12,50% porque alguém
  digitou isso.
- Preço de BTC em BRL por API pública de mercado.
- Campo de vencimento nos títulos, com o prazo da simulação limitado por ele.

*Toca em:* `dados/catalogo/`, `coletor/fontes/`. Não mexe no motor nem na página.

## Fase 2 — Fidelidade do cálculo

- ✅ **Come-cotas** em fundos (2026-09): regime `fundo_longo_prazo` completo, semestral
  a 15%, creditado contra a tabela regressiva no resgate — ver docs 03 e 05.
- **Marcação a mercado** de prefixados e IPCA+ para resgate antes do vencimento.
- Calendário real em vez de mês comercial de 30 dias no IR.
- Carência e liquidez afetando o resgate: hoje `liquidez` é texto decorativo.
- Aporte com periodicidade diferente de mensal.

*Toca em:* `app/nucleo/`. Reconfira a tabela de casos do doc 03 a cada mudança.

## Fase 3 — Histórico como simulação

Hoje o histórico é uma aba separada. A ideia é responder *"e se eu tivesse investido
R$ 100 em janeiro de 2020?"* rodando o motor sobre as séries reais em vez de uma taxa
constante.

- Backtest com série real do BCB mês a mês.
- Comparar projeção contra realizado no mesmo gráfico.
- Séries diárias de preço para renda variável (aqui pode valer SQLite — ver doc 01).

*Toca em:* `app/nucleo/motor.js` (aceitar vetor de taxas), `app/dados.js`.

## Fase 4 — Carteira

- ✅ **Múltiplos aportes na mesma simulação** (2026-09): cada item da carteira tem seu
  próprio valor inicial e aporte mensal; prazo/cenário/IR/inflação continuam globais.
  Visualização individual (uma linha por item) ou somada (uma linha com o total da
  carteira). Ver docs 07.
- Rebalanceamento periódico.
- Salvar e recarregar cenários (a carteira hoje vive só em memória, some ao recarregar
  a página).
- Aporte distribuído por percentual entre ativos, em vez de valor fixo por item.

## Fase 5 — Incerteza

- Monte Carlo usando `volatilidade_aa`, que já está no JSON sem uso.
- Faixa de confiança no gráfico em vez de linha única para ativos estimados.
- Correlação entre ativos (a essa altura, provavelmente vale aceitar numpy — discuta
  antes, a regra 5 do `CLAUDE.md` proíbe dependência sem conversa).

## Dívidas conhecidas

| Dívida | Impacto | Onde |
|---|---|---|
| Sem marcação a mercado | prefixado e IPCA+ só fazem sentido até o vencimento | `motor.js` |
| Mês comercial de 30 dias (IR e come-cotas) | casos de fronteira podem cair na faixa/evento errado; come-cotas simulado por múltiplo de 6 meses, não maio/novembro reais | `motor.js` |
| Isenção mensal assume venda única | ações, BDR e cripto podem ficar mais isentos na prática | `tributos.js` |
| `liquidez` e `fgc` são decorativos | não afetam nada no cálculo | `ativos.json` |
| Sem testes automatizados | a tabela do doc 03 é conferida à mão | — |
| Taxa de prefixado fixa no JSON | envelhece sem avisar | `ativos.json`, fase 1 |
| Resumo de fundo é média simples, não ponderada | mês com PL pequeno pesa igual a mês com PL grande | `coletor/atualizar.py`, `_resumo_fii`/`_resumo_precos` |
| ETF/BDR/fundo comum não separam distribuição de preço | se distribuir provento, ou está embutido no preço/cota ou não é capturado | `b3_precos.py`, `cvm_fi.py`, doc 05 |
| Sem aba de histórico por fundo | `pontos` de cada fundo é coletado mas só o `resumo` é usado hoje | `app/app.js` |
| Come-cotas não compensa prejuízo | se o fundo cair de valor depois de reter come-cotas, o valor retido não é devolvido no cálculo (a lei permite compensar contra ganho futuro no mesmo fundo, não modelado) | `tributos.js` |

*Nota sobre as linhas de fundos:* adicionadas em 2026-09 junto do cadastro de FII, ETF,
BDR e fundo comum.

## Como escolher a próxima tarefa

Pergunte primeiro: *isso muda a resposta de "onde coloco R$ 100 hoje"?* Se a resposta
for não, provavelmente é polimento e pode esperar.

Pelo peso sobre a fidelidade dos números, a ordem mais útil é: integrar o Tesouro
Transparente (fase 1), depois come-cotas (fase 2), depois backtest (fase 3).
