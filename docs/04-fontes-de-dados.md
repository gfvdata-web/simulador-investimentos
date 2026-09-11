# 04 — Fontes de dados

Regra do projeto: só fonte oficial, pública e de acesso livre. Sem scraping de
corretora, sem API paga, sem dado atrás de login.

## Em uso hoje

### Banco Central — Sistema Gerenciador de Séries Temporais (SGS)

```
https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json
```

Pública, sem chave, sem limite documentado. Módulo: `coletor/fontes/bcb_sgs.py`.

| Código | Série | Unidade | Uso |
|---|---|---|---|
| 4389 | CDI anualizado, base 252 | % a.a. | indicador de CDI |
| 4391 | CDI acumulado no mês | % a.m. | histórico mensal |
| 432 | Meta Selic do Copom | % a.a. | indicador de Selic |
| 4390 | Selic acumulada no mês | % a.m. | histórico mensal |
| 433 | IPCA, variação mensal | % a.m. | IPCA 12 meses e histórico |
| 196 | Poupança, rendimento (regra nova) | % a.m. | indicador e histórico |
| 226 | TR mensal | % a.m. | reservado |

## Armadilhas já encontradas

Três coisas custaram tempo e estão resolvidas no código. Se mexer no cliente, não
desfaça:

**1. A ordenação não é garantida.** As séries mensais voltam da mais recente para a
mais antiga; as diárias, ao contrário. Sem ordenar, `serie[-1]` pega o ponto mais
*antigo* e o gráfico histórico sai invertido. `bcb_sgs.serie()` ordena por data em
ordem crescente antes de devolver qualquer coisa.

**2. O mês corrente vem parcial.** A série 4391 publica o CDI acumulado do mês em
curso, que no dia 10 vale só um terço do mês. Incluído no histórico, ele desenha uma
queda falsa no último ponto. `dados.historico()` descarta o mês corrente e pede um mês
a mais para compensar.

**3. `/ultimos/N` quebra para N grande.** O endpoint `/dados/ultimos/{n}` responde
400 Bad Request para qualquer N acima de ~12 nas séries mensais (4391, 4390, 433,
196) — não é intermitência, é reprodutível. A consulta por intervalo de datas
(`?dataInicial=dd/MM/aaaa&dataFinal=dd/MM/aaaa`) funciona sem limite prático e é a
que o coletor usa para histórico. `/ultimos/1` continua confiável e é usado para
pegar só o valor mais recente.

Uma quarta, ainda aberta: o IPCA sai por volta do dia 10 do mês seguinte, então o
"IPCA 12 meses" está sempre um a dois meses atrasado em relação ao CDI. Isso é da
natureza do índice, não um bug — mas explica a diferença de data de referência entre
os cartões da página.

## Quando e como a coleta roda

`.github/workflows/atualizar-dados.yml`, às 21h UTC (18h em Brasília) de segunda a
sexta, e sob demanda pelo botão "Run workflow". O coletor grava em `dados/mercado/` e
commita só se algo mudou.

Na mão: `python coletor/atualizar.py --meses 120` (ou `scripts/atualizar-dados.cmd`).

## Degradação em três níveis

O coletor e a página degradam em cadeia, e cada nível é visível na tela:

1. **Coleta ok** — valor do BCB, com série SGS e data de referência.
2. **Fonte falhou, retrato anterior existe** — o campo herda o valor antigo, marcado
   como `"retrato anterior (fonte indisponivel na ultima coleta)"`. O arquivo de série
   anterior é preservado intacto.
3. **Nada disponível** — cai para `indicadores` de `premissas.json`, a página marca
   `_degradado` e mostra aviso amarelo.

Além disso, retrato com mais de 10 dias (`DIAS_ATE_VENCER` em `app/dados.js`) vira
aviso na tela mesmo se estiver completo, porque significa que a automação parou.

Nunca substitua nada disso por um valor padrão silencioso. A regra 1 do `CLAUDE.md`
existe por causa deste ponto: um simulador que mostra número velho sem avisar é pior
que um que não mostra número.

## Fontes mapeadas para as próximas fases

| Fonte | O que traz | Endereço | Situação |
|---|---|---|---|
| Tesouro Transparente | preços e taxas diárias de todos os títulos públicos | `tesourotransparente.gov.br` (CSV/API) | próxima a integrar |
| B3 | cotações e composição de índices | dados públicos da B3 | a avaliar |
| IBGE (SIDRA) | IPCA detalhado por grupo | `servicodados.ibge.gov.br` | a avaliar |
| Coinbase / Kraken | preço de BTC em BRL | APIs públicas de mercado | a avaliar |
| CVM | dados cadastrais e cotas de fundos | dados abertos da CVM | fase de fundos |

## Como plugar uma fonte nova

Uma vantagem do desenho por snapshot: a fonte nova não precisa liberar CORS, porque
quem fala com ela é o Actions, não o navegador.

1. Um módulo por fonte em `coletor/fontes/`, com uma exceção própria (siga o padrão de
   `FalhaFonte`).
2. Normalize para `[{"data": "YYYY-MM-DD", "valor": float}]` ordenado crescente.
3. Grave em `dados/mercado/` no formato do doc 06 e **preserve o arquivo anterior** se
   a coleta falhar.
4. Nunca invente valor quando a fonte falhar: levante a exceção e deixe
   `atualizar.py` decidir a degradação.
5. Documente a série e as armadilhas nas tabelas acima.
