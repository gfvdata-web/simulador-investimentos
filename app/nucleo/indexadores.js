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

/** Devolve a taxa efetiva do ativo e a explicação de como chegou nela. */
export function resolver(ativo, indicadores, premissas, cenario = 'base') {
  const spec = ativo.rendimento;
  const estimativas = premissas.estimativas || {};
  const { cdi_aa: cdi, selic_meta_aa: selic, ipca_12m: ipca, poupanca_am: poupancaAm } = indicadores;

  let bruta, explicacao, natureza;

  switch (spec.tipo) {
    case 'pos_cdi': {
      const pct = spec.percentual_cdi;
      bruta = (cdi * pct) / 100;
      explicacao = `${pct}% do CDI (${dec(cdi)}% a.a.)`;
      natureza = 'contratada';
      break;
    }
    case 'pos_selic': {
      const spread = spec.spread_aa || 0;
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
      const ipcaProj = valorDoCenario(estimativas.ipca_projetado_aa, cenario, ipca);
      bruta = compor(ipcaProj, spread);
      explicacao = `IPCA projetado ${dec(ipcaProj)}% a.a. + ${spread}% de juro real`;
      natureza = 'hibrida';
      break;
    }
    case 'poupanca': {
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
    default:
      throw new Error(`Tipo de rendimento não suportado: ${spec.tipo}`);
  }

  const taxas = ativo.taxas || {};
  const custo = (taxas.administracao_aa || 0) + (taxas.custodia_aa || 0);
  const liquidaDeTaxas = descontar(bruta, custo);
  if (custo) explicacao += `, menos ${custo}% a.a. de taxas`;

  return {
    taxa_aa: arredondar(liquidaDeTaxas, 4),
    taxa_aa_antes_taxas: arredondar(bruta, 4),
    taxa_am: aaParaAm(liquidaDeTaxas),
    custo_aa: arredondar(custo, 4),
    explicacao,
    natureza,
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
