# 07 — Página do simulador

`index.html` na raiz mais três arquivos em `app/`, sem build, sem framework, sem CDN.
Um servidor estático qualquer serve o repositório, então editar e recarregar já basta.
O cálculo roda no navegador, em `app/nucleo/` (doc 06).

| Arquivo | Papel |
|---|---|
| `index.html` (raiz) | estrutura e ids — nenhum texto de resultado é escrito aqui. Os controles da simulação (valor, aporte, prazo, cenário, opções, botão) ficam no `<header>`; a coluna esquerda do `<main>` tem só o card de ativos |
| `app/estilo.css` | tokens de tema e todos os componentes |
| `app/app.js` | estado, render da tabela, gráfico e alternador de tema |
| `app/dados.js` | leitura dos JSON do repositório e procedência dos indicadores |

## Estado

Um objeto só, no topo de `app.js`:

```js
const estado = {
  ativos: [],               // catálogo cru de dados/catalogo/ativos.json
  selecionados: new Set(),  // ids marcados
  ultimaSimulacao: null,    // última saída de motor.comparar()
  serieHistorica: null,     // última série carregada de dados/mercado/series/
  premissas: null,
  indicadores: null,        // já com procedência e idade do retrato
};
```

Sem framework e sem reatividade: cada função de render recebe os dados e reescreve o
`innerHTML` da sua região. Para um punhado de linhas e um gráfico, isso é mais simples
de seguir do que qualquer camada de binding.

## Fluxo

1. `iniciar()` liga os controles, carrega indicadores e catálogo em paralelo, e dispara
   uma simulação inicial com o ativo padrão — a página nunca abre vazia.
2. Mudar qualquer campo re-simula automaticamente, mas só se já houve uma simulação
   antes (`estado.ultimaSimulacao`). Evita render duplicado enquanto a página carrega.
   Marcar/desmarcar um ativo também re-simula, com debounce de 250 ms
   (`agendarSimulacao()`), então o gráfico ganha e perde linhas na hora, sem clicar em
   "Simular".
3. `renderizarResultados()` escreve o resumo em uma frase, a tabela, o gráfico e o
   painel de procedência.

## Convenções de interface

**Ativos agrupados por classe, cada grupo colapsável.** Cada classe é um `<details open>`
com `<summary>`; o contador `marcados/total` no canto direito é atualizado por
`atualizarContagem()`. Abrir/fechar é só o comportamento nativo do `<details>`, sem JS.

**Toda estimativa é marcada.** Ativo com `rendimento.tipo === 'estimado'` ganha o selo
âmbar "estimado" na lista. Isso implementa a regra 3 do `CLAUDE.md` na camada visual —
não remova ao redesenhar.

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
