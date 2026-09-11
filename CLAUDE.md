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
5. **Zero dependências.** O coletor usa só a biblioteca padrão do Python; a página é
   HTML/CSS/JS puro, sem build e sem CDN. Se uma tarefa parece exigir uma dependência,
   discuta antes de adicionar.
6. **A página nunca acessa a rede.** Só o coletor fala com fontes externas, e ele roda
   fora do navegador. Se algo na página precisar de `fetch` para fora do repositório,
   a resposta certa é ensinar o coletor a trazer aquele dado.

## Convenções de código

- **Português** em nomes de função, variável, chave de JSON, comentário e commit.
  Mantém tudo no mesmo idioma do domínio (aporte, rendimento, líquido, resgate).
- Arquivos e identificadores em `snake_case`; ids de ativo em `kebab-case`
  (`tesouro-ipca-2035`).
- Taxas entram e saem em **% ao ano** nas fronteiras (JSON, tela). A conversão para
  fração mensal acontece só dentro do motor, via `indexadores.aaParaAm`.
- Dinheiro em `float` com arredondamento só na saída. A precisão de centavo não muda
  uma projeção de 5 anos, e simplicidade vale mais aqui.
- Funções de `app/nucleo/` são **puras**: recebem objetos, devolvem objetos, não leem
  arquivo nem fazem rede. Só `app/dados.js` e `coletor/` tocam I/O.
- Python no coletor fica sem acento no código-fonte (roda em ambiente de CI com locale
  imprevisível); JavaScript e documentação usam português com acento normal.

## Onde mexer para cada tipo de tarefa

| Você quer… | Mexa em | Não precisa tocar |
|---|---|---|
| Adicionar um ativo | `dados/catalogo/ativos.json` | código nenhum, se o tipo de rendimento já existir |
| Mudar um palpite de retorno | `dados/premissas/premissas.json` | — |
| Novo tipo de rendimento (ex.: `cdi_mais`) | `app/nucleo/indexadores.js` + `docs/02` | motor, tributos |
| Nova regra fiscal | `app/nucleo/tributos.js` + `docs/05` | motor |
| Nova fonte de dados | `coletor/fontes/` (um módulo por fonte) + `docs/04` e `docs/06` | a página |
| Mudar formato de arquivo de dados | coletor + `app/dados.js` + `docs/06`, no mesmo commit | — |
| Mexer na interface | `index.html`, `app/estilo.css`, `app/app.js` + `docs/07` | núcleo, coletor |

## Como entregar

- Uma frente por vez: dados, motor, API e página evoluem independentes de propósito.
- Toda mudança no motor precisa de um caso conferido à mão no comentário ou no teste
  (ex.: "R$ 100 a 100% do CDI de 13,90% por 12 meses = R$ 113,90 bruto; IR de 20% sobre
  R$ 13,90 = R$ 2,78; líquido R$ 111,12").
- Mudou o formato de um arquivo de dados? Atualize `docs/06-contratos.md`, o coletor e
  a página no mesmo commit — são duas pontas que só conversam por aquele contrato.
- Adicionou ativo com retorno estimado? A estimativa precisa de `fonte` preenchida.

## Estado atual

v0.2.0 — publicado no GitHub Pages, sem backend. O site é estático e os dados são um
retrato versionado, atualizado pelo Actions. Ver `docs/08-roadmap.md` para o que vem em
seguida e `docs/00-catalogo.md` para o índice da documentação.

A v0.1 tinha um backend Python que consultava o BCB a cada clique. Ele foi removido
quando ficou claro que (a) o BCB libera CORS, então ele não resolvia o problema que
justificava sua existência, e (b) o Pages só serve estático. Está no histórico do git
se algum dia fizer falta.
