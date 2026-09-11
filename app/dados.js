/* Acesso aos arquivos de dados do repositório.

   A página NÃO fala com a internet. Tudo que ela lê está versionado aqui:

     dados/catalogo/ativos.json       o que existe para simular
     dados/premissas/premissas.json   palpites e regras fiscais
     dados/mercado/indicadores.json   retrato do mercado + manifesto das séries e fundos
     dados/mercado/series/*.json      histórico mensal dos indicadores
     dados/mercado/fundos/*.json      histórico mensal de cada FII/ETF (dividend
                                       yield, valorização e/ou preço, ver docs/04)

   Os dois últimos são gerados pelo coletor (coletor/atualizar.py). Nada aqui
   sabe quais indicadores ou séries existem: a lista vem do próprio retrato,
   com rótulo e unidade. Indicador novo é edição de um lugar só, no coletor.

   Consequência a encarar: o dado tem idade. Ela viaja junto com o número, e a
   página mostra quando o retrato ficou velho demais. */

const CAMINHOS = {
  ativos: 'dados/catalogo/ativos.json',
  premissas: 'dados/premissas/premissas.json',
  mercado: 'dados/mercado/indicadores.json',
};
const DIR_MERCADO = 'dados/mercado/';
const DIR_FUNDOS = 'dados/mercado/fundos/';

/** Acima disso a página avisa que o retrato está velho. */
export const DIAS_ATE_VENCER = 10;

const memoria = new Map();

async function lerJson(caminho) {
  if (memoria.has(caminho)) return memoria.get(caminho);
  const promessa = fetch(caminho, { cache: 'no-cache' }).then((r) => {
    if (!r.ok) throw new Error(`Não consegui ler ${caminho} (HTTP ${r.status})`);
    return r.json();
  });
  memoria.set(caminho, promessa);
  return promessa;
}

export async function catalogo() {
  return lerJson(CAMINHOS.ativos);
}

export async function ativosPorId() {
  const { ativos } = await catalogo();
  return Object.fromEntries(ativos.map((a) => [a.id, a]));
}

export async function premissas() {
  return lerJson(CAMINHOS.premissas);
}

async function retratoMercado() {
  try {
    return await lerJson(CAMINHOS.mercado);
  } catch (erro) {
    return { _erro: erro.message, campos: {}, series: [] };
  }
}

function diasDesde(iso) {
  if (!iso) return null;
  const quando = new Date(iso);
  if (Number.isNaN(quando.getTime())) return null;
  return Math.floor((Date.now() - quando.getTime()) / 86400000);
}

/** Indicadores prontos para o motor, com a procedência de cada campo.

    O motor lê os valores por nome (`indicadores.cdi_aa`); a página lê
    `_meta` para montar os cartões sem saber de antemão quais existem. */
export async function indicadores() {
  const premissasArquivo = await premissas();
  const fallback = premissasArquivo.indicadores || {};
  const retrato = await retratoMercado();

  const final = {};
  const meta = {};
  let degradado = false;

  // As chaves saem do retrato; o fallback só entra para as que o retrato
  // conhece mas não conseguiu preencher.
  for (const [chave, campo] of Object.entries(retrato.campos || {})) {
    if (campo.valor !== null && campo.valor !== undefined) {
      final[chave] = campo.valor;
      meta[chave] = {
        rotulo: campo.rotulo || chave,
        unidade: campo.unidade || '',
        origem: campo.fonte || 'fonte oficial',
        heranca: campo.origem !== 'fonte oficial' ? campo.origem : null,
        referencia_fonte: campo.referencia_fonte,
        referencia: campo.referencia,
      };
    } else if (chave in fallback) {
      final[chave] = fallback[chave];
      meta[chave] = {
        rotulo: campo.rotulo || chave,
        unidade: campo.unidade || '',
        origem: 'fallback de premissas.json',
        referencia: premissasArquivo.atualizado_em,
        detalhe: campo.detalhe || 'fonte indisponível',
      };
      degradado = true;
    }
    // Campo sem valor e sem fallback fica de fora: melhor ausente que inventado.
  }

  // Retrato ilegível: sobra o que premissas.json souber, todo marcado.
  if (!Object.keys(final).length) {
    for (const [chave, valor] of Object.entries(fallback)) {
      if (chave.startsWith('_')) continue;
      final[chave] = valor;
      meta[chave] = {
        rotulo: chave,
        unidade: '',
        origem: 'fallback de premissas.json',
        referencia: premissasArquivo.atualizado_em,
        detalhe: retrato._erro || 'retrato de mercado indisponível',
      };
    }
    degradado = true;
  }

  const idade = diasDesde(retrato.coletado_em);
  final._meta = meta;
  final._degradado = degradado;
  final._coletado_em = retrato.coletado_em || null;
  final._idade_dias = idade;
  final._vencido = idade !== null && idade > DIAS_ATE_VENCER;
  return final;
}

/** Manifesto das séries disponíveis: [{id, rotulo, rotulo_curto, ...}]. */
export async function seriesDisponiveis() {
  const retrato = await retratoMercado();
  return retrato.series || [];
}

/** Série histórica mensal real, acumulada a partir do primeiro ponto. */
export async function historico(serieId, meses = 60) {
  const disponiveis = await seriesDisponiveis();
  const entrada = disponiveis.find((s) => s.id === serieId);
  if (!entrada) {
    const ids = disponiveis.map((s) => s.id).join(', ') || 'nenhuma';
    throw new Error(`Série "${serieId}" não está no retrato. Disponíveis: ${ids}`);
  }

  const arquivo = await lerJson(DIR_MERCADO + entrada.arquivo);

  // O mês corrente é publicado parcial pela fonte: incluí-lo desenharia uma
  // queda falsa no último ponto.
  const mesAtual = new Date().toISOString().slice(0, 7);
  const pontos = arquivo.pontos
    .filter((p) => p.data.slice(0, 7) !== mesAtual)
    .slice(-meses);
  if (!pontos.length) throw new Error(`Série "${serieId}" sem meses fechados disponíveis`);

  let fator = 1;
  const acumulado = pontos.map((p) => {
    fator *= 1 + p.valor / 100;
    return {
      data: p.data,
      mensal_pct: p.valor,
      acumulado_pct: Math.round((fator - 1) * 1e6) / 1e4,
      indice_100: Math.round(fator * 1e6) / 1e4,
    };
  });

  return {
    ...entrada,
    coletado_em: arquivo.coletado_em,
    meses_disponiveis: arquivo.pontos.length,
    pontos: acumulado,
    acumulado_total_pct: acumulado[acumulado.length - 1].acumulado_pct,
  };
}

/* ---------------------------------------------------------- fundos (FII/ETF) */
/** Manifesto dos fundos coletados: [{ticker, tipo, rotulo, arquivo, ...}]. */
export async function fundosDisponiveis() {
  const retrato = await retratoMercado();
  return retrato.fundos || [];
}

/** Histórico + resumo de um conjunto de tickers, só o que `app/nucleo/` precisa
    para resolver 'fundo_fii' e 'etf_historico'. Pede só os tickers dos ativos
    selecionados - a página não carrega os 13 arquivos se o usuário marcou 2. */
export async function fundos(tickers) {
  const unicos = [...new Set(tickers)];
  const entradas = await Promise.all(unicos.map(async (ticker) => {
    try {
      return [ticker, await lerJson(DIR_FUNDOS + `${ticker}.json`)];
    } catch (erro) {
      // Sem arquivo coletado ainda: o resolver do núcleo é quem decide o que
      // fazer (hoje, o ativo cai em `erros` da comparação com uma mensagem
      // clara) - não inventamos um valor aqui.
      return [ticker, null];
    }
  }));
  return Object.fromEntries(entradas.filter(([, valor]) => valor !== null));
}
