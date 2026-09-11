# Contrato de trabalho — Simulador de Investimentos

Este arquivo é lido no início de cada sessão. Ele existe para que qualquer prompt
futuro (página, consultas, novos ativos) caia na estrutura certa sem precisar
reexplicar o projeto.

## O que este projeto é

Um simulador local e pessoal para comparar rendimento de investimentos brasileiros
ao longo de um prazo escolhido. Responde à pergunta: *"colocando R$ X hoje (e talvez
R$ Y por mês), quanto eu tenho em N meses em cada uma das opções que eu marcar?"*

Não é uma corretora, não é um robô de recomendação, não executa ordens.

## As cinco regras que não se quebram

1. **Nenhum número inventado.** Todo valor que chega à tela é (a) um fato buscado em
   fonte oficial, (b) um parâmetro contratado do próprio ativo, ou (c) uma estimativa
   explícita de `dados/premissas/premissas.json`. Se o modelo não sabe, o campo fica
   vazio e a tela diz que está vazio — nunca um chute plausível.
2. **A procedência viaja com o número.** Toda resposta da API carrega de onde veio cada
   indicador (série do SGS, data de referência, ou "fallback local"). A página mostra
   isso. Nunca remova esse rastro para "limpar" a saída.
3. **Fato e estimativa nunca se misturam no mesmo campo.** CDI é fato. Retorno do
   Bitcoin é palpite. Os dois nunca aparecem com o mesmo peso visual nem na mesma
   chave de JSON.
4. **Só fontes oficiais, públicas e de uso livre.** Banco Central (SGS), Tesouro
   Transparente, dados públicos da B3, IBGE. Nada de scraping de site de corretora,
   nada de API paga, nada de dado atrás de login.
5. **Zero dependências de runtime.** Backend usa só a biblioteca padrão do Python;
   o front é HTML/CSS/JS puro, sem build e sem CDN. Se uma tarefa parece exigir uma
   dependência, discuta antes de adicionar.

## Convenções de código

- **Português** em nomes de função, variável, chave de JSON, comentário e commit.
  Mantém tudo no mesmo idioma do domínio (aporte, rendimento, líquido, resgate).
- Arquivos e identificadores em `snake_case`; ids de ativo em `kebab-case`
  (`tesouro-ipca-2035`).
- Taxas entram e saem em **% ao ano** nas fronteiras (JSON, API, tela). A conversão
  para fração mensal acontece só dentro do motor, via `indexadores.aa_para_am`.
- Dinheiro em `float` com arredondamento só na saída. Nada de `Decimal` por ora — a
  precisão de centavo não muda uma projeção de 5 anos, e simplicidade vale mais aqui.
- Funções do motor são **puras**: recebem dicionários, devolvem dicionários, não leem
  arquivo nem fazem rede. Só `backend/dados.py` e `backend/fontes/` tocam I/O.

## Onde mexer para cada tipo de tarefa

| Você quer… | Mexa em | Não precisa tocar |
|---|---|---|
| Adicionar um ativo | `dados/catalogo/ativos.json` | código nenhum, se o tipo de rendimento já existir |
| Mudar um palpite de retorno | `dados/premissas/premissas.json` | — |
| Novo tipo de rendimento (ex.: `cdi_mais`) | `backend/engine/indexadores.py` + `docs/02` | motor, tributos |
| Nova regra fiscal | `backend/engine/tributos.py` + `docs/05` | motor |
| Nova fonte de dados | `backend/fontes/` (um módulo por fonte) + `docs/04` | motor |
| Novo endpoint | `backend/app.py` + `docs/06` | — |
| Mexer na página | `web/` + `docs/07` | backend |

## Como entregar

- Uma frente por vez: dados, motor, API e página evoluem independentes de propósito.
- Toda mudança no motor precisa de um caso conferido à mão no comentário ou no teste
  (ex.: "R$ 100 a 100% do CDI de 13,90% por 12 meses = R$ 113,90 bruto; IR de 20% sobre
  R$ 13,90 = R$ 2,78; líquido R$ 111,12").
- Mudou contrato de API? Atualize `docs/06-api.md` no mesmo commit.
- Adicionou ativo com retorno estimado? A estimativa precisa de `fonte` preenchida.

## Estado atual

v0.1.0 — preview funcional. Ver `docs/08-roadmap.md` para o que vem em seguida e
`docs/00-catalogo.md` para o índice da documentação.
