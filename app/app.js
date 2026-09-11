/* Simulador de Investimentos — front-end.
   Sem frameworks e sem dependências externas. O cálculo roda no navegador
   (app/nucleo/) e os dados vêm dos arquivos versionados em dados/, coletados
   periodicamente pelo coletor Python. A página nunca acessa a rede. */

import * as dados from './dados.js';
import * as motor from './nucleo/motor.js';

const PALETA = ['#1f6feb', '#e2506b', '#1a9e6a', '#d98324', '#8250df', '#0aa2c0', '#b8860b', '#5c6670'];

const estado = {
  ativos: [],
  ativoEscolhido: null, // id marcado na lista à esquerda — o que "+ Adicionar à carteira" usa
  carteira: [],       // { id, ativoId, nome, valorInicial, aporteMensal } — cada item é um aporte oficializado
  proximoIdCarteira: 1,
  modoVisualizacao: 'individual', // 'individual' | 'somado'
  ultimaSimulacao: null,
  historico: null,
  premissas: null,
  indicadores: null,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

/* ---------------------------------------------------------- formatadores */
const moeda = (v) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const moedaCurta = (v) => {
  const abs = Math.abs(v);
  if (abs >= 1e6) return 'R$ ' + (v / 1e6).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + 'M';
  if (abs >= 1e3) return 'R$ ' + (v / 1e3).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + 'k';
  return 'R$ ' + v.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
};
/** Formata segundo a unidade que o coletor declarou. Nem todo indicador é
    percentual: preço de ativo chega como "R$", e taxa como "% a.a.". */
const MOEDAS = ['R$', 'US$', 'EUR', '€', '$'];
const valorComUnidade = (valor, unidade = '') => {
  if (unidade.startsWith('%')) return pct(valor) + unidade.slice(1).trimEnd();
  const moeda = MOEDAS.find((m) => unidade.startsWith(m));
  if (moeda) {
    const resto = unidade.slice(moeda.length).trim();
    const numero = valor.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return `${moeda} ${numero}${resto ? ' ' + resto : ''}`;
  }
  const numero = valor.toLocaleString('pt-BR', { maximumFractionDigits: 4 });
  return unidade ? `${numero} ${unidade}` : numero;
};
const pct = (v) => v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '%';
const dataBR = (iso) => {
  if (!iso) return '';
  const [a, m, d] = iso.split('-');
  return d ? `${d}/${m}/${a}` : `${m}/${a}`;
};
const textoIdade = (dias) => {
  if (dias === null || dias === undefined) return '';
  if (dias <= 0) return 'hoje';
  if (dias === 1) return 'ontem';
  return `há ${dias} dias`;
};
const abreviarFonte = (nome) => String(nome).split(' - ')[0].replace('Banco Central do Brasil', 'BCB');
const escapar = (t) => String(t).replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/* ---------------------------------------------------------- indicadores */
async function carregarIndicadores() {
  try {
    const ind = await dados.indicadores();
    estado.indicadores = ind;
    // Nada de lista fixa: os cartões saem do próprio retrato, com o rótulo
    // e a unidade que o coletor gravou. Indicador novo aparece sozinho.
    $('#indicadores').innerHTML = Object.entries(ind._meta).map(([chave, m]) => {
      const procedencia = m.origem === 'fallback de premissas.json'
        ? 'fallback local'
        : `${abreviarFonte(m.origem)} · ${dataBR(m.referencia)}`;
      return `<li${m.heranca ? ' class="herdado" title="' + escapar(m.heranca) + '"' : ''}>
        <span class="rotulo">${escapar(m.rotulo)}</span>
        <div class="valor">${valorComUnidade(ind[chave], m.unidade)}</div>
        <span class="fonte">${escapar(procedencia)}</span></li>`;
    }).join('');

    const avisos = [];
    if (ind._degradado) {
      avisos.push(`Alguns indicadores não estavam no retrato de mercado; o simulador está usando os
        valores de <code>premissas.json</code> como reserva.`);
    }
    if (ind._vencido) {
      avisos.push(`O retrato de mercado foi coletado há ${ind._idade_dias} dias. O coletor deveria rodar
        todo dia útil — vale conferir se a automação está de pé.`);
    }
    $('#aviso-degradado').innerHTML = avisos.length
      ? `<div class="aviso">${avisos.join('<br>')}</div>` : '';

    $('#idade-dados').textContent = ind._coletado_em
      ? `dados coletados ${textoIdade(ind._idade_dias)}` : '';
  } catch (erro) {
    $('#indicadores').innerHTML = `<li><span class="rotulo">Indicadores</span><div class="valor">—</div>
      <span class="fonte">${escapar(erro.message)}</span></li>`;
  }
}

/* ---------------------------------------------------------- catálogo */
const NOMES_CLASSE = {
  renda_fixa: 'Renda fixa',
  renda_variavel: 'Renda variável',
  cripto: 'Cripto',
  fundos: 'Fundos',
};

// Mesmo critério que a página usa pra decidir "isso é fato ou palpite?" (regra
// 3 do CLAUDE.md), só que aqui de antemão, a partir do catálogo cru - antes de
// rodar o núcleo e saber a `natureza` de verdade.
const TIPOS_NAO_CONTRATADOS = new Set(['estimado', 'fundo_fii', 'etf_historico']);

async function carregarAtivos() {
  const catalogo = await dados.catalogo();
  estado.ativos = catalogo.ativos;

  const porClasse = {};
  for (const ativo of catalogo.ativos) (porClasse[ativo.classe] ||= []).push(ativo);

  $('#lista-ativos').innerHTML = Object.entries(porClasse).map(([classe, itens]) => `
    <details class="grupo" open>
      <summary>
        ${NOMES_CLASSE[classe] || classe}
        <span class="cont-grupo">${itens.length}</span>
      </summary>
      <div class="grupo-corpo">
        ${itens.map((a) => `
          <label class="ativo" title="${escapar(a.descricao)}">
            <input type="radio" name="ativo-escolhido" value="${a.id}">
            <span>
              <span class="nome">${escapar(a.nome)}</span>
              ${TIPOS_NAO_CONTRATADOS.has(a.rendimento.tipo) ? '<span class="selo estimado">estimado</span>' : ''}
              ${a.tributacao.regime === 'isento' ? '<span class="selo isento">isento de IR</span>' : ''}
              <div class="meta">${rotuloRendimento(a)} · risco ${a.risco}/6</div>
            </span>
          </label>`).join('')}
      </div>
    </details>
  `).join('');

  $$('#lista-ativos input[name="ativo-escolhido"]').forEach((radio) => radio.addEventListener('change', () => {
    if (radio.checked) escolherAtivo(radio.value);
  }));

  $('#contagem-ativos').textContent = `(${catalogo.ativos.length} disponíveis)`;

  // Página nunca abre sem um ativo pronto pra aportar: o padrão (ou o
  // primeiro do catálogo, se ele não existir) já vem marcado.
  const padrao = estado.ativos.find((a) => a.id === 'cdb-100-cdi') || estado.ativos[0];
  if (padrao) escolherAtivo(padrao.id);
}

/** Marca o rádio correspondente na lista e atualiza o resumo no formulário de
    aporte — única fonte de verdade de "qual ativo estou prestes a adicionar". */
function escolherAtivo(ativoId) {
  const ativo = estado.ativos.find((a) => a.id === ativoId);
  if (!ativo) return;
  estado.ativoEscolhido = ativoId;
  const radio = $(`#lista-ativos input[value="${CSS.escape(ativoId)}"]`);
  if (radio) radio.checked = true;
  $('#ativo-escolhido-nome').textContent = ativo.nome;
}

function rotuloRendimento(a) {
  const r = a.rendimento;
  switch (r.tipo) {
    case 'pos_cdi': return `${r.percentual_cdi}% do CDI`;
    case 'pos_selic': return r.spread_aa ? `Selic + ${r.spread_aa}%` : 'Selic';
    case 'prefixado': return `${r.taxa_aa}% a.a. prefixado`;
    case 'ipca_mais': return `IPCA + ${r.spread_aa}%`;
    case 'poupanca': return 'Regra da poupança';
    case 'estimado': return 'Retorno estimado';
    case 'fundo_fii': return 'Dividend yield (fato) + valorização opcional';
    case 'etf_historico': return 'Retorno estimado (histórico de preço)';
    default: return r.tipo;
  }
}

/* ---------------------------------------------------------- carteira */
function adicionarAoCarteira() {
  const ativoId = estado.ativoEscolhido;
  const ativo = estado.ativos.find((a) => a.id === ativoId);
  const avisoEl = $('#aviso-adicionar');
  if (!ativo) {
    avisoEl.textContent = 'Escolha um ativo na lista à esquerda.';
    return;
  }
  const valorInicial = Number($('#valor-inicial').value) || 0;
  const aporteMensal = Number($('#aporte-mensal').value) || 0;
  if (valorInicial <= 0 && aporteMensal <= 0) {
    avisoEl.textContent = 'Informe um valor inicial ou aporte mensal maior que zero.';
    return;
  }
  avisoEl.textContent = '';
  estado.carteira.push({
    id: 'c' + estado.proximoIdCarteira++,
    ativoId,
    nome: ativo.nome,
    valorInicial,
    aporteMensal,
  });
  renderizarCarteira();
  simular();
  if (!$('#aba-historico').hidden || estado.historico) carregarHistoricoCarteira();
}

function renderizarCarteira() {
  const lista = $('#lista-carteira');
  const vazio = $('#carteira-vazia');
  const modo = $('#modo-visualizacao');
  if (!estado.carteira.length) {
    lista.innerHTML = '';
    vazio.hidden = false;
    modo.hidden = true;
    return;
  }
  vazio.hidden = true;
  modo.hidden = estado.carteira.length < 2;

  lista.innerHTML = estado.carteira.map((c, i) => {
    const partes = [];
    if (c.valorInicial > 0) partes.push(`${moeda(c.valorInicial)} inicial`);
    if (c.aporteMensal > 0) partes.push(`${moeda(c.aporteMensal)}/mês`);
    return `
      <li>
        <span class="pastilha" style="background:${PALETA[i % PALETA.length]}"></span>
        <span class="item-corpo">
          <span class="nome">${escapar(c.nome)}</span>
          <span class="meta">${escapar(partes.join(' + '))}</span>
        </span>
        <button type="button" class="remover-item" data-id="${c.id}" aria-label="Remover ${escapar(c.nome)} da carteira">×</button>
      </li>`;
  }).join('');

  $$('#lista-carteira .remover-item').forEach((botao) => botao.addEventListener('click', () => {
    estado.carteira = estado.carteira.filter((c) => c.id !== botao.dataset.id);
    renderizarCarteira();
    simular();
    if (!$('#aba-historico').hidden || estado.historico) carregarHistoricoCarteira();
  }));
}

/* ---------------------------------------------------------- simulação */
let timerSimulacao;

/** Marcar vários ativos em sequência dispara um render só. */
function agendarSimulacao(atraso = 250) {
  clearTimeout(timerSimulacao);
  timerSimulacao = setTimeout(simular, atraso);
}

async function simular() {
  if (!estado.carteira.length) {
    $('#resumo').innerHTML = '<p class="vazio">Adicione ao menos um ativo à carteira usando o formulário acima.</p>';
    $('#grafico-caixa').hidden = true;
    $('#painel-detalhe').hidden = true;
    return;
  }
  const botao = $('#simular');
  botao.disabled = true;
  botao.textContent = 'Simulando…';

  try {
    // Prazo, cenário e as três chaves de IR/inflação/valorização são premissas
    // da simulação inteira; valor inicial e aporte mensal são por item da
    // carteira (cada um oficializado com o botão "Adicionar à carteira").
    const parametrosBase = {
      meses: Number($('#meses').value) || 12,
      cenario: $('#cenario').value,
      considerar_ir: $('#considerar-ir').checked,
      considerar_inflacao: $('#considerar-inflacao').checked,
      considerar_valorizacao_projetada: $('#considerar-valorizacao').checked,
    };

    const [premissas, indicadores, porId] = await Promise.all([
      dados.premissas(), estado.indicadores ? estado.indicadores : dados.indicadores(), dados.ativosPorId(),
    ]);
    estado.indicadores = indicadores;
    estado.premissas = premissas;

    const itens = estado.carteira.map((c) => ({ ...c, ativo: porId[c.ativoId] })).filter((it) => it.ativo);
    // Só busca o histórico dos FII/ETF de fato presentes na carteira - a página
    // não baixa os 13 arquivos de fundo pra simular 2 CDBs.
    const tickersFundo = [...new Set(itens
      .filter((it) => it.ativo.rendimento.tipo === 'fundo_fii' || it.ativo.rendimento.tipo === 'etf_historico')
      .map((it) => it.ativo.rendimento.ticker))];
    const fundos = tickersFundo.length ? await dados.fundos(tickersFundo) : {};

    // Item repetido (mesmo ativo, aportes diferentes) precisa de um rótulo que
    // distinga as linhas na tabela e na legenda do gráfico.
    const ocorrenciasTotal = {};
    for (const it of itens) ocorrenciasTotal[it.ativoId] = (ocorrenciasTotal[it.ativoId] || 0) + 1;
    const ocorrencia = {};

    const resultados = [];
    const erros = [];
    for (const item of itens) {
      const parametros = {
        ...parametrosBase,
        valor_inicial: item.valorInicial,
        aporte_mensal: item.aporteMensal,
      };
      try {
        const r = motor.projetar(item.ativo, indicadores, premissas, parametros, fundos);
        ocorrencia[item.ativoId] = (ocorrencia[item.ativoId] || 0) + 1;
        if (ocorrenciasTotal[item.ativoId] > 1) r.nome = `${r.nome} (#${ocorrencia[item.ativoId]})`;
        r.item_id = item.id;
        resultados.push(r);
      } catch (erro) {
        erros.push({ ativo_id: item.nome, erro: erro.message });
      }
    }
    resultados.sort((a, b) => b.liquido - a.liquido);

    const saida = { resultados, erros, parametros: parametrosBase, indicadores };

    estado.ultimaSimulacao = saida;
    renderizarResultados(saida);
  } catch (erro) {
    $('#resumo').innerHTML = `<div class="aviso">${escapar(erro.message)}</div>`;
  } finally {
    botao.disabled = false;
    botao.textContent = 'Simular';
  }
}

function renderizarResultados(saida) {
  const { resultados, parametros, erros } = saida;
  if (!resultados.length) {
    $('#resumo').innerHTML = '<p class="vazio">Nenhum resultado.</p>';
    $('#grafico-caixa').hidden = true;
    return;
  }
  const mostrarReal = parametros.considerar_inflacao;
  const mostrarIR = parametros.considerar_ir;

  const cabecalho = `
    <tr>
      <th>Ativo</th><th>Taxa efetiva</th><th>Investido</th><th>Bruto</th>
      <th title="Dividendo isento de IR recebido no período — já somado ao Bruto e ao Valor real, mostrado à parte para você acompanhar o que o fundo de fato pagou.">Dividendos</th>
      ${mostrarIR ? '<th>IR + IOF</th>' : ''}
      <th>Líquido</th>
      ${mostrarReal ? '<th>Valor real</th>' : ''}
      <th>Ganho líq.</th><th>Rent. líq.</th>
    </tr>`;
  const colunas = 7 + (mostrarIR ? 1 : 0) + (mostrarReal ? 1 : 0) + 1;

  const linhas = resultados.map((r, i) => {
    const cor = PALETA[i % PALETA.length];
    const ganho = r.rendimento_liquido;
    const sinal = ganho >= 0 ? 'positivo' : 'negativo';
    return `
      <tr class="tem-explicacao">
        <td><span class="pastilha" style="background:${cor}"></span>${escapar(r.nome)}</td>
        <td class="num">${pct(r.taxa.taxa_aa)} a.a.</td>
        <td class="num">${moeda(r.investido)}</td>
        <td class="num">${moeda(r.bruto)}</td>
        <td class="num positivo">${r.dividendos_isentos ? moeda(r.dividendos_isentos) : '—'}</td>
        ${mostrarIR ? `<td class="num negativo">${r.impostos.total ? '−' + moeda(r.impostos.total) : '—'}</td>` : ''}
        <td class="num destaque">${moeda(r.liquido)}</td>
        ${mostrarReal ? `<td class="num">${moeda(r.liquido_real)}</td>` : ''}
        <td class="num ${sinal}">${ganho >= 0 ? '+' : ''}${moeda(ganho)}</td>
        <td class="num ${sinal} destaque">${pct(r.rentabilidade_liquida_pct)}</td>
      </tr>
      <tr class="linha-explicacao">
        <td colspan="${colunas}">${escapar(r.taxa.explicacao)}. ${escapar(r.impostos.detalhe)}.
        ${mostrarReal ? `Descontando IPCA projetado de ${pct(r.inflacao.ipca_aa_projetado)} a.a., sobra ${pct(r.rentabilidade_real_pct)} de ganho real.` : ''}</td>
      </tr>`;
  }).join('');

  const totalInvestido = resultados.reduce((s, r) => s + r.investido, 0);
  const totalBruto = resultados.reduce((s, r) => s + r.bruto, 0);
  const totalDividendos = resultados.reduce((s, r) => s + r.dividendos_isentos, 0);
  const totalImpostos = resultados.reduce((s, r) => s + r.impostos.total, 0);
  const totalLiquido = resultados.reduce((s, r) => s + r.liquido, 0);
  const totalLiquidoReal = resultados.reduce((s, r) => s + r.liquido_real, 0);
  const totalGanho = totalLiquido - totalInvestido;
  const sinalTotal = totalGanho >= 0 ? 'positivo' : 'negativo';
  const rentTotalLiquida = totalInvestido > 0 ? (totalLiquido / totalInvestido - 1) * 100 : 0;
  const linhaTotal = resultados.length > 1 ? `
    <tr class="linha-total">
      <td>Total da carteira</td>
      <td class="num">—</td>
      <td class="num">${moeda(totalInvestido)}</td>
      <td class="num">${moeda(totalBruto)}</td>
      <td class="num positivo">${totalDividendos ? moeda(totalDividendos) : '—'}</td>
      ${mostrarIR ? `<td class="num negativo">${totalImpostos ? '−' + moeda(totalImpostos) : '—'}</td>` : ''}
      <td class="num">${moeda(totalLiquido)}</td>
      ${mostrarReal ? `<td class="num">${moeda(totalLiquidoReal)}</td>` : ''}
      <td class="num ${sinalTotal}">${totalGanho >= 0 ? '+' : ''}${moeda(totalGanho)}</td>
      <td class="num ${sinalTotal}">${pct(rentTotalLiquida)}</td>
    </tr>` : '';

  const melhor = resultados[0];
  const prazoTexto = parametros.meses === 1 ? '1 mês' : `${parametros.meses} meses`;
  const nAtivos = resultados.length;
  const avisoErros = erros.length
    ? `<div class="aviso">${erros.map((e) => `${escapar(e.ativo_id)}: ${escapar(e.erro)}`).join('<br>')}</div>`
    : '';

  $('#resumo').innerHTML = `
    ${avisoErros}
    <p style="margin:0 0 14px;color:var(--texto-fraco)">
      ${moeda(totalInvestido)} investidos em ${nAtivos} aporte${nAtivos > 1 ? 's' : ''} ao longo de
      <strong>${prazoTexto}</strong>.
      Melhor posição individual: <strong style="color:var(--texto)">${escapar(melhor.nome)}</strong>
      com ${moeda(melhor.liquido)}${mostrarReal ? ` (${moeda(melhor.liquido_real)} em poder de compra de hoje)` : ''}.
      ${totalDividendos ? ` Dos quais ${moeda(totalDividendos)} vieram de dividendo isento de FII, já embutido no bruto e no líquido.` : ''}
    </p>
    <div class="tabela-envolucro"><table><thead>${cabecalho}</thead><tbody>${linhas}${linhaTotal}</tbody></table></div>`;

  $('#grafico-caixa').hidden = false;
  const series = estado.modoVisualizacao === 'somado' && resultados.length > 1
    ? [
      {
        nome: 'Total da carteira',
        cor: PALETA[0],
        valores: somarSeries(resultados.map((r) => r.serie.map((p) => p.bruto))),
      },
      {
        nome: 'Total investido',
        cor: 'var(--texto-tenue)',
        tracejada: true,
        valores: somarSeries(resultados.map((r) => r.serie.map((p) => p.investido))),
      },
    ]
    : resultados.map((r, i) => ({
      nome: r.nome,
      cor: PALETA[i % PALETA.length],
      valores: r.serie.map((p) => p.bruto),
    }));
  desenharLinhas($('#grafico'), series, { rotuloX: (i) => `mês ${i}` });

  $('#legenda').innerHTML = series.map((s) =>
    `<span><i class="pastilha" style="background:${s.cor}"></i>${escapar(s.nome)}</span>`).join('');

  renderizarDetalhe(saida);
}

/** Soma, mês a mês, várias séries do mesmo prazo — usada no modo "Somado". */
function somarSeries(arrs) {
  const n = Math.max(...arrs.map((a) => a.length));
  const total = new Array(n).fill(0);
  for (const arr of arrs) arr.forEach((v, i) => { total[i] += v; });
  return total;
}

function renderizarDetalhe(saida) {
  const ind = saida.indicadores;
  const linhas = Object.entries(ind._meta).map(([chave, m]) => `
    <tr>
      <td>${escapar(m.rotulo)}</td>
      <td class="num">${valorComUnidade(ind[chave], m.unidade)}</td>
      <td>${escapar(m.heranca || m.origem)}${m.referencia_fonte ? ` · série ${m.referencia_fonte}` : ''}</td>
      <td>${dataBR(m.referencia)}</td>
    </tr>`).join('');

  $('#painel-detalhe').hidden = false;
  $('#detalhe').innerHTML = `
    <div class="tabela-envolucro"><table>
      <thead><tr><th>Indicador</th><th>Valor</th><th>Fonte</th><th>Referência</th></tr></thead>
      <tbody>${linhas}</tbody>
    </table></div>
    <p class="rodape-nota">Prazos de IR usam mês comercial de 30 dias. Cada aporte mensal é tratado como um
    lote próprio, então na tabela regressiva os aportes mais recentes pagam alíquota maior.</p>`;
}

/* ---------------------------------------------------------- histórico */
// Ativo sem série própria de mercado usa o índice que contrata: CDI, Selic,
// IPCA ou poupança. Prefixado e estimado não têm série real — regra 1 do
// CLAUDE.md proíbe inventar um histórico pra eles, então ficam de fora com aviso.
const INDEXADOR_DA_SERIE = { pos_cdi: 'cdi', pos_selic: 'selic', ipca_mais: 'ipca', poupanca: 'poupanca' };
const MESES_HISTORICO = 12;

/** Monta, por ativo da carteira, a série real dos últimos 12 meses: preço/
    valorização + dividendo pra FII/ETF, ou o indexador contratado pro resto.
    Reage à carteira igual o gráfico de projeção — nada de seletor à parte. */
async function carregarHistoricoCarteira() {
  const caixa = $('#grafico-historico-caixa');
  if (!estado.carteira.length) {
    caixa.hidden = true;
    $('#resumo-historico').innerHTML =
      '<p class="vazio">Adicione um ativo à carteira para ver o histórico real dele aqui.</p>';
    estado.historico = null;
    return;
  }

  $('#resumo-historico').innerHTML = '<p class="vazio">carregando histórico…</p>';
  const porId = await dados.ativosPorId();
  // Um ativo só aparece uma vez no gráfico, mesmo se tiver mais de um aporte.
  const ativos = [...new Set(estado.carteira.map((c) => c.ativoId))]
    .map((id) => porId[id]).filter(Boolean);

  const tickers = [...new Set(ativos
    .filter((a) => a.rendimento.tipo === 'fundo_fii' || a.rendimento.tipo === 'etf_historico')
    .map((a) => a.rendimento.ticker))];
  const fundos = tickers.length ? await dados.fundos(tickers) : {};

  const mesAtual = new Date().toISOString().slice(0, 7);
  const series = [];
  const cards = [];
  const semHistorico = [];

  for (let i = 0; i < ativos.length; i++) {
    const ativo = ativos[i];
    const cor = PALETA[i % PALETA.length];
    const tipo = ativo.rendimento.tipo;

    if (tipo === 'fundo_fii' || tipo === 'etf_historico') {
      const arquivo = fundos[ativo.rendimento.ticker];
      if (!arquivo) { semHistorico.push(`${ativo.nome} (sem arquivo coletado ainda)`); continue; }
      const pontos = arquivo.pontos.filter((p) => p.data.slice(0, 7) !== mesAtual).slice(-MESES_HISTORICO);
      if (!pontos.length) { semHistorico.push(`${ativo.nome} (sem meses fechados)`); continue; }
      let fator = 1;
      const acumulado = pontos.map((p) => {
        fator *= 1 + p.rentabilidade_efetiva_pct / 100;
        return { ...p, indice_100: Math.round(fator * 1e6) / 1e4 };
      });
      series.push({ nome: ativo.nome, cor, valores: acumulado.map((p) => p.indice_100), datas: acumulado.map((p) => p.data) });
      const somaDy = acumulado.reduce((s, p) => s + p.dividend_yield_pct, 0);
      const ultimo = acumulado[acumulado.length - 1];
      cards.push(`
        <li><span class="pastilha" style="background:${cor}"></span>
          <strong>${escapar(ativo.nome)}</strong>
          — rentabilidade efetiva acumulada em ${acumulado.length} meses:
          <strong>${pct(Math.round((fator - 1) * 1e6) / 1e4)}</strong>.
          Dividend yield pago no período: ${pct(Math.round(somaDy * 1e4) / 1e4)}
          (último mês, ${dataBR(ultimo.data)}: ${pct(ultimo.dividend_yield_pct)}).
          Fonte: ${escapar(arquivo.fonte)}.
        </li>`);
    } else if (tipo in INDEXADOR_DA_SERIE) {
      let hist;
      try {
        hist = await dados.historico(INDEXADOR_DA_SERIE[tipo], MESES_HISTORICO);
      } catch (erro) { semHistorico.push(`${ativo.nome} (${erro.message})`); continue; }
      series.push({ nome: `${ativo.nome} (via ${hist.rotulo_curto || hist.rotulo})`, cor,
        valores: hist.pontos.map((p) => p.indice_100), datas: hist.pontos.map((p) => p.data) });
      const ultimo = hist.pontos[hist.pontos.length - 1];
      cards.push(`
        <li><span class="pastilha" style="background:${cor}"></span>
          <strong>${escapar(ativo.nome)}</strong>
          — segue ${escapar(hist.rotulo)}, acumulado em ${hist.pontos.length} meses:
          <strong>${pct(hist.acumulado_total_pct)}</strong> (até ${dataBR(ultimo.data)}).
          Fonte: ${escapar(hist.fonte)}${hist.referencia_fonte ? `, série ${hist.referencia_fonte}` : ''}.
        </li>`);
    } else {
      semHistorico.push(`${ativo.nome} (taxa ${tipo === 'prefixado' ? 'prefixada' : 'estimada'}, sem série de mercado própria)`);
    }
  }

  estado.historico = { series };
  caixa.hidden = !series.length;
  const avisoSemHistorico = semHistorico.length
    ? `<div class="aviso">Sem histórico real pra mostrar: ${semHistorico.map(escapar).join('; ')}.</div>` : '';
  $('#resumo-historico').innerHTML = avisoSemHistorico +
    (cards.length ? `<ul class="lista-resumo-historico">${cards.join('')}</ul>` : '');

  if (series.length) {
    const n = Math.max(...series.map((s) => s.valores.length));
    desenharLinhas($('#grafico-historico'), series,
      { rotuloX: (i) => dataBR(series.find((s) => s.datas.length === n)?.datas[i] || series[0].datas[Math.min(i, series[0].datas.length - 1)]) });
    $('#legenda-historico').innerHTML = series.map((s) =>
      `<span><i class="pastilha" style="background:${s.cor}"></i>${escapar(s.nome)}</span>`).join('');
  }
}

/* ---------------------------------------------------------- gráfico */
function desenharLinhas(canvas, series, opcoes = {}) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const largura = canvas.clientWidth;
  const altura = canvas.clientHeight;
  canvas.width = largura * dpr;
  canvas.height = altura * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);

  const estilo = getComputedStyle(document.body);
  const corBorda = estilo.getPropertyValue('--borda').trim();
  const corTexto = estilo.getPropertyValue('--texto-tenue').trim();

  const rotularPontas = opcoes.rotularPontas !== false && series.length <= 10;
  const margem = { topo: 12, direita: rotularPontas ? 76 : 12, baixo: 26, esquerda: 62 };
  const w = largura - margem.esquerda - margem.direita;
  const h = altura - margem.topo - margem.baixo;
  const n = Math.max(...series.map((s) => s.valores.length));

  const todos = series.flatMap((s) => s.valores);
  let min = Math.min(...todos);
  let max = Math.max(...todos);
  if (min === max) { min -= 1; max += 1; }
  const folga = (max - min) * 0.08;
  min = Math.max(0, min - folga);
  max += folga;

  const px = (i) => margem.esquerda + (n > 1 ? (i / (n - 1)) * w : w / 2);
  const py = (v) => margem.topo + h - ((v - min) / (max - min)) * h;

  ctx.font = '11px ui-monospace, monospace';
  ctx.strokeStyle = corBorda;
  ctx.fillStyle = corTexto;
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const valor = min + ((max - min) * i) / 4;
    const y = Math.round(py(valor)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(margem.esquerda, y);
    ctx.lineTo(largura - margem.direita, y);
    ctx.stroke();
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillText(moedaCurta(valor), margem.esquerda - 8, y);
  }

  ctx.textBaseline = 'top';
  const passo = Math.max(1, Math.ceil(n / 8));
  const marcas = [];
  for (let i = 0; i < n; i += passo) marcas.push(i);
  if (marcas[marcas.length - 1] !== n - 1) marcas.push(n - 1);
  marcas.forEach((i, k) => {
    // Âncora as pontas para dentro, senão o primeiro e o último rótulo vazam.
    ctx.textAlign = i === 0 ? 'left' : (i === n - 1 ? 'right' : 'center');
    if (k > 0 && i - marcas[k - 1] < passo / 2) return; // evita rótulos colados
    ctx.fillText(opcoes.rotuloX ? opcoes.rotuloX(i) : String(i), px(i), margem.topo + h + 8);
  });

  const corResolvida = (cor) => (cor.startsWith('var(')
    ? estilo.getPropertyValue(cor.slice(4, -1)).trim() : cor);

  for (const s of series) {
    ctx.beginPath();
    ctx.strokeStyle = corResolvida(s.cor);
    ctx.lineWidth = s.tracejada ? 1.5 : 2;
    ctx.setLineDash(s.tracejada ? [4, 4] : []);
    s.valores.forEach((v, i) => (i ? ctx.lineTo(px(i), py(v)) : ctx.moveTo(px(i), py(v))));
    ctx.stroke();
  }
  ctx.setLineDash([]);

  if (rotularPontas) {
    const marcas = series.map((s2) => ({
      texto: moedaCurta(s2.valores[s2.valores.length - 1]),
      cor: corResolvida(s2.cor),
      y: py(s2.valores[s2.valores.length - 1]),
    })).sort((a, b) => a.y - b.y);

    // Empurra para baixo o que ficaria sobreposto, mantendo a ordem vertical.
    const ALTURA_MIN = 13;
    for (let i = 1; i < marcas.length; i++) {
      if (marcas[i].y - marcas[i - 1].y < ALTURA_MIN) {
        marcas[i].y = marcas[i - 1].y + ALTURA_MIN;
      }
    }
    const excesso = marcas.length && marcas[marcas.length - 1].y - (margem.topo + h);
    if (excesso > 0) marcas.forEach((m) => { m.y -= excesso; });

    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    for (const marca of marcas) {
      ctx.fillStyle = marca.cor;
      ctx.fillText(marca.texto, largura - margem.direita + 8, marca.y);
    }
    ctx.fillStyle = corTexto;
  }

  canvas._grafico = { series, px, py, n, margem, w, h, opcoes };
  ligarLeitura(canvas);
}

function ligarLeitura(canvas) {
  const leitura = $('#leitura');
  if (!leitura || canvas.id !== 'grafico' || canvas._ligado) return;
  canvas._ligado = true;

  canvas.addEventListener('mouseleave', () => {
    leitura.style.display = 'none';
    redesenhar(canvas);
  });
  canvas.addEventListener('mousemove', (evento) => {
    const g = canvas._grafico;
    if (!g) return;
    const caixa = canvas.getBoundingClientRect();
    const i = Math.round(((evento.clientX - caixa.left - g.margem.esquerda) / g.w) * (g.n - 1));
    if (i < 0 || i >= g.n) { leitura.style.display = 'none'; return; }

    redesenhar(canvas);
    const ctx = canvas.getContext('2d');
    ctx.save();
    ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--texto-tenue').trim();
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(g.px(i), g.margem.topo);
    ctx.lineTo(g.px(i), g.margem.topo + g.h);
    ctx.stroke();
    ctx.restore();

    leitura.innerHTML = `<div class="cabeca">${g.opcoes.rotuloX ? g.opcoes.rotuloX(i) : 'mês ' + i}</div>` +
      g.series.map((s) => `<div style="color:${s.cor.startsWith('var(') ? 'var(--texto-fraco)' : s.cor}">
        ${moeda(s.valores[Math.min(i, s.valores.length - 1)])} · ${escapar(s.nome)}</div>`).join('');
    leitura.style.display = 'block';
    const alvo = g.px(i) + 14;
    leitura.style.left = (alvo + leitura.offsetWidth > canvas.clientWidth
      ? g.px(i) - leitura.offsetWidth - 14 : alvo) + 'px';
    leitura.style.top = '10px';
  });
}

function redesenhar(canvas) {
  if (canvas._grafico) desenharLinhas(canvas, canvas._grafico.series, canvas._grafico.opcoes);
}

/* ---------------------------------------------------------- tema claro/escuro */
const CHAVE_TEMA = 'simulador-investimentos:tema';

// tema salvo (se houver) manda; senão segue o prefers-color-scheme do sistema.
function temaEfetivo() {
  const escolhido = document.documentElement.dataset.tema;
  if (escolhido) return escolhido;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'escuro' : 'claro';
}

function aplicarTema(tema, persistir = true) {
  if (tema) document.documentElement.dataset.tema = tema;
  else delete document.documentElement.dataset.tema;

  if (persistir) {
    try {
      if (tema) localStorage.setItem(CHAVE_TEMA, tema);
      else localStorage.removeItem(CHAVE_TEMA);
    } catch (erro) { /* localStorage indisponível (privado, etc.) — segue sem persistir */ }
  }

  const efetivo = temaEfetivo();
  $$('#alterna-tema button').forEach((botao) => {
    botao.setAttribute('aria-pressed', String(botao.dataset.temaOpcao === efetivo));
  });

  // o gráfico lê as cores do tema via getComputedStyle no momento do desenho,
  // então precisa ser refeito quando o tema muda.
  if (estado.ultimaSimulacao) redesenhar($('#grafico'));
  if (estado.historico) redesenhar($('#grafico-historico'));
}

function ligarTema() {
  let salvo = null;
  try { salvo = localStorage.getItem(CHAVE_TEMA); } catch (erro) { /* segue sem tema salvo */ }
  aplicarTema(salvo, false);

  $$('#alterna-tema button').forEach((botao) => {
    botao.addEventListener('click', () => aplicarTema(botao.dataset.temaOpcao));
  });

  // se o usuário nunca escolheu um tema, acompanha mudança do sistema ao vivo
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (!document.documentElement.dataset.tema) aplicarTema(null, false);
  });
}

/* ---------------------------------------------------------- eventos */
function ligarControles() {
  $('#simular').addEventListener('click', simular);
  $('#adicionar-aporte').addEventListener('click', adicionarAoCarteira);

  $('#modo-visualizacao').addEventListener('click', (evento) => {
    const botao = evento.target.closest('button');
    if (!botao) return;
    estado.modoVisualizacao = botao.dataset.modo;
    $$('#modo-visualizacao button').forEach((b) => b.setAttribute('aria-pressed', String(b === botao)));
    if (estado.ultimaSimulacao) renderizarResultados(estado.ultimaSimulacao);
  });

  $('#prazos').addEventListener('click', (evento) => {
    const botao = evento.target.closest('button');
    if (!botao) return;
    $('#meses').value = botao.dataset.meses;
    marcarPrazo();
    simular();
  });
  $('#meses').addEventListener('input', marcarPrazo);
  $('#meses').addEventListener('change', marcarPrazo);

  $$('.abas button').forEach((botao) => botao.addEventListener('click', () => {
    $$('.abas button').forEach((b) => b.setAttribute('aria-selected', String(b === botao)));
    const aba = botao.dataset.aba;
    $('#aba-projecao').hidden = aba !== 'projecao';
    $('#aba-historico').hidden = aba !== 'historico';
    $('#painel-detalhe').hidden = aba !== 'projecao' || !estado.ultimaSimulacao;
    if (aba === 'historico' && !estado.historico) {
      carregarHistoricoCarteira();
    }
  }));

  ['meses', 'cenario', 'considerar-ir', 'considerar-inflacao', 'considerar-valorizacao']
    .forEach((id) => $('#' + id).addEventListener('change', () => {
      if (estado.ultimaSimulacao) simular();
    }));

  let temporizador;
  window.addEventListener('resize', () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => {
      if (estado.ultimaSimulacao) redesenhar($('#grafico'));
      if (estado.historico) redesenhar($('#grafico-historico'));
    }, 150);
  });
}

function marcarPrazo() {
  const meses = $('#meses').value;
  $$('#prazos button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.meses === meses)));
}

(async function iniciar() {
  ligarTema();
  ligarControles();
  marcarPrazo();
  await Promise.all([carregarIndicadores(), carregarAtivos()]);

  // A página nunca abre vazia: oficializa um aporte padrão com o ativo que
  // carregarAtivos() já deixou marcado na lista e os valores dos campos.
  if (estado.ativoEscolhido) {
    const padrao = estado.ativos.find((a) => a.id === estado.ativoEscolhido);
    estado.carteira.push({
      id: 'c' + estado.proximoIdCarteira++,
      ativoId: padrao.id,
      nome: padrao.nome,
      valorInicial: Number($('#valor-inicial').value) || 100,
      aporteMensal: Number($('#aporte-mensal').value) || 0,
    });
    renderizarCarteira();
  }
  simular();
})();
