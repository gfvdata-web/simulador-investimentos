"""Coletor de dados de mercado.

Le as fontes oficiais e grava um retrato em dados/mercado/. A pagina do
simulador nunca fala com a internet: ela le esses arquivos, que sao versionados
no git. Isso deixa cada simulacao auditavel (da para ver no historico do
repositorio exatamente qual CDI foi usado em cada dia) e faz o site funcionar
mesmo se a fonte estiver fora do ar.

    python coletor/atualizar.py
    python coletor/atualizar.py --meses 120 --so cdi_aa,ipca_12m

PARA ACRESCENTAR UM INDICADOR OU UMA SERIE, edite so os registros INDICADORES e
SERIES logo abaixo. O retrato gravado carrega rotulo e unidade de cada item, e a
pagina se monta a partir disso - nao ha lista de indicadores escrita na mao do
lado do navegador. Fonte nova: crie o modulo em coletor/fontes/ seguindo o
protocolo documentado em PROTOCOLO_FONTE e registre em FONTES.

PARA ACRESCENTAR UM FUNDO (FII ou ETF negociado em bolsa), edite o registro
FUNDOS logo abaixo. Esses tem um formato proprio (nao o PROTOCOLO_FONTE
generico): FII grava dividend yield e valorizacao patrimonial publicados pela
CVM; ETF grava fechamento da B3 e calcula a variacao. Ver `coletar_fundos` e
docs/04-fontes-de-dados.md.

Se uma fonte falhar, o dado anterior e PRESERVADO: dado velho com data visivel e
melhor que dado ausente, e muito melhor que dado inventado.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fontes import b3_precos, bcb_sgs, cvm_fii  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
DIR_MERCADO = RAIZ / "dados" / "mercado"
DIR_SERIES = DIR_MERCADO / "series"
DIR_FUNDOS = DIR_MERCADO / "fundos"

MESES_PADRAO = 120

# Convencao do arquivo: identificadores e comentarios sem acento (o CI roda com
# locale imprevisivel), mas 'rotulo' e texto que aparece na tela do usuario e
# leva acentuacao normal - ele viaja como dado UTF-8 para o JSON.

PROTOCOLO_FONTE = """
Um modulo de fonte precisa expor:
    FalhaFonte              excecao levantada quando a fonte nao responde
    ultimo(nome) -> dict    {'data': 'YYYY-MM-DD', 'valor': float}
    serie(nome, meses)      [{'data': ..., 'valor': ...}], crescente por data
    NOME                    nome legivel da fonte, usado na tela
Nada de inventar valor: se falhar, levante FalhaFonte.
"""

FONTES = {
    "bcb": bcb_sgs,
    "cvm_fii": cvm_fii,
    "b3": b3_precos,
}

# --- Indicadores: o valor "de hoje" de cada referencia do mercado -----------
# agregacao: 'ultimo' pega o ponto mais recente; 'acumulado_12m' compoe os 12
# ultimos pontos mensais em uma taxa anual.
INDICADORES = {
    "cdi_aa": {
        "fonte": "bcb", "serie": "cdi_aa", "agregacao": "ultimo",
        "rotulo": "CDI", "unidade": "% a.a.", "referencia_fonte": 4389,
    },
    "selic_meta_aa": {
        "fonte": "bcb", "serie": "selic_meta_aa", "agregacao": "ultimo",
        "rotulo": "Selic meta", "unidade": "% a.a.", "referencia_fonte": 432,
    },
    "ipca_12m": {
        "fonte": "bcb", "serie": "ipca_mensal", "agregacao": "acumulado_12m",
        "rotulo": "IPCA 12 meses", "unidade": "%", "referencia_fonte": 433,
    },
    "poupanca_am": {
        "fonte": "bcb", "serie": "poupanca_mensal", "agregacao": "ultimo",
        "rotulo": "Poupança", "unidade": "% a.m.", "referencia_fonte": 196,
    },
}

# --- Series historicas mensais publicadas para a aba de historico ----------
SERIES = {
    "cdi": {
        "fonte": "bcb", "serie": "cdi_mensal", "referencia_fonte": 4391,
        "rotulo": "CDI acumulado no mês", "rotulo_curto": "CDI",
    },
    "selic": {
        "fonte": "bcb", "serie": "selic_mensal", "referencia_fonte": 4390,
        "rotulo": "Selic acumulada no mês", "rotulo_curto": "Selic",
    },
    "ipca": {
        "fonte": "bcb", "serie": "ipca_mensal", "referencia_fonte": 433,
        "rotulo": "IPCA mensal", "rotulo_curto": "IPCA",
    },
    "poupanca": {
        "fonte": "bcb", "serie": "poupanca_mensal", "referencia_fonte": 196,
        "rotulo": "Rendimento da poupança", "rotulo_curto": "Poupança",
    },
}


# --- Fundos negociados em bolsa (FII e ETF) ---------------------------------
# FII: a fonte e o informe mensal da CVM, que ja publica dividend yield e
# valorizacao patrimonial como FATO (nao e este projeto que calcula). ETF: a
# CVM nao publica esse informe para fundo de indice, entao a fonte e o preco
# de fechamento da B3 (COTAHIST) e a valorizacao e calculada aqui - o metodo
# fica descrito no proprio 'resumo' gravado, nunca escondido.
#
# `cnpj` identifica o FII na CVM (fundo/classe). Tickers verificados a mao em
# 2026-09-10 batendo CNPJ (CVM) x ISIN (B3 COTAHIST) - ver docs/04.
FUNDOS = {
    "VILG11": {"tipo": "fii", "cnpj": "24.853.044/0001-22",
               "rotulo": "VILG11 (Vinci Logística FII)", "segmento": "Logística"},
    "ALZR11": {"tipo": "fii", "cnpj": "28.737.771/0001-85",
               "rotulo": "ALZR11 (Alianza Trust Renda Imobiliária FII)", "segmento": "Híbrido"},
    "BTLG11": {"tipo": "fii", "cnpj": "11.839.593/0001-09",
               "rotulo": "BTLG11 (BTG Pactual Logística FII)", "segmento": "Logística"},
    "GGRC11": {"tipo": "fii", "cnpj": "26.614.291/0001-00",
               "rotulo": "GGRC11 (GGR Covepi Renda FII)", "segmento": "Logística"},
    "RECR11": {"tipo": "fii", "cnpj": "28.152.272/0001-26",
               "rotulo": "RECR11 (REC Recebíveis Imobiliários FII)", "segmento": "Papel (CRI)"},
    "HGLG11": {"tipo": "fii", "cnpj": "11.728.688/0001-47",
               "rotulo": "HGLG11 (Pátria Logística FII, ex-CSHG Logística)", "segmento": "Logística"},
    "XPLG11": {"tipo": "fii", "cnpj": "26.502.794/0001-85",
               "rotulo": "XPLG11 (XP Log FII)", "segmento": "Logística"},
    "KNCR11": {"tipo": "fii", "cnpj": "16.706.958/0001-32",
               "rotulo": "KNCR11 (Kinea Rendimentos Imobiliários FII)", "segmento": "Papel (pós-CDI)"},
    "DIVO11": {"tipo": "etf", "rotulo": "DIVO11 (It Now IDIV)", "indice": "IDIV (dividendos B3)"},
    "GOLD11": {"tipo": "etf", "rotulo": "GOLD11 (Trend Ouro)", "indice": "ouro (commodity)"},
    "WRLD11": {"tipo": "etf", "rotulo": "WRLD11 (Investo MSCI World)", "indice": "MSCI World"},
    "XINA11": {"tipo": "etf", "rotulo": "XINA11 (XP ETF China)", "indice": "ações chinesas"},
    "NASD11": {"tipo": "etf", "rotulo": "NASD11 (Trend Nasdaq)", "indice": "Nasdaq-100"},
}

JANELA_FUNDOS_MESES = 36


def _media(valores: list):
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if valores else None


def _desvio_padrao(valores: list, media: float) -> float:
    valores = [v for v in valores if v is not None]
    if len(valores) < 2:
        return 0.0
    variancia = sum((v - media) ** 2 for v in valores) / (len(valores) - 1)
    return variancia ** 0.5


def _mes_corrente_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _resumo_fii(pontos: list) -> dict:
    """DY e valorizacao sao FATOS ja publicados pela CVM: o resumo so faz a
    media/desvio da janela, sem projetar nada. Quem projeta e o motor (app/
    nucleo/indexadores.js), e so quando o usuario liga a projeção de valorização."""
    dys = [p["dividend_yield_pct"] for p in pontos]
    valorizacoes = [p["valorizacao_patrimonial_pct"] for p in pontos]
    dy_medio = _media(dys) or 0.0
    valorizacao_media = _media(valorizacoes) or 0.0
    return {
        "janela_meses": len(pontos),
        "dividend_yield_am_medio_pct": round(dy_medio, 4),
        "valorizacao_patrimonial_am_media_pct": round(valorizacao_media, 4),
        "valorizacao_patrimonial_am_desvio_pct": round(_desvio_padrao(valorizacoes, valorizacao_media), 4),
        "referencia": pontos[-1]["data"],
        "metodo": "Média simples dos meses fechados publicados pela CVM (Informe Mensal FII).",
    }


def _resumo_etf(pontos: list) -> dict:
    """ETF nao tem informe de rendimento na CVM: a 'estimativa' aqui e CAGR
    historico de preco +/- 1 desvio-padrao anualizado, tudo calculado a partir
    do fechamento da B3 - nunca um numero digitado a mao (regra 1 do CLAUDE.md)."""
    fechados = [p for p in pontos if p["data"][:7] != _mes_corrente_iso()]
    variacoes = [p["variacao_mes_pct"] for p in fechados if p["variacao_mes_pct"] is not None]
    media_am = _media(variacoes) or 0.0
    desvio_am = _desvio_padrao(variacoes, media_am)
    base_aa = ((1 + media_am / 100) ** 12 - 1) * 100
    desvio_aa = desvio_am * (12 ** 0.5)
    referencia = fechados[-1]["data"] if fechados else pontos[-1]["data"]
    return {
        "janela_meses": len(variacoes),
        "retorno_am_medio_pct": round(media_am, 4),
        "retorno_aa": {
            "pessimista": round(base_aa - desvio_aa, 2),
            "base": round(base_aa, 2),
            "otimista": round(base_aa + desvio_aa, 2),
        },
        "volatilidade_aa": round(desvio_aa, 2),
        "referencia": referencia,
        "metodo": ("CAGR mensal composto do fechamento (B3 COTAHIST) sobre os meses "
                   "fechados da janela, +/- 1 desvio-padrão anualizado (desvio mensal x "
                   "raiz de 12). O mês corrente, ainda em curso, é excluído da média."),
    }


def _entrada_manifesto_fundo(ticker: str, definicao: dict, conteudo: dict) -> dict:
    pontos = conteudo.get("pontos") or []
    return {
        "ticker": ticker,
        "tipo": definicao["tipo"],
        "rotulo": definicao["rotulo"],
        "arquivo": f"fundos/{ticker}.json",
        "pontos": len(pontos),
        "primeiro": pontos[0]["data"] if pontos else None,
        "ultimo": pontos[-1]["data"] if pontos else None,
        "coletado_em": conteudo.get("coletado_em"),
    }


def coletar_fundos(quais: set, relatorio: list) -> list:
    """FII e ETF negociados em bolsa. Grava um arquivo por ticker em
    dados/mercado/fundos/ e devolve o manifesto para indicadores.json - mesma
    filosofia de degradação das séries: falha na coleta preserva o arquivo
    anterior, nunca apaga o que já existia."""
    manifesto = []
    for ticker, definicao in FUNDOS.items():
        if quais and ticker not in quais:
            continue
        caminho = DIR_FUNDOS / f"{ticker}.json"
        try:
            if definicao["tipo"] == "fii":
                pontos = cvm_fii.informe_mensal(definicao["cnpj"], meses=JANELA_FUNDOS_MESES)
                resumo = _resumo_fii(pontos)
                fonte = cvm_fii.NOME
            else:
                pontos = b3_precos.fechamentos_mensais(ticker, anos=max(3, JANELA_FUNDOS_MESES // 12))
                resumo = _resumo_etf(pontos)
                fonte = b3_precos.NOME
        except (cvm_fii.FalhaFonte, b3_precos.FalhaFonte) as erro:
            relatorio.append(f"  FALHA fundo {ticker}: {erro} (arquivo anterior preservado)")
            if caminho.exists():
                try:
                    anterior = json.loads(caminho.read_text(encoding="utf-8"))
                    manifesto.append(_entrada_manifesto_fundo(ticker, definicao, anterior))
                except json.JSONDecodeError:
                    pass
            continue

        conteudo = {
            "ticker": ticker,
            **definicao,
            "fonte": fonte,
            "coletado_em": agora(),
            "pontos": pontos,
            "resumo": resumo,
        }
        gravar(caminho, conteudo)
        manifesto.append(_entrada_manifesto_fundo(ticker, definicao, conteudo))
        relatorio.append(f"  ok    fundo {ticker}: {len(pontos)} pontos, referência {resumo['referencia']}")

    return manifesto


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def gravar(caminho: Path, conteudo: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def modulo_da(definicao: dict):
    nome = definicao["fonte"]
    if nome not in FONTES:
        raise KeyError(f"Fonte '{nome}' nao registrada em FONTES")
    return FONTES[nome]


def coletar_indicadores(quais: set, relatorio: list) -> dict:
    campos = {}
    for chave, definicao in INDICADORES.items():
        if quais and chave not in quais:
            continue
        modulo = modulo_da(definicao)
        # Metadados vao para o arquivo mesmo quando a coleta falha: a pagina
        # precisa saber rotular o campo para poder avisar que ele esta vazio.
        meta = {
            "rotulo": definicao["rotulo"],
            "unidade": definicao["unidade"],
            "fonte": modulo.NOME,
            "referencia_fonte": definicao.get("referencia_fonte"),
        }
        try:
            if definicao["agregacao"] == "acumulado_12m":
                bruto = modulo.acumulado_12m(definicao["serie"])
            else:
                ponto = modulo.ultimo(definicao["serie"])
                bruto = {"valor": ponto["valor"], "referencia": ponto["data"]}
            campos[chave] = {**meta, "valor": bruto["valor"],
                             "origem": "fonte oficial", "referencia": bruto["referencia"]}
            relatorio.append(f"  ok    {chave} = {bruto['valor']} {definicao['unidade']}")
        except modulo.FalhaFonte as erro:
            campos[chave] = {**meta, "valor": None, "origem": "indisponivel", "detalhe": str(erro)}
            relatorio.append(f"  FALHA {chave}: {erro}")
    return campos


def herdar_do_anterior(campos: dict, anterior: dict, relatorio: list) -> dict:
    """Campo que falhou fica com o valor do retrato anterior, marcado como tal."""
    for chave, campo in campos.items():
        if campo.get("valor") is not None:
            continue
        antigo = (anterior.get("campos") or {}).get(chave)
        if antigo and antigo.get("valor") is not None:
            campos[chave] = {
                **campo,
                "valor": antigo["valor"],
                "referencia": antigo.get("referencia"),
                "origem": "retrato anterior (fonte indisponivel na ultima coleta)",
                "coletado_em": anterior.get("coletado_em"),
            }
            relatorio.append(f"  herda {chave} do retrato de {anterior.get('coletado_em')}")
    return campos


def coletar_series(meses: int, quais: set, relatorio: list, anterior: dict) -> list:
    manifesto = []
    indice_anterior = {s["id"]: s for s in (anterior.get("series") or [])}

    for nome, definicao in SERIES.items():
        if quais and nome not in quais:
            continue
        caminho = DIR_SERIES / f"{nome}.json"
        modulo = modulo_da(definicao)
        entrada = {
            "id": nome,
            "rotulo": definicao["rotulo"],
            "rotulo_curto": definicao["rotulo_curto"],
            "arquivo": f"series/{nome}.json",
            "fonte": modulo.NOME,
            "referencia_fonte": definicao.get("referencia_fonte"),
        }
        try:
            pontos = modulo.serie(definicao["serie"], meses=meses)
        except modulo.FalhaFonte as erro:
            relatorio.append(f"  FALHA serie {nome}: {erro} (arquivo anterior preservado)")
            if caminho.exists() and nome in indice_anterior:
                manifesto.append(indice_anterior[nome])
            continue

        gravar(caminho, {**entrada, "coletado_em": agora(), "pontos": pontos})
        manifesto.append({**entrada, "pontos": len(pontos),
                          "primeiro": pontos[0]["data"], "ultimo": pontos[-1]["data"]})
        relatorio.append(f"  ok    serie {nome}: {len(pontos)} pontos ate {pontos[-1]['data']}")

    return manifesto


def main() -> int:
    parser = argparse.ArgumentParser(description="Atualiza os dados de mercado")
    parser.add_argument("--meses", type=int, default=MESES_PADRAO,
                        help=f"quantos meses de historico buscar (padrao {MESES_PADRAO})")
    parser.add_argument("--so", default="",
                        help="coleta so estes indicadores/series, separados por virgula")
    args = parser.parse_args()
    quais = {p.strip() for p in args.so.split(",") if p.strip()}

    caminho = DIR_MERCADO / "indicadores.json"
    anterior = {}
    if caminho.exists():
        try:
            anterior = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    relatorio = [f"Coleta iniciada em {agora()}"]
    campos = herdar_do_anterior(coletar_indicadores(quais, relatorio), anterior, relatorio)
    series = coletar_series(args.meses, quais, relatorio, anterior)
    fundos = coletar_fundos(quais, relatorio)

    # Coleta parcial (--so) nao pode apagar o que ja estava no retrato.
    if quais:
        campos = {**(anterior.get("campos") or {}), **campos}
        ids = {s["id"] for s in series}
        series = series + [s for s in (anterior.get("series") or []) if s["id"] not in ids]
        tickers = {f["ticker"] for f in fundos}
        fundos = fundos + [f for f in (anterior.get("fundos") or []) if f["ticker"] not in tickers]

    vivos = sum(1 for c in campos.values() if c.get("valor") is not None)
    gravar(caminho, {
        "coletado_em": agora(),
        "completo": vivos == len(campos) and len(series) == len(SERIES) and len(fundos) == len(FUNDOS),
        "campos": campos,
        "series": series,
        "fundos": fundos,
    })
    relatorio.append(
        f"  {vivos}/{len(campos)} indicadores com valor, {len(series)} serie(s), {len(fundos)} fundo(s)"
    )

    print("\n".join(relatorio))
    if vivos == 0:
        print("\nNenhum indicador coletado. Falhando para o Actions avisar.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
