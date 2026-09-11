/* Camada fiscal brasileira aplicada sobre o resultado bruto da projeção.

   Regimes suportados:
     isento              LCI, LCA, CRI, CRA, poupança, debênture incentivada
     rf_regressivo       CDB, RDB, LC, Tesouro Direto (IR 22,5% -> 15% + IOF < 30d)
     etf_renda_variavel  ETFs de ações: 15% sobre o ganho, SEM isenção mensal
     acoes               15% sobre o ganho, isento até R$ 20.000 vendidos no mês
     cripto              15% sobre o ganho, isento até R$ 35.000 vendidos no mês
     fii                 20% sobre o ganho de capital na venda, SEM isenção mensal.
                          O dividendo mensal (isento) não entra aqui - o motor já
                          o separou antes de chamar `tributar` (ver motor.js)
     fundo_longo_prazo   come-cotas semestral (ainda não modelado, ver docs/05)

   Nada aqui é conselho tributário. As regras refletem a legislação geral para
   pessoa física e devem ser reconferidas antes de qualquer decisão real. */

import { arredondar } from './indexadores.js';

export const DIAS_MES_COMERCIAL = 30;

export function aliquotaIrRf(dias, tabela) {
  for (const faixa of tabela) {
    if (faixa.ate_dias === null || faixa.ate_dias === undefined || dias <= faixa.ate_dias) {
      return faixa.aliquota;
    }
  }
  return tabela[tabela.length - 1].aliquota;
}

/** IOF regressivo sobre o RENDIMENTO nos 30 primeiros dias. */
export function aliquotaIof(dias, tabela) {
  if (dias >= 30 || dias < 1) return 0;
  return dias - 1 < tabela.length ? Number(tabela[dias - 1]) : 0;
}

/** Calcula IOF e IR de uma posição encerrada.
    `lotes` = [{principal, valor_final, dias}], um por aporte, porque na tabela
    regressiva cada aporte tem seu próprio prazo. */
export function tributar(regime, lotes, valorVendaTotal, regras) {
  const rendimentoTotal = lotes.reduce((s, l) => s + (l.valor_final - l.principal), 0);

  if (regime === 'isento') return zero('Isento de IR para pessoa física');
  if (rendimentoTotal <= 0) return zero('Sem rendimento tributável no período');

  if (regime === 'rf_regressivo') {
    let iofTotal = 0;
    let irTotal = 0;
    for (const lote of lotes) {
      const ganho = lote.valor_final - lote.principal;
      if (ganho <= 0) continue;
      const iof = (ganho * aliquotaIof(lote.dias, regras.iof_regressivo_30d)) / 100;
      irTotal += ((ganho - iof) * aliquotaIrRf(lote.dias, regras.ir_regressivo_rf)) / 100;
      iofTotal += iof;
    }
    const tabela = regras.ir_regressivo_rf;
    const maior = Math.max(...lotes.map((l) => l.dias));
    const menor = Math.min(...lotes.map((l) => l.dias));
    const faixa = maior === menor
      ? `${aliquotaIrRf(maior, tabela)}%`
      : `${aliquotaIrRf(maior, tabela)}% a ${aliquotaIrRf(menor, tabela)}% (aportes com prazos diferentes)`;
    return montar(iofTotal, irTotal, rendimentoTotal, `IR regressivo: ${faixa}`);
  }

  if (regime === 'etf_renda_variavel' || regime === 'acoes' || regime === 'cripto' || regime === 'fii') {
    let aliquota;
    if (regime === 'acoes') {
      const limite = regras.isencao_venda_acoes_mensal || 0;
      aliquota = regras.ir_renda_variavel_aliquota;
      if (valorVendaTotal <= limite) return zero(textoIsencao(valorVendaTotal, limite));
    } else if (regime === 'cripto') {
      const limite = regras.isencao_venda_cripto_mensal || 0;
      aliquota = regras.ir_cripto_aliquota;
      if (valorVendaTotal <= limite) return zero(textoIsencao(valorVendaTotal, limite));
    } else if (regime === 'fii') {
      aliquota = regras.ir_fii_aliquota;
    } else {
      aliquota = regras.ir_renda_variavel_aliquota;
    }
    const detalhe = regime === 'fii'
      ? `${aliquota}% sobre o ganho de capital na venda de cotas (dividendo mensal já isento, contado à parte)`
      : `${aliquota}% sobre o ganho de capital`;
    return montar(0, (rendimentoTotal * aliquota) / 100, rendimentoTotal, detalhe);
  }

  if (regime === 'fundo_longo_prazo') {
    return montar(0, (rendimentoTotal * 15) / 100, rendimentoTotal,
      '15% (come-cotas ainda não modelado)');
  }

  throw new Error(`Regime tributário desconhecido: ${regime}`);
}

const reais = (v) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

function textoIsencao(venda, limite) {
  return `Venda de ${reais(venda)} abaixo da isenção mensal de ${reais(limite)}`;
}

function montar(iof, ir, rendimento, detalhe) {
  const total = iof + ir;
  return {
    iof: arredondar(iof),
    ir: arredondar(ir),
    total: arredondar(total),
    aliquota_efetiva: rendimento > 0 ? arredondar((total / rendimento) * 100) : 0,
    detalhe,
  };
}

function zero(detalhe) {
  return { iof: 0, ir: 0, total: 0, aliquota_efetiva: 0, detalhe };
}
