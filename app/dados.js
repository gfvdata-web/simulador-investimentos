/* Acesso aos arquivos de dados do repositório.

   A página NÃO fala com a internet. Tudo que ela lê está versionado aqui:

     dados/catalogo/ativos.json       o que existe para simular
     dados/premissas/premissas.json   palpites e regras fiscais
     dados/mercado/indicadores.json   retrato do CDI/Selic/IPCA/poupança
     dados/mercado/series/*.json      histórico mensal

   Os dois últimos são gerados pelo coletor (coletor/atualizar.py), que roda
   periodicamente no GitHub Actions. Consequências boas disso: o site funciona
   mesmo com a fonte fora do ar, cada simulação é auditável pelo histórico do
   git, e nenhuma fonte precisa liberar CORS para o projeto crescer.

   Consequência a encarar: o dado tem idade. Ela viaja junto com o número, e a
   página mostra quando o retrato ficou velho demais. */

const CAMINHOS = {
  ativos: 'dados/catalogo/ativos.json',
  premissas: 'dados/premissas/premissas.json',
  indicadores: 'dados/mercado/indicadores.json',
  serie: (nome) => `dados/mercado/series/${nome}.json`,
};

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

function diasDesde(iso) {
  if (!iso) return null;
  const quando = new Date(iso);
  if (Number.isNaN(quando.getTime())) return null;
  return Math.floor((Date.now() - quando.getTime()) / 86400000);
}

/** Indicadores prontos para o motor, com a procedência de cada campo. */
export async function indicadores() {
  const premissasArquivo = await premissas();
  const base = premissasArquivo.indicadores;

  let retrato = null;
  let erroRetrato = null;
  try {
    retrato = await lerJson(CAMINHOS.indicadores);
  } catch (erro) {
    erroRetrato = erro.message;
  }

  const final = {};
  const procedencia = {};
  let degradado = false;

  for (const chave of ['cdi_aa', 'selic_meta_aa', 'ipca_12m', 'poupanca_am']) {
    const campo = retrato?.campos?.[chave];
    if (campo && campo.valor !== null && campo.valor !== undefined) {
      final[chave] = campo.valor;
      procedencia[chave] = {
        origem: campo.origem || 'Banco Central (SGS)',
        serie_sgs: campo.serie_sgs,
        referencia: campo.referencia,
        coletado_em: retrato.coletado_em,
      };
    } else {
      final[chave] = base[chave];
      procedencia[chave] = {
        origem: 'fallback de premissas.json',
        referencia: premissasArquivo.atualizado_em,
        detalhe: campo?.detalhe || erroRetrato || 'retrato de mercado indisponível',
      };
      degradado = true;
    }
  }

  const idade = diasDesde(retrato?.coletado_em);
  final.tr_am = base.tr_am || 0;
  final._origem = procedencia;
  final._degradado = degradado;
  final._coletado_em = retrato?.coletado_em || null;
  final._idade_dias = idade;
  final._vencido = idade !== null && idade > DIAS_ATE_VENCER;
  return final;
}

export const SERIES_HISTORICAS = ['cdi', 'selic', 'ipca', 'poupanca'];

/** Série histórica mensal real, acumulada a partir do primeiro ponto. */
export async function historico(serieNome, meses = 60) {
  if (!SERIES_HISTORICAS.includes(serieNome)) {
    throw new Error(`Série "${serieNome}" indisponível. Opções: ${SERIES_HISTORICAS.join(', ')}`);
  }
  const arquivo = await lerJson(CAMINHOS.serie(serieNome));

  // O mês corrente é publicado parcial pelo BCB: incluí-lo desenharia uma
  // queda falsa no último ponto.
  const mesAtual = new Date().toISOString().slice(0, 7);
  const pontos = arquivo.pontos
    .filter((p) => p.data.slice(0, 7) !== mesAtual)
    .slice(-meses);
  if (!pontos.length) throw new Error(`Série "${serieNome}" sem meses fechados disponíveis`);

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
    serie: serieNome,
    rotulo: arquivo.rotulo,
    fonte: arquivo.fonte,
    serie_sgs: arquivo.serie_sgs,
    coletado_em: arquivo.coletado_em,
    meses_disponiveis: arquivo.pontos.length,
    pontos: acumulado,
    acumulado_total_pct: acumulado[acumulado.length - 1].acumulado_pct,
  };
}
