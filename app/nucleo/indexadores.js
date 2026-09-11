/* Traduz o bloco 'rendimento' de um ativo em uma taxa mensal efetiva.
   Toda taxa entra aqui em % ao ano e sai como fração ao mês. O resultado
   carrega a explicação de como foi obtido, para a tela nunca mostrar um
   número sem procedência. */

export const MESES_ANO = 12;

/** 12,00 (% a.a.) -> 0,009489 (fração a.m.), por juro composto. */
export function aaParaAm(taxaAaPct) {
  return Math.pow(1 + taxaAaPct / 100, 1 / MESES_ANO) - 1;
}

export function amParaAa(taxaAmFracao) {
  return (Math.pow(1 + taxaAmFracao, MESES_ANO) - 1) * 100;
}

/** Composição correta de duas taxas (ex.: IPCA + juro real). */
export function compor(taxaAPct, taxaBPct) {
  return ((1 + taxaAPct / 100) * (1 + taxaBPct / 100) - 1) * 100;
}

/** Retira um custo anual (administração/custódia) de uma taxa anual. */
export function descontar(taxaBrutaPct, taxaCustoPct) {
  if (taxaCustoPct <= 0) return taxaBrutaPct;
  return ((1 + taxaBrutaPct / 100) / (1 + taxaCustoPct / 100) - 1) * 100;
}

const dec = (v, casas = 2) => v.toLocaleString('pt-BR', {
  minimumFractionDigits: casas, maximumFractionDigits: casas,
});

/** Devolve a taxa efetiva do ativo e a explicação de como chegou nela.

    `fundos` é o mapa {ticker: conteúdo de dados/mercado/fundos/<ticker>.json},
    só preenchido para quem selecionou um FII ou ETF (ver app/dados.js). Sem
    isso os tipos 'fundo_fii' e 'etf_historico' não têm de onde ler. */
export function resolver(ativo, indicadores, premissas, cenario = 'base', fundos = {}, considerarValorizacaoProjetada = false) {
  const spec = ativo.rendimento;
  const estimativas = premissas.estimativas || {};

  const exigirFundo = (ticker) => {
    const bloco = fundos[ticker];
    if (!bloco || !bloco.resumo) {
      throw new Error(
        `"${ativo.nome}" depende do histórico de ${ticker}, que não está em dados/mercado/fundos/ `
        + '(rode "python coletor/atualizar.py" para coletar)');
    }
    return bloco;
  };

  // Indicador ausente daria NaN e viraria "R$ NaN" na tela. Falhar aqui faz o
  // ativo aparecer na lista de erros com o motivo, sem contaminar a comparação.
  const exigir = (chave) => {
    const valor = indicadores[chave];
    if (typeof valor !== 'number' || !Number.isFinite(valor)) {
      throw new Error(
        `"${ativo.nome}" depende do indicador ${chave}, que não está no retrato de mercado`);
    }
    return valor;
  };

  let bruta, explicacao, natureza;
  // Só 'fundo_fii' preenche isto: dividendo é isento e não deve compor o
  // capital tributável (ver docs/05-tributacao.md, regime 'fii'). Para todo
  // outro tipo, o motor trata 100% do crescimento como tributável, igual a
  // antes desta separação existir.
  let componenteIsentoAm;
  let componenteTributavelAm;

  switch (spec.tipo) {
    case 'pos_cdi': {
      const pct = spec.percentual_cdi;
      const cdi = exigir('cdi_aa');
      bruta = (cdi * pct) / 100;
      explicacao = `${pct}% do CDI (${dec(cdi)}% a.a.)`;
      natureza = 'contratada';
      break;
    }
    case 'pos_selic': {
      const spread = spec.spread_aa || 0;
      const selic = exigir('selic_meta_aa');
      bruta = spread ? compor(selic, spread) : selic;
      explicacao = `Selic ${dec(selic)}% a.a.` + (spread ? ` + ${spread}%` : '');
      natureza = 'contratada';
      break;
    }
    case 'prefixado': {
      bruta = spec.taxa_aa;
      explicacao = `Taxa prefixada de ${dec(bruta)}% a.a.`;
      natureza = 'contratada';
      break;
    }
    case 'ipca_mais': {
      const spread = spec.spread_aa;
      const ipcaProj = valorDoCenario(estimativas.ipca_projetado_aa, cenario, indicadores.ipca_12m);
      bruta = compor(ipcaProj, spread);
      explicacao = `IPCA projetado ${dec(ipcaProj)}% a.a. + ${spread}% de juro real`;
      natureza = 'hibrida';
      break;
    }
    case 'poupanca': {
      const poupancaAm = exigir('poupanca_am');
      bruta = amParaAa(poupancaAm / 100);
      explicacao = `Poupança a ${dec(poupancaAm, 4)}% a.m., anualizado`;
      natureza = 'contratada';
      break;
    }
    case 'estimado': {
      const bloco = estimativas[spec.chave_premissa];
      if (!bloco) {
        throw new Error(`Sem premissa de retorno para "${spec.chave_premissa}" em premissas.json`);
      }
      bruta = valorDoCenario(bloco.retorno_aa, cenario, null);
      explicacao = `Retorno ESTIMADO de ${dec(bruta)}% a.a. (cenário ${cenario})`;
      natureza = 'estimada';
      break;
    }
    case 'fundo_fii': {
      const bloco = exigirFundo(spec.ticker);
      const { resumo } = bloco;
      const dyAm = resumo.dividend_yield_am_medio_pct;
      const valorizacaoAm = considerarValorizacaoProjetada
        ? resumo.valorizacao_patrimonial_am_media_pct : 0;
      componenteIsentoAm = dyAm / 100;
      componenteTributavelAm = valorizacaoAm / 100;
      bruta = amParaAa(compor(dyAm, valorizacaoAm) / 100);
      explicacao = `Dividend yield médio de ${dec(dyAm)}% a.m. (fato: média dos últimos `
        + `${resumo.janela_meses} meses até ${resumo.referencia}, ${bloco.fonte})`
        + (considerarValorizacaoProjetada
          ? ` + valorização patrimonial projetada de ${dec(valorizacaoAm)}% a.m. (média do mesmo histórico)`
          : ' + valorização de cota NÃO projetada (opção desligada)');
      natureza = 'hibrida';
      break;
    }
    case 'etf_historico': {
      const bloco = exigirFundo(spec.ticker);
      const { resumo } = bloco;
      bruta = valorDoCenario(resumo.retorno_aa, cenario, null);
      explicacao = `Retorno ESTIMADO de ${dec(bruta)}% a.a. (cenário ${cenario}), a partir do `
        + `CAGR de preço dos últimos ${resumo.janela_meses} meses até ${resumo.referencia} `
        + `(${dec(resumo.retorno_aa.base)}% a.a. no cenário base ± ${dec(resumo.volatilidade_aa)}% `
        + `de desvio-padrão anualizado, ${bloco.fonte})`;
      natureza = 'estimada';
      break;
    }
    default:
      throw new Error(`Tipo de rendimento não suportado: ${spec.tipo}`);
  }

  const taxas = ativo.taxas || {};
  const custo = (taxas.administracao_aa || 0) + (taxas.custodia_aa || 0);
  // Nota: para 'fundo_fii', o DY e a valorização já vêm líquidos de despesas
  // do fundo (a CVM os calcula sobre o patrimônio líquido). `custo` só existe
  // para taxas ADICIONAIS que o simulador cobraria por fora (não é o caso de
  // nenhum ativo hoje) - se um dia existir, teria que ser rateado entre os
  // dois componentes abaixo, não só descontado de `bruta`.
  const liquidaDeTaxas = descontar(bruta, custo);
  if (custo) explicacao += `, menos ${custo}% a.a. de taxas`;

  return {
    taxa_aa: arredondar(liquidaDeTaxas, 4),
    taxa_aa_antes_taxas: arredondar(bruta, 4),
    taxa_am: aaParaAm(liquidaDeTaxas),
    custo_aa: arredondar(custo, 4),
    explicacao,
    natureza,
    ...(componenteIsentoAm !== undefined ? { componente_isento_am: componenteIsentoAm } : {}),
    ...(componenteTributavelAm !== undefined ? { componente_tributavel_am: componenteTributavelAm } : {}),
  };
}

function valorDoCenario(bloco, cenario, padrao) {
  if (typeof bloco === 'number') return bloco;
  if (bloco && typeof bloco === 'object') {
    if (cenario in bloco) return Number(bloco[cenario]);
    if ('base' in bloco) return Number(bloco.base);
  }
  if (padrao === null || padrao === undefined) {
    throw new Error('Cenário sem valor definido e sem padrão');
  }
  return Number(padrao);
}

export function arredondar(valor, casas = 2) {
  const f = Math.pow(10, casas);
  return Math.round((valor + Number.EPSILON) * f) / f;
}
