# 01 — Arquitetura

## A ideia em uma frase

O site é estático e nunca acessa a internet. Um coletor separado busca os dados
oficiais de tempos em tempos e **commita o resultado no repositório**; a página lê
esses arquivos e faz todo o cálculo no navegador.

```
  GitHub Actions (agendado, dias úteis 18h BRT)
        │
        ▼
  coletor/atualizar.py ──> api.bcb.gov.br
        │
        ▼  git commit
  dados/mercado/indicadores.json
  dados/mercado/series/*.json
        │
        ▼  (arquivos estáticos, servidos pelo Pages)
  navegador
    ├── app/dados.js      lê os JSON do repositório, carimba a procedência
    └── app/nucleo/       funções puras, sem I/O
          ├── indexadores.js  "110% do CDI" -> 0,0121 ao mês
          ├── motor.js        aportes + taxa -> trajetória mês a mês
          └── tributos.js     trajetória -> IR e IOF devidos
```

Regra de dependência: `app/nucleo/` não importa `dados.js`. O motor recebe tudo por
parâmetro — o que o mantém testável e faz dele o único lugar onde mora o cálculo.

## Por que snapshot em vez de consulta ao vivo

A primeira versão tinha um backend Python que consultava o Banco Central a cada
clique. Duas descobertas mudaram o desenho:

1. A API do BCB devolve `Access-Control-Allow-Origin: *`, então o backend não era
   necessário para contornar CORS — que era a justificativa dele existir.
2. O GitHub Pages só serve arquivo estático. Consulta ao vivo do navegador
   funcionaria, mas amarraria o site à disponibilidade da fonte **naquele instante**.

O snapshot versionado é melhor em quatro pontos concretos:

- **Funciona com a fonte fora do ar.** O último retrato bom continua no repositório.
- **É auditável.** O histórico do git mostra exatamente qual CDI o simulador usou em
  qualquer data passada. Em uma ferramenta que projeta dinheiro, isso importa.
- **Não depende de CORS.** Fontes futuras que não liberam o cabeçalho entram sem
  mudar nada na página — o coletor roda no Actions, onde CORS não existe.
- **É rápido e previsível.** A página carrega quatro arquivos do mesmo domínio.

O custo é que o dado tem idade. Ela é tratada como cidadã de primeira classe: viaja
junto com cada número, aparece no cabeçalho ("dados coletados hoje") e vira aviso
amarelo quando passa de `DIAS_ATE_VENCER` (10 dias) em `app/dados.js`.

## Fluxo de uma simulação

1. A página lê `dados/catalogo/ativos.json`, `dados/premissas/premissas.json` e
   `dados/mercado/indicadores.json`.
2. `dados.indicadores()` monta os indicadores com a origem de cada campo; campo
   ausente cai para o fallback de `premissas.json` e marca `_degradado`.
3. Para cada ativo marcado, `indexadores.resolver()` transforma o bloco `rendimento`
   em taxa anual efetiva — já sem taxas de administração e custódia — mais a frase
   que explica como chegou nela.
4. `motor.projetar()` roda a trajetória mês a mês criando um **lote** por entrada de
   dinheiro (ver doc 03).
5. `tributos.tributar()` aplica IOF e IR lote a lote, porque a tabela regressiva conta
   o prazo de cada aporte separadamente.
6. `motor.comparar()` ordena por valor líquido e anota o ranking.

Tudo isso é síncrono e roda em milissegundos: não há rede no caminho.

## Decisões e porquês

**Coletor em Python, página em JavaScript.** São dois trabalhos diferentes: buscar e
normalizar dado de fonte oficial (offline, agendado, com retry) versus calcular e
desenhar (no navegador, instantâneo). Não há duplicação de lógica entre eles — o
coletor não sabe calcular rendimento, e a página não sabe falar com o BCB.

**Biblioteca padrão no coletor, zero dependências na página.** Nenhum `pip install`,
nenhum `npm install`, nenhum CDN. O projeto roda em qualquer máquina com Python e
qualquer navegador, e não apodrece por dependência desatualizada.

**Módulos ES nativos.** Sem bundler e sem passo de build: editar e recarregar basta.
Em troca, abrir `index.html` por `file://` não funciona — precisa de um servidor
estático, mesmo local (`scripts/iniciar.cmd`).

**JSON versionado em vez de banco.** O catálogo é pequeno, muda por edição humana e se
beneficia de diff legível. As séries mensais somam ~120 pontos cada. Se um dia entrar
histórico diário de preços de ações, aí vale reconsiderar — e o único arquivo a mudar
seria `app/dados.js`.

**Lotes de aporte em vez de uma conta única.** A tabela regressiva de IR conta o prazo
de cada aplicação individualmente. Um aporte feito no mês 58 de uma simulação de 60
meses paga 22,5%, não 15%. Tratar a posição como um bolo só superestimaria o líquido
de quem aporta todo mês — justamente o caso de uso mais comum.

**Motor separado da camada fiscal.** Rentabilidade e tributação mudam por motivos
diferentes e em ritmos diferentes: a primeira por decisão de modelagem, a segunda por
mudança de lei. Separadas, uma reforma tributária mexe em um arquivo só.

**Canvas na mão em vez de biblioteca de gráfico.** Um gráfico de linhas com eixo,
rótulos de ponta e tooltip cabe em ~120 linhas. Uma biblioteca traria CDN ou build.

## O que deliberadamente não existe

- **Backend.** Foi removido na v0.2 — o histórico do git tem a versão com ele.
- **Autenticação.** O site é público e não recebe dado de ninguém.
- **Persistência de simulações.** Cada rodada é efêmera. Só a escolha de tema é
  lembrada, em `localStorage`.
- **Simulação estocástica (Monte Carlo).** A v1 projeta retorno determinístico por
  cenário. `volatilidade_aa` já está no JSON esperando essa fase.
- **Marcação a mercado de prefixados e IPCA+.** O simulador assume que o título é
  levado ao vencimento. Ver dívidas conhecidas no doc 08.
