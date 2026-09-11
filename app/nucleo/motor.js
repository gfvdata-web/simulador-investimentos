/* Motor de projeção: transforma aportes + taxa em uma trajetória mês a mês.

   Convenções (documentadas em docs/03-motor-de-calculo.md):
     - O mês 1 é o primeiro mês cheio de rendimento.
     - O capital inicial entra no começo do mês 1 e rende os N meses.
     - Cada aporte mensal entra no começo do seu mês e rende daquele mês em diante.
     - Cada entrada de dinheiro vira um LOTE próprio, porque a tabela regressiva
       de IR conta o prazo de cada aporte separadamente.
     - Prazo para fins de IR usa mês comercial de 30 dias. */

import { resolver, arredondar } from './indexadores.js';
import { tributar, DIAS_MES_COMERCIAL } from './tributos.js';

export const MAX_MESES = 600;

export function projetar(ativo, indicadores, premissas, {
  valor_inicial: valorInicial = 0,
  aporte_mensal: aporteMensal = 0,
  meses = 12,
  cenario = 'base',
  considerar_ir: considerarIr = true,
  considerar_inflacao: considerarInflacao = true,
  considerar_valorizacao_projetada: considerarValorizacaoProjetada = false,
} = {}, fundos = {}) {
  if (!Number.isFinite(meses) || meses < 1 || meses > MAX_MESES) {
    throw new Error(`Prazo deve estar entre 1 e ${MAX_MESES} meses`);
  }
  if (valorInicial < 0 || aporteMensal < 0) {
    throw new Error('Valores de aporte não podem ser negativos');
  }
  if (valorInicial <= 0 && aporteMensal <= 0) {
    throw new Error('Informe um valor inicial ou um aporte mensal');
  }

  const taxa = resolver(ativo, indicadores, premissas, cenario, fundos, considerarValorizacaoProjetada);
  const taxaAm = taxa.taxa_am;
  // Só FII (regime 'fii') preenche estes dois campos, separando o dividendo
  // (isento, não compõe o capital que sofre ganho de capital) da valorização
  // patrimonial (tributável na venda). Para todo outro ativo, isentoAm é 0 e
  // tributavelAm é a taxa cheia - o cálculo abaixo se reduz exatamente ao que
  // era antes desta separação existir (ver docs/03-motor-de-calculo.md).
  const isentoAm = taxa.componente_isento_am || 0;
  const tributavelAm = taxa.componente_tributavel_am ?? taxaAm;

  const lotes = [];
  const serie = [{ mes: 0, bruto: arredondar(valorInicial), investido: arredondar(valorInicial) }];
  let investido = valorInicial;
  let dividendosIsentos = 0;

  if (valorInicial > 0) {
    lotes.push({ mes_entrada: 1, principal: valorInicial, valor_final: valorInicial });
  }

  for (let mes = 1; mes <= meses; mes++) {
    if (aporteMensal > 0) {
      lotes.push({ mes_entrada: mes, principal: aporteMensal, valor_final: aporteMensal });
      investido += aporteMensal;
    }
    for (const lote of lotes) {
      dividendosIsentos += lote.valor_final * isentoAm;
      lote.valor_final *= 1 + tributavelAm;
    }
    const brutoPatrimonialMes = lotes.reduce((s, l) => s + l.valor_final, 0);
    serie.push({
      mes,
      bruto: arredondar(brutoPatrimonialMes + dividendosIsentos),
      investido: arredondar(investido),
    });
  }

  // `brutoPatrimonial` é só a parte que ainda está "na cota" - é sobre ela
  // que o IR de ganho de capital incide. Os dividendos já foram recebidos
  // (isentos) mês a mês e não entram nos lotes.
  const brutoPatrimonial = lotes.reduce((s, l) => s + l.valor_final, 0);
  const brutoFinal = brutoPatrimonial + dividendosIsentos;
  for (const lote of lotes) {
    lote.dias = (meses - lote.mes_entrada + 1) * DIAS_MES_COMERCIAL;
  }

  const impostos = considerarIr
    ? tributar(ativo.tributacao.regime, lotes, brutoPatrimonial, premissas.tributacao)
    : { iof: 0, ir: 0, total: 0, aliquota_efetiva: 0, detalhe: 'Impostos desligados nesta simulação' };

  const liquido = brutoPatrimonial - impostos.total + dividendosIsentos;
  const inflacao = calcularInflacao(premissas, indicadores, cenario, meses);
  const liquidoReal = considerarInflacao ? liquido / inflacao.fator : liquido;

  return {
    ativo_id: ativo.id,
    nome: ativo.nome,
    classe: ativo.classe,
    risco: ativo.risco,
    taxa,
    meses,
    investido: arredondar(investido),
    bruto: arredondar(brutoFinal),
    rendimento_bruto: arredondar(brutoFinal - investido),
    dividendos_isentos: arredondar(dividendosIsentos),
    impostos,
    liquido: arredondar(liquido),
    rendimento_liquido: arredondar(liquido - investido),
    liquido_real: arredondar(liquidoReal),
    ganho_real: arredondar(liquidoReal - investido),
    rentabilidade_bruta_pct: variacao(brutoFinal, investido),
    rentabilidade_liquida_pct: variacao(liquido, investido),
    rentabilidade_real_pct: variacao(liquidoReal, investido),
    inflacao,
    serie,
    lotes: lotes.length,
  };
}

export function comparar(ativos, indicadores, premissas, parametros, fundos = {}) {
  const resultados = [];
  const erros = [];

  for (const ativo of ativos) {
    try {
      resultados.push(projetar(ativo, indicadores, premissas, parametros, fundos));
    } catch (erro) {
      erros.push({ ativo_id: ativo.id, erro: erro.message });
    }
  }

  resultados.sort((a, b) => b.liquido - a.liquido);
  resultados.forEach((r, i) => {
    r.ranking = i + 1;
    r.diferenca_para_1o = arredondar(r.liquido - resultados[0].liquido);
  });

  return { resultados, erros };
}

function calcularInflacao(premissas, indicadores, cenario, meses) {
  const bloco = (premissas.estimativas || {}).ipca_projetado_aa;
  let ipcaAa;
  if (bloco && typeof bloco === 'object') {
    ipcaAa = Number(bloco[cenario] ?? bloco.base ?? indicadores.ipca_12m);
  } else {
    ipcaAa = Number(bloco || indicadores.ipca_12m);
  }
  const fator = Math.pow(1 + ipcaAa / 100, meses / 12);
  return {
    ipca_aa_projetado: arredondar(ipcaAa, 4),
    fator,
    perda_poder_compra_pct: arredondar((1 - 1 / fator) * 100),
    cenario,
  };
}

function variacao(final, investido) {
  if (investido <= 0) return 0;
  return arredondar((final / investido - 1) * 100);
}
