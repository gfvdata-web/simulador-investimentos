# Contrato de trabalho — Simulador de Investimentos

Lido no início de cada sessão, para qualquer prompt futuro cair na estrutura certa sem
reexplicar o projeto.

## O que é

Simulador pessoal para comparar rendimento de investimentos brasileiros num prazo
escolhido. Responde a: *"colocando R$ X hoje (e talvez R$ Y por mês), quanto eu tenho
em N meses em cada opção que eu marcar?"*

Não é corretora, não recomenda, não executa ordem. Site estático publicado no GitHub
Pages; os dados são um retrato versionado no repositório, coletado pelo Actions.

## As seis regras que não se quebram

1. **Nenhum número inventado.** Todo valor na tela é (a) fato de fonte oficial,
   (b) parâmetro contratado do próprio ativo, ou (c) estimativa explícita de
   `premissas.json`. O que o simulador não sabe fica vazio e a tela diz que está vazio
   — nunca um chute plausível. Na prática: indicador ausente faz `resolver()` lançar
   erro e o ativo aparece na lista de erros. Não "conserte" isso com um valor padrão.
2. **A procedência viaja com o número.** Cada indicador carrega fonte, referência da
   série e data. A página mostra isso e avisa quando o dado é herdado, é fallback ou
   está velho. Nunca remova esse rastro para "limpar" a saída.
3. **Fato e estimativa nunca se misturam.** CDI é fato; retorno do Bitcoin é palpite.
   Nunca no mesmo campo de JSON, nunca com o mesmo peso visual. O selo âmbar
   "estimado" sai de `taxa.natureza` — mantenha-o em qualquer redesenho.
4. **Só fontes oficiais, públicas e de uso livre.** Banco Central, Tesouro
   Transparente, IBGE, dados públicos da B3 e da CVM. Nada de scraping de corretora,
   nada de API paga, nada atrás de login.
5. **Zero dependências.** Coletor usa só a stdlib do Python; a página é HTML/CSS/JS
   puro, sem build e sem CDN. Precisa de dependência? Discuta antes.
6. **A página nunca acessa a rede.** Só o coletor fala com fontes externas, fora do
   navegador. Se algo na página parecer precisar de `fetch` para fora do repositório,
   a resposta certa é ensinar o coletor a trazer aquele dado.

## Onde mexer para cada tarefa

| Você quer… | Mexa só em | Observação |
|---|---|---|
| Adicionar um ativo | `dados/catalogo/ativos.json` | nenhuma linha de código, se o tipo de rendimento já existir |
| Mudar um palpite de retorno | `dados/premissas/premissas.json` | precisa de `fonte` preenchida |
| Indicador ou série nova de uma fonte já existente | registros `INDICADORES` / `SERIES` em `coletor/atualizar.py` | a página se monta sozinha a partir do retrato — não há lista de indicadores no JS |
| Fonte de dados nova | novo módulo em `coletor/fontes/` + registro em `FONTES` | siga `PROTOCOLO_FONTE`; atualize `docs/04` |
| Novo tipo de rendimento (ex.: `cdi_mais`) | `app/nucleo/indexadores.js` | some em `scripts/validar.py` e `docs/02` |
| Nova regra fiscal | `app/nucleo/tributos.js` | tabelas vão em `premissas.json`, não no código; `docs/05` |
| Mexer na interface | `index.html`, `app/estilo.css`, `app/app.js` | núcleo e coletor ficam intactos; `docs/07` |
| Mudar formato de arquivo de dados | coletor **e** `app/dados.js` **e** `docs/06` | mesmo commit: são duas pontas de um contrato |

A regra por trás da tabela: **adicionar nunca deve exigir editar mais de um lugar.** Se
uma adição estiver pedindo mudança em três arquivos, o desenho está errado — conserte o
desenho, não repita o dado.

## Convenções de código

- **Português** em nome de função, variável, chave de JSON, comentário e commit. Mesmo
  idioma do domínio (aporte, rendimento, líquido, resgate).
- Python em `snake_case`, JavaScript em `camelCase`, chaves de JSON em `snake_case`,
  ids de ativo em `kebab-case` (`tesouro-ipca-2035`).
- Taxas entram e saem em **% ao ano** nas fronteiras (JSON, tela). A conversão para
  fração mensal acontece só dentro do núcleo, via `indexadores.aaParaAm`.
- Dinheiro em `float`, arredondado só na saída. Precisão de centavo não muda uma
  projeção de 5 anos.
- `app/nucleo/` é **puro**: recebe objetos, devolve objetos, não lê arquivo nem faz
  rede. Só `app/dados.js` e `coletor/` tocam I/O.
- Código Python sem acento em identificador e comentário (CI roda com locale
  imprevisível). **Exceção:** `rotulo` e outros textos que aparecem na tela levam
  acentuação normal — são dados UTF-8, não código.
- Todo texto vindo de arquivo de dados passa por `escapar()` antes de virar HTML.

## Como entregar

```bash
python -m http.server 8765     # a página usa módulos ES: file:// não funciona
python scripts/validar.py      # antes de qualquer commit que toque em dados/
```

- Uma frente por vez: catálogo, núcleo, coletor e página evoluem independentes.
- Toda mudança no núcleo reconfere a tabela de casos do `docs/03`. Se um número mudar,
  descubra se você achou um bug antigo ou criou um novo **antes** de atualizar a tabela.
- Tipo, regime ou classe nova: acrescente também em `scripts/validar.py`, senão o
  validador passa a reprovar o catálogo (ele faz checagem cruzada com o código).
- Não rode o coletor só para "atualizar" — cada execução vira commit de dados. Rode
  quando estiver mexendo em fonte, ou deixe o Actions fazer.

## Estado atual

v0.2.0 — estático, publicado, sem backend. Ver `docs/08-roadmap.md` para o que vem em
seguida e `docs/00-catalogo.md` para o índice da documentação.

Duas decisões que já foram revertidas uma vez — não as refaça sem motivo novo:

- **Backend Python consultando a fonte a cada clique** (v0.1). Removido: o BCB libera
  CORS, então ele não resolvia o problema que o justificava, e o Pages só serve
  estático. Está no histórico do git.
- **Listas de indicadores escritas à mão no JS.** Removidas: um indicador novo exigia
  editar cinco arquivos. Hoje o retrato é autodescrito (rótulo, unidade, fonte) e a
  página se monta a partir dele.
