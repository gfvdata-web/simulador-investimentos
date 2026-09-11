# 01 — Arquitetura

## Camadas

```
  navegador (web/)                 HTML + CSS + JS puro, sem build
        │  fetch /api/*
        ▼
  backend/app.py                   servidor stdlib, rotas, validação de entrada
        │
        ├── backend/dados.py       carrega JSON, funde com indicadores vivos,
        │        │                 carimba a procedência de cada número
        │        └── backend/fontes/bcb_sgs.py ──> api.bcb.gov.br  (com cache)
        │
        └── backend/engine/        funções puras, sem I/O
                 ├── indexadores.py  "110% do CDI" -> 0,0121 ao mês
                 ├── motor.py        aportes + taxa -> trajetória mês a mês
                 └── tributos.py     trajetória -> IR e IOF devidos
```

Regra de dependência: `engine/` não importa `dados.py` nem `fontes/`. O motor recebe
tudo pronto por parâmetro. Isso mantém o cálculo testável sem rede e sem arquivo.

## Fluxo de uma simulação

1. A página envia `POST /api/simular` com ativos marcados e parâmetros.
2. `app.py` valida entrada e resolve os ids no catálogo.
3. `dados.indicadores()` busca CDI/Selic/IPCA/poupança no BCB (ou usa o cache, ou cai
   no fallback de `premissas.json`) e devolve cada campo com sua origem.
4. Para cada ativo, `indexadores.resolver()` transforma o bloco `rendimento` em uma
   taxa anual efetiva — já descontadas taxas de administração e custódia — mais a
   frase que explica como chegou nela.
5. `motor.projetar()` roda a trajetória mês a mês criando um **lote** por entrada de
   dinheiro (ver doc 03).
6. `tributos.tributar()` aplica IOF e IR lote a lote, porque a tabela regressiva conta
   o prazo de cada aporte separadamente.
7. `motor.comparar()` ordena por valor líquido e anota o ranking.
8. A resposta volta com resultados, parâmetros ecoados, indicadores usados e a
   procedência de cada um.

## Decisões e porquês

**Backend Python em vez de página 100% estática.**
Várias APIs oficiais não mandam cabeçalho CORS, então o navegador não consegue lê-las
direto. O backend também é onde mora o cache — sem ele, cada clique bateria de novo no
Banco Central. Custo: precisa de um comando para subir. Ganho: dado oficial ao vivo.

**Biblioteca padrão, sem FastAPI/Flask.**
`http.server` cobre com folga um servidor local de um usuário. Zero `pip install`
significa que o projeto roda em qualquer máquina com Python e não apodrece por
dependência desatualizada. Se um dia precisar de WebSocket ou auth, reavalie.

**JSON versionado em vez de banco.**
O catálogo é pequeno, muda por edição humana e se beneficia de diff legível no git.
Séries históricas longas vão para o cache, que é descartável. Se o histórico diário de
preços entrar no projeto (fase 3 do roadmap), aí sim vale considerar SQLite — e o
único arquivo a mudar seria `dados.py`.

**Lotes de aporte em vez de uma conta única.**
A tabela regressiva de IR conta o prazo de cada aplicação individualmente. Um aporte
feito no mês 58 de uma simulação de 60 meses paga 22,5%, não 15%. Tratar a posição
como um bolo só superestimaria o líquido de quem aporta todo mês — justamente o caso
de uso mais comum.

**Motor separado da camada fiscal.**
Rentabilidade e tributação mudam por motivos diferentes e em ritmos diferentes: a
primeira por decisão de modelagem, a segunda por mudança de lei. Separadas, uma
reforma tributária mexe em um arquivo só.

**Canvas na mão em vez de biblioteca de gráfico.**
Um gráfico de linhas com eixo e tooltip cabe em ~80 linhas. Uma biblioteca traria CDN
(que a regra 5 proíbe) ou um passo de build. Se o projeto ganhar candlestick ou
histograma, reavalie.

## O que deliberadamente não existe

- **Autenticação e multiusuário.** É um simulador pessoal rodando em `127.0.0.1`.
- **Persistência de simulações.** Cada rodada é efêmera. Salvar cenários está no
  roadmap, fase 4.
- **Simulação estocástica (Monte Carlo).** A v1 projeta retorno determinístico por
  cenário. Volatilidade já está no JSON esperando essa fase.
- **Marcação a mercado de prefixados e IPCA+.** O simulador assume que o título é
  levado ao vencimento. Ver dívidas conhecidas no doc 08.
