/* Simulador de Investimentos - front-end.
   Sem frameworks e sem dependencias externas: o backend local serve este
   arquivo e responde a /api/*. */

const API = '';
const PALETA = ['#1f6feb', '#e2506b', '#1a9e6a', '#d98324', '#8250df', '#0aa2c0', '#b8860b', '#5c6670'];

const estado = {
  ativos: [],
  selecionados: new Set(['cdb-100-cdi']),
  ultimaSimulacao: null,
  serieHistorica: null,
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
const pct = (v) => v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '%';
const dataBR = (iso) => {
  if (!iso) return '';
  const [a, m, d] = iso.split('-');
  return d ? `${d}/${m}/${a}` : `${m}/${a}`;
};

async function pegar(rota, opcoes) {
  const resposta = await fetch(API + rota, opcoes);
  const corpo = await resposta.json().catch(() => ({ erro: 'Resposta ilegível do servidor' }));
  if (!resposta.ok) throw new Error(corpo.erro || `Erro ${resposta.status}`);
  return corpo;
}

/* ---------------------------------------------------------- indicadores */
async function carregarIndicadores() {
  try {
    const dados = await pegar('/api/indicadores');
    const fonte = (chave) => {
      const o = dados._origem[chave] || {};
      return o.origem === 'Banco Central (SGS)'
        ? `BCB · ${dataBR(o.referencia)}`
        : `fallback local`;
    };
    const cartoes = [
      ['CDI', pct(dados.cdi_aa) + ' a.a.', fonte('cdi_aa')],
      ['Selic meta', pct(dados.selic_meta_aa) + ' a.a.', fonte('selic_meta_aa')],
      ['IPCA 12 meses', pct(dados.ipca_12m), fonte('ipca_12m')],
      ['Poupança', pct(dados.poupanca_am) + ' a.m.', fonte('poupanca_am')],
    ];
    $('#indicadores').innerHTML = cartoes.map(([r, v, f]) =>
      `<li><span class="rotulo">${r}</span><div class="valor">${v}</div><span class="fonte">${f}</span></li>`
    ).join('');

    $('#aviso-degradado').innerHTML = dados._degradado
      ? `<div class="aviso">Alguns indicadores não puderam ser lidos no Banco Central agora; o simulador está usando
         os valores de <code>premissas.json</code> como reserva. Os números abaixo podem estar desatualizados.</div>`
      : '';
  } catch (erro) {
    $('#indicadores').innerHTML = `<li><span class="rotulo">Indicadores</span><div class="valor">—</div>
      <span class="fonte">${erro.message}</span></li>`;
  }
}

/* ---------------------------------------------------------- catálogo */
const NOMES_CLASSE = {
  renda_fixa: 'Renda fixa',
  renda_variavel: 'Renda variável',
  cripto: 'Cripto',
  fundos: 'Fundos',
};

async function carregarAtivos() {
  const catalogo = await pegar('/api/ativos');
  estado.ativos = catalogo.ativos;

  const porClasse = {};
  for (const ativo of catalogo.ativos) (porClasse[ativo.classe] ||= []).push(ativo);

  $('#lista-ativos').innerHTML = Object.entries(porClasse).map(([classe, itens]) => `
    <div class="grupo-classe">${NOMES_CLASSE[classe] || classe}</div>
    ${itens.map((a) => `
      <label class="ativo" title="${a.descricao}">
        <input type="checkbox" value="${a.id}" ${estado.selecionados.has(a.id) ? 'checked' : ''}>
        <span>
          <span class="nome">${a.nome}</span>
          ${a.rendimento.tipo === 'estimado' ? '<span class="selo estimado">estimado</span>' : ''}
          ${a.tributacao.regime === 'isento' ? '<span class="selo isento">isento de IR</span>' : ''}
          <div class="meta">${rotuloRendimento(a)} · risco ${a.risco}/6</div>
        </span>
      </label>`).join('')}
  `).join('');

  $$('#lista-ativos input').forEach((caixa) => caixa.addEventListener('change', () => {
    caixa.checked ? estado.selecionados.add(caixa.value) : estado.selecionados.delete(caixa.value);
    atualizarContagem();
  }));
  atualizarContagem();
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
    default: return r.tipo;
  }
}

function atualizarContagem() {
  const n = estado.selecionados.size;
  $('#contagem-ativos').textContent = n ? `(${n} selecionado${n > 1 ? 's' : ''})` : '';
}

/* ---------------------------------------------------------- simulação */
async function simular() {
  if (!estado.selecionados.size) {
    $('#resumo').innerHTML = '<p class="vazio">Selecione ao menos um ativo.</p>';
    return;
  }
  const botao = $('#simular');
  botao.disabled = true;
  botao.textContent = 'Simulando…';

  try {
    const corpo = {
      ativos: Array.from(estado.selecionados),
      valor_inicial: Number($('#valor-inicial').value) || 0,
      aporte_mensal: Number($('#aporte-mensal').value) || 0,
      meses: Number($('#meses').value) || 12,
      cenario: $('#cenario').value,
      considerar_ir: $('#considerar-ir').checked,
      considerar_inflacao: $('#considerar-inflacao').checked,
    };
    const saida = await pegar('/api/simular', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corpo),
    });
    estado.ultimaSimulacao = saida;
    renderizarResultados(saida);
  } catch (erro) {
    $('#resumo').innerHTML = `<div class="aviso">${erro.message}</div>`;
  } finally {
    botao.disabled = false;
    botao.textContent = 'Simular';
  }
}

function renderizarResultados(saida) {
  const { resultados, parametros } = saida;
  if (!resultados.length) {
    $('#resumo').innerHTML = '<p class="vazio">Nenhum resultado.</p>';
    return;
  }
  const mostrarReal = parametros.considerar_inflacao;
  const mostrarIR = parametros.considerar_ir;

  const cabecalho = `
    <tr>
      <th>Ativo</th>
      <th>Taxa efetiva</th>
      <th>Investido</th>
      <th>Bruto</th>
      ${mostrarIR ? '<th>IR + IOF</th>' : ''}
      <th>Líquido</th>
      ${mostrarReal ? '<th>Valor real</th>' : ''}
      <th>Ganho líq.</th>
      <th>Rent. líq.</th>
    </tr>`;

  const linhas = resultados.map((r, i) => {
    const cor = PALETA[i % PALETA.length];
    const ganho = r.rendimento_liquido;
    return `
      <tr class="tem-explicacao">
        <td><span class="pastilha" style="background:${cor}"></span>${r.nome}</td>
        <td class="num">${pct(r.taxa.taxa_aa)} a.a.</td>
        <td class="num">${moeda(r.investido)}</td>
        <td class="num">${moeda(r.bruto)}</td>
        ${mostrarIR ? `<td class="num negativo">${r.impostos.total ? '−' + moeda(r.impostos.total) : '—'}</td>` : ''}
        <td class="num destaque">${moeda(r.liquido)}</td>
        ${mostrarReal ? `<td class="num">${moeda(r.liquido_real)}</td>` : ''}
        <td class="num ${ganho >= 0 ? 'positivo' : 'negativo'}">${ganho >= 0 ? '+' : ''}${moeda(ganho)}</td>
        <td class="num ${ganho >= 0 ? 'positivo' : 'negativo'} destaque">${pct(r.rentabilidade_liquida_pct)}</td>
      </tr>
      <tr class="linha-explicacao">
        <td colspan="9">${r.taxa.explicacao}. ${r.impostos.detalhe}.
        ${mostrarReal ? `Descontando IPCA projetado de ${pct(r.inflacao.ipca_aa_projetado)} a.a., sobra ${pct(r.rentabilidade_real_pct)} de ganho real.` : ''}</td>
      </tr>`;
  }).join('');

  const melhor = resultados[0];
  const prazoTexto = parametros.meses === 1 ? '1 mês' : `${parametros.meses} meses`;
  const aporteTexto = parametros.aporte_mensal > 0
    ? ` com aportes de ${moeda(parametros.aporte_mensal)} por mês` : '';

  $('#resumo').innerHTML = `
    <p style="margin:0 0 14px;color:var(--texto-fraco)">
      ${moeda(parametros.valor_inicial)}${aporteTexto} em <strong>${prazoTexto}</strong>.
      Melhor resultado líquido: <strong style="color:var(--texto)">${melhor.nome}</strong>
      com ${moeda(melhor.liquido)}${mostrarReal ? ` (${moeda(melhor.liquido_real)} em poder de compra de hoje)` : ''}.
    </p>
    <div class="tabela-envolucro"><table><thead>${cabecalho}</thead><tbody>${linhas}</tbody></table></div>`;

  $('#grafico-caixa').hidden = false;
  const series = resultados.map((r, i) => ({
    nome: r.nome,
    cor: PALETA[i % PALETA.length],
    valores: r.serie.map((p) => p.bruto),
  }));
  series.push({
    nome: 'Total investido',
    cor: 'var(--texto-tenue)',
    tracejada: true,
    valores: resultados[0].serie.map((p) => p.investido),
  });
  desenharLinhas($('#grafico'), series, { rotuloX: (i) => `mês ${i}` });

  $('#legenda').innerHTML = series.map((s) =>
    `<span><i class="pastilha" style="background:${s.cor}"></i>${s.nome}</span>`).join('');

  renderizarDetalhe(saida);
}

function renderizarDetalhe(saida) {
  const p = saida.procedencia;
  const unidade = { cdi_aa: ' a.a.', selic_meta_aa: ' a.a.', ipca_12m: '', poupanca_am: ' a.m.' };
  const linhas = Object.entries(p).map(([chave, info]) => `
    <tr>
      <td>${({ cdi_aa: 'CDI', selic_meta_aa: 'Selic meta', ipca_12m: 'IPCA 12 meses', poupanca_am: 'Poupança' })[chave] || chave}</td>
      <td class="num">${pct(saida.indicadores[chave])}${unidade[chave] ?? ''}</td>
      <td>${info.origem}${info.serie_sgs ? ` · série SGS ${info.serie_sgs}` : ''}</td>
      <td>${dataBR(info.referencia)}</td>
    </tr>`).join('');
  $('#painel-detalhe').hidden = false;
  $('#detalhe').innerHTML = `
    <div class="tabela-envolucro"><table>
      <thead><tr><th>Indicador</th><th>Valor</th><th>Fonte</th><th>Referência</th></tr></thead>
      <tbody>${linhas}</tbody>
    </table></div>
    <p class="rodape-nota">Prazos de IR usam mês comercial de 30 dias. Cada aporte mensal é tratado como um lote
    próprio, então na tabela regressiva os aportes mais recentes pagam alíquota maior.</p>`;
}

/* ---------------------------------------------------------- histórico */
async function carregarHistorico() {
  const serie = $('#serie-historica').value;
  $('#resumo-historico').innerHTML = '<p class="vazio">carregando série do Banco Central…</p>';
  try {
    const dados = await pegar(`/api/historico?serie=${serie}&meses=60`);
    estado.serieHistorica = dados;
    const primeiro = dados.pontos[0], ultimo = dados.pontos[dados.pontos.length - 1];
    $('#resumo-historico').innerHTML = `
      <p style="margin:0 0 12px;color:var(--texto-fraco)">
        <strong style="color:var(--texto)">${dados.rotulo}</strong> — acumulado de
        <strong style="color:var(--texto)">${pct(dados.acumulado_total_pct)}</strong>
        entre ${dataBR(primeiro.data)} e ${dataBR(ultimo.data)}.
        R$ 100 aplicados no início do período valeriam ${moeda(ultimo.indice_100)}.
        Fonte: ${dados.fonte}, série ${dados.serie_sgs}.
      </p>`;
    desenharLinhas($('#grafico-historico'), [{
      nome: dados.rotulo,
      cor: PALETA[0],
      valores: dados.pontos.map((p) => p.indice_100),
    }], { rotuloX: (i) => dataBR(dados.pontos[Math.min(i, dados.pontos.length - 1)].data) });
  } catch (erro) {
    $('#resumo-historico').innerHTML = `<div class="aviso">${erro.message}</div>`;
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

  const margem = { topo: 12, direita: 12, baixo: 26, esquerda: 62 };
  const w = largura - margem.esquerda - margem.direita;
  const h = altura - margem.topo - margem.baixo;
  const n = Math.max(...series.map((s) => s.valores.length));

  const todos = series.flatMap((s) => s.valores);
  let min = Math.min(...todos), max = Math.max(...todos);
  if (min === max) { min -= 1; max += 1; }
  const folga = (max - min) * 0.08;
  min = Math.max(0, min - folga); max += folga;

  const px = (i) => margem.esquerda + (n > 1 ? (i / (n - 1)) * w : w / 2);
  const py = (v) => margem.topo + h - ((v - min) / (max - min)) * h;

  ctx.font = '11px ui-monospace, monospace';
  ctx.strokeStyle = corBorda;
  ctx.fillStyle = corTexto;
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const valor = min + ((max - min) * i) / 4;
    const y = Math.round(py(valor)) + 0.5;
    ctx.beginPath(); ctx.moveTo(margem.esquerda, y); ctx.lineTo(largura - margem.direita, y); ctx.stroke();
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    ctx.fillText(moedaCurta(valor), margem.esquerda - 8, y);
  }

  ctx.textBaseline = 'top';
  const passo = Math.max(1, Math.ceil(n / 8));
  const marcas = [];
  for (let i = 0; i < n; i += passo) marcas.push(i);
  if (marcas[marcas.length - 1] !== n - 1) marcas.push(n - 1);
  marcas.forEach((i, k) => {
    // Ancora as pontas para dentro, senao o primeiro e o ultimo rotulo vazam.
    ctx.textAlign = i === 0 ? 'left' : (i === n - 1 ? 'right' : 'center');
    if (k > 0 && i - marcas[k - 1] < passo / 2) return; // evita rotulos colados
    ctx.fillText(opcoes.rotuloX ? opcoes.rotuloX(i) : String(i), px(i), margem.topo + h + 8);
  });

  const corResolvida = (cor) => cor.startsWith('var(')
    ? estilo.getPropertyValue(cor.slice(4, -1)).trim() : cor;

  for (const s of series) {
    ctx.beginPath();
    ctx.strokeStyle = corResolvida(s.cor);
    ctx.lineWidth = s.tracejada ? 1.5 : 2;
    ctx.setLineDash(s.tracejada ? [4, 4] : []);
    s.valores.forEach((v, i) => (i ? ctx.lineTo(px(i), py(v)) : ctx.moveTo(px(i), py(v))));
    ctx.stroke();
  }
  ctx.setLineDash([]);

  canvas._grafico = { series, px, py, n, margem, w, h, opcoes };
  ligarLeitura(canvas);
}

function ligarLeitura(canvas) {
  const leitura = $('#leitura');
  if (!leitura || canvas.id !== 'grafico') return;
  if (canvas._ligado) return;
  canvas._ligado = true;

  canvas.addEventListener('mouseleave', () => { leitura.style.display = 'none'; redesenhar(canvas); });
  canvas.addEventListener('mousemove', (evento) => {
    const g = canvas._grafico;
    if (!g) return;
    const caixa = canvas.getBoundingClientRect();
    const x = evento.clientX - caixa.left;
    const i = Math.round(((x - g.margem.esquerda) / g.w) * (g.n - 1));
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
        ${moeda(s.valores[Math.min(i, s.valores.length - 1)])} · ${s.nome}</div>`).join('');
    leitura.style.display = 'block';
    const larguraLeitura = leitura.offsetWidth;
    const alvo = g.px(i) + 14;
    leitura.style.left = (alvo + larguraLeitura > canvas.clientWidth ? g.px(i) - larguraLeitura - 14 : alvo) + 'px';
    leitura.style.top = '10px';
  });
}

function redesenhar(canvas) {
  const g = canvas._grafico;
  if (g) desenharLinhas(canvas, g.series, g.opcoes);
}

/* ---------------------------------------------------------- eventos */
function ligarControles() {
  $('#simular').addEventListener('click', simular);

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
    if (aba === 'historico' && !estado.serieHistorica) carregarHistorico();
  }));
  $('#serie-historica').addEventListener('change', carregarHistorico);

  ['valor-inicial', 'aporte-mensal', 'meses', 'cenario'].forEach((id) => {
    $('#' + id).addEventListener('change', () => estado.ultimaSimulacao && simular());
  });
  ['considerar-ir', 'considerar-inflacao'].forEach((id) => {
    $('#' + id).addEventListener('change', () => estado.ultimaSimulacao && simular());
  });

  let temporizador;
  window.addEventListener('resize', () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => {
      if (estado.ultimaSimulacao) redesenhar($('#grafico'));
      if (estado.serieHistorica) redesenhar($('#grafico-historico'));
    }, 150);
  });
}

function marcarPrazo() {
  const meses = $('#meses').value;
  $$('#prazos button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.meses === meses)));
}

(async function iniciar() {
  ligarControles();
  marcarPrazo();
  await Promise.all([carregarIndicadores(), carregarAtivos()]);
  simular();
})();
