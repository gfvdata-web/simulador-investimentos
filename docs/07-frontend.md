# 07 — Página do simulador

`index.html` na raiz mais três arquivos em `app/`, sem build, sem framework, sem CDN.
Um servidor estático qualquer serve o repositório, então editar e recarregar já basta.
O cálculo roda no navegador, em `app/nucleo/` (doc 06).

| Arquivo | Papel |
|---|---|
| `index.html` (raiz) | estrutura e ids — nenhum texto de resultado é escrito aqui. Os controles da simulação (formulário de aporte, prazo, cenário, opções, botão) ficam no `<header>`; a coluna esquerda do `<main>` tem o card de ativos (catálogo, só consulta) |
| `app/estilo.css` | tokens de tema e todos os componentes |
| `app/app.js` | estado, render da tabela, gráfico e alternador de tema |
| `app/dados.js` | leitura dos JSON do repositório e procedência dos indicadores |

## Estado

Um objeto só, no topo de `app.js`:

```js
const estado = {
  ativos: [],                // catálogo cru de dados/catalogo/ativos.json
  carteira: [],               // { id, ativoId, nome, valorInicial, aporteMensal } — aportes oficializados
  proximoIdCarteira: 1,
  modoVisualizacao: 'individual', // 'individual' | 'somado', controla só o gráfico
  ultimaSimulacao: null,      // última saída montada em simular()
  serieHistorica: null,       // última série carregada de dados/mercado/series/
  premissas: null,
  indicadores: null,          // já com procedência e idade do retrato
};
```

Sem framework e sem reatividade: cada função de render recebe os dados e reescreve o
`innerHTML` da sua região. Para um punhado de linhas e um gráfico, isso é mais simples
de seguir do que qualquer camada de binding.

## Carteira: múltiplos ativos, cada um com seu próprio aporte

A simulação não compara ativos com um valor/aporte compartilhado — cada item da
carteira carrega seu próprio `valorInicial`/`aporteMensal`, e só prazo, cenário e as
três chaves de IR/inflação/valorização são premissas globais da simulação inteira.

Fluxo de uso: marcar um ativo na lista à esquerda (rádio de seleção única,
`name="ativo-escolhido"` — só um pode estar marcado por vez, e é ele quem dita o que
"+ Adicionar à carteira" vai usar), preencher valor inicial e/ou aporte mensal, clicar o
botão (`adicionarAoCarteira()`). Isso empilha um item em `estado.carteira` e resimula. O
card "Carteira" (`renderizarCarteira()`), fixado ao lado do gráfico via `.area-projecao`,
lista cada item com um botão de remover — remover também resimula.

`estado.ativoEscolhido` é a única fonte de verdade de "qual ativo está prestes a ser
adicionado" — `escolherAtivo(id)` marca o rádio certo (mesmo se a mudança veio de outro
lugar) e atualiza o resuminho no cabeçalho (`#ativo-escolhido-nome`). Não existe mais
seletor `<select>` duplicando essa escolha.

O mesmo ativo pode entrar mais de uma vez na carteira, com aportes diferentes; `simular()`
desambigua o nome com um sufixo `(#2)`, `(#3)` quando isso acontece.

`simular()` chama `motor.projetar()` uma vez por item da carteira (não usa mais
`motor.comparar()`), passando os parâmetros globais mais o valor/aporte daquele item.
A tabela de resultados ganha uma linha extra em negrito com o total da carteira quando
há mais de um item.

## Individual vs. somado

O toggle `#modo-visualizacao` (dois estados, só aparece com 2+ itens na carteira) afeta
só o gráfico:

- **Individual** (padrão): uma linha por item da carteira, cor de `PALETA` por índice.
- **Somado**: duas linhas — a soma mês a mês do bruto de todos os itens
  (`somarSeries()`) e a soma do investido, tracejada. Como todos os itens compartilham o
  mesmo prazo global, as séries sempre têm o mesmo comprimento e somam ponto a ponto sem
  ajuste.

## Controles da simulação

`#considerar-ir`, `#considerar-inflacao` e `#considerar-valorizacao` (a mais nova: liga
a projeção de valorização patrimonial de FII, ver docs 02 e 03) seguem o mesmo padrão —
checkbox lido direto em `simular()`, re-simula em `change`. Novo parâmetro booleano
global segue os mesmos três passos: campo em `index.html`, leitura em `simular()`, id na
lista de `ligarControles()`. `#valor-inicial` e `#aporte-mensal` **não** entram nessa
lista — são campos de estagiamento, só lidos por `adicionarAoCarteira()` no clique do
botão, não disparam simulação sozinhos.

## Convenções de interface

**Ativos agrupados por classe, cada grupo colapsável — e a lista É o seletor.** Cada
classe é um `<details open>` com `<summary>` e uma contagem estática de itens do grupo.
Cada ativo é um `<label class="ativo">` com um rádio dentro (`.ativo:has(input:checked)`
pinta a linha inteira, não só o rádio). Marcar um ativo não o adiciona à carteira sozinho
— só o deixa pronto no formulário de aporte, acima, até o clique em "+ Adicionar à
carteira". Abrir/fechar o grupo é só o comportamento nativo do `<details>`, sem JS.

**Toda estimativa é marcada.** Ativo cujo `rendimento.tipo` está em
`TIPOS_NAO_CONTRATADOS` (`estimado`, `fundo_fii`, `etf_historico`) ganha o selo âmbar
"estimado" na lista. Isso implementa a regra 3 do `CLAUDE.md` na camada visual — não
remova ao redesenhar, e acrescente um tipo novo nesse `Set` se ele não for uma taxa
contratada.

**Dividendo isento tem coluna própria.** A tabela de resultados tem uma coluna
"Dividendos" com `resultado.dividendos_isentos` (só FII preenche; o resto mostra "—").
O valor já está embutido em "Bruto", "Líquido" e "Valor real" — a coluna só existe pra
não esconder que uma parte do retorno já chegou como dividendo isento, sem esperar o
resgate. O resumo em texto acima da tabela também soma o total de dividendos da carteira
quando há algum.

**Todo número explica de onde veio.** Cada linha da tabela tem, logo abaixo, uma linha
em cinza com `taxa.explicacao`, `impostos.detalhe` e o efeito da inflação. O painel "de
onde vem cada número" mostra série do SGS e data de referência de cada indicador.

**Fonte monoespaçada em número, proporcional em texto.** Facilita comparar colunas de
valores. Classe `.num` nas células numéricas.

**Cores são semânticas, não decorativas.** Verde é ganho, vermelho é imposto ou perda,
âmbar é aviso ou estimativa. A paleta de séries (`PALETA`) é só identidade de linha.

## Tema

Tokens em `:root` no tema claro; o bloco `@media (prefers-color-scheme: dark)` redefine
os mesmos tokens quando o sistema prefere escuro. Nenhuma cor é definida apenas dentro
do bloco escuro — se for adicionar, defina no claro primeiro.

Três estados para o atributo `data-tema` em `<html>`:

| `data-tema` | Efeito |
|---|---|
| ausente | segue `prefers-color-scheme` do sistema (padrão) |
| `"claro"` | força claro mesmo com o sistema em escuro |
| `"escuro"` | força escuro mesmo com o sistema em claro (bloco `:root[data-tema="escuro"]`, fora da media query) |

O botão `#alterna-tema` no cabeçalho alterna entre claro/escuro e persiste a escolha em
`localStorage` (`simulador-investimentos:tema`). Um script inline no `<head>` de
`index.html` aplica o tema salvo antes do primeiro paint, para não piscar no tema
errado ao carregar. Se o usuário nunca clicou no botão, a página continua acompanhando
o `prefers-color-scheme` do sistema ao vivo (listener em `ligarTema()`).

O gráfico lê as cores de borda e texto via `getComputedStyle` no momento do desenho,
então ele acompanha o tema sem código extra — `aplicarTema()` só precisa redesenhar o
canvas existente quando o tema muda, não recalcular nada.

## Gráfico

`desenharLinhas(canvas, series, opcoes)` em ~70 linhas de canvas 2d.

```js
desenharLinhas($('#grafico'), [
  { nome: 'CDB 100% do CDI', cor: '#1f6feb', valores: [100, 101.09, ...] },
  { nome: 'Total investido', cor: 'var(--texto-tenue)', tracejada: true, valores: [...] },
], { rotuloX: (i) => `mês ${i}` });
```

- Escala Y automática com 8% de folga, começando em zero quando os valores são baixos.
- Rótulos de dados: o valor final de cada série é escrito na margem direita, com a cor
  da linha. Quando dois rótulos ficariam sobrepostos, são empurrados verticalmente
  (mínimo de 13 px entre eles). Some com `opcoes.rotularPontas === false` ou acima de
  10 séries; a margem direita cresce para abrir espaço quando ligado.
- `devicePixelRatio` aplicado no `setTransform`, senão a linha sai borrada em tela HiDPI.
- Rótulos das pontas ancorados para dentro (`textAlign` muda no primeiro e no último),
  senão vazam para fora da área do gráfico.
- Cor pode ser um token CSS (`var(--x)`): é resolvida na hora de desenhar.
- O estado do gráfico fica em `canvas._grafico`, o que permite redesenhar no hover e no
  resize sem refazer a requisição.

A linha tracejada "Total investido" é o que dá sentido à altura das outras: sem ela,
uma curva subindo não diz quanto é rendimento e quanto é dinheiro novo aportado.

## Abas

Duas: **Projeção** (o simulador) e **Histórico real (BCB)**, que mostra o que o
indicador de fato fez nos últimos 60 meses. O histórico só é carregado quando a aba é
aberta pela primeira vez.

## Ideias mapeadas

- Exportar o comparativo em CSV.
- Guardar a última configuração em `localStorage`.
- Escala logarítmica no gráfico para prazos longos.
- Marcar no gráfico o mês em que a alíquota de IR cai de faixa.
- Linha de inflação acumulada como referência visual de "empatar com o IPCA".
