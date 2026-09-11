# 04 — Fontes de dados

Regra do projeto: só fonte oficial, pública e de acesso livre. Sem scraping de
corretora, sem API paga, sem dado atrás de login.

## Em uso hoje

### Banco Central — Sistema Gerenciador de Séries Temporais (SGS)

```
https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json
```

Pública, sem chave, sem limite documentado. Módulo: `backend/fontes/bcb_sgs.py`.

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

Duas coisas custaram tempo e estão resolvidas no código. Se mexer no cliente, não
desfaça:

**1. A ordenação não é garantida.** As séries mensais voltam da mais recente para a
mais antiga; as diárias, ao contrário. Sem ordenar, `serie[-1]` pega o ponto mais
*antigo* e o gráfico histórico sai invertido. `bcb_sgs.serie()` ordena por data em
ordem crescente antes de devolver qualquer coisa.

**2. O mês corrente vem parcial.** A série 4391 publica o CDI acumulado do mês em
curso, que no dia 10 vale só um terço do mês. Incluído no histórico, ele desenha uma
queda falsa no último ponto. `dados.historico()` descarta o mês corrente e pede um mês
a mais para compensar.

Uma terceira, ainda aberta: o IPCA sai por volta do dia 10 do mês seguinte, então o
"IPCA 12 meses" está sempre um a dois meses atrasado em relação ao CDI. Isso é da
natureza do índice, não um bug — mas explica a diferença de data de referência entre
os cartões da página.

## Cache

`backend/fontes/cache.py`. Um arquivo JSON por consulta em `dados/cache/`, com TTL
padrão de 6 horas. A pasta é descartável e está no `.gitignore` — apagar força uma
releitura.

Para forçar atualização sem apagar nada: `GET /api/indicadores?atualizar=1`.

## Como o fallback funciona

`dados.indicadores()` tenta cada campo separadamente. Se um falhar, aquele campo — e
só ele — cai para `premissas.json`, marcado com `origem: "fallback de premissas.json"`.
A resposta ganha `_degradado: true` e a página mostra um aviso amarelo.

Nunca substitua isso por um valor padrão silencioso. A regra 1 do `CLAUDE.md` existe
por causa deste ponto exato: um simulador que mostra número velho sem avisar é pior que
um que não mostra número.

## Fontes mapeadas para as próximas fases

| Fonte | O que traz | Endereço | Situação |
|---|---|---|---|
| Tesouro Transparente | preços e taxas diárias de todos os títulos públicos | `tesourotransparente.gov.br` (CSV/API) | próxima a integrar |
| B3 | cotações e composição de índices | dados públicos da B3 | a avaliar |
| IBGE (SIDRA) | IPCA detalhado por grupo | `servicodados.ibge.gov.br` | a avaliar |
| Coinbase / Kraken | preço de BTC em BRL | APIs públicas de mercado | a avaliar |
| CVM | dados cadastrais e cotas de fundos | dados abertos da CVM | fase de fundos |

## Como plugar uma fonte nova

1. Um módulo por fonte em `backend/fontes/`, com uma exceção própria (siga o padrão de
   `FalhaFonte`).
2. Normalize para `[{"data": "YYYY-MM-DD", "valor": float}]` ordenado crescente.
3. Passe tudo por `cache.ler` / `cache.gravar` com um TTL adequado ao ritmo da série.
4. Nunca invente valor quando a fonte falhar: levante a exceção e deixe `dados.py`
   decidir o fallback.
5. Documente a série e as armadilhas nas tabelas acima.
