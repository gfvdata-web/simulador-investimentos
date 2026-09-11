"""Cliente das Series Historicas da B3 (COTAHIST).

Fonte oficial, publica e de acesso livre, sem chave nem login:
    https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP

Cada arquivo anual traz, em layout de largura fixa, o preco de fechamento de
todo instrumento negociado na B3 em cada pregao do ano. Usado aqui para ETFs,
que a CVM nao publica com informe de rendimento como faz para FII (ver
docs/04-fontes-de-dados.md): a valorizacao de um ETF e calculada por este
projeto a partir do preco de fechamento, e o metodo fica documentado no
`resumo` gravado pelo coletor, nunca escondido atras de um numero pronto.

Layout usado (posicoes 0-based, validado contra o manual "SeriesHistoricas"
da B3 e conferido linha a linha durante o desenvolvimento):
    [0:2]     TIPREG    '01' = registro de cotacao (ignora cabecalho e rodape)
    [2:10]    DATA_PREGAO  AAAAMMDD
    [12:24]   CODNEG    codigo de negociacao (ticker), ex. 'VILG11'
    [24:27]   TPMERC    tipo de mercado; '010' = mercado a vista, lote padrao
    [108:121] PREULT    preco de fechamento, 2 casas decimais implicitas

Regra do projeto: este modulo NUNCA inventa numero. Se a rede falhar ou o
ticker nao aparecer no periodo, ele avisa quem chamou.
"""
from __future__ import annotations

import functools
import io
import urllib.error
import urllib.request
import zipfile
from datetime import date

NOME = "B3 - Séries Históricas (COTAHIST)"
BASE = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP"
TIMEOUT = 60
TENTATIVAS = 3
ANOS_PADRAO = 3


class FalhaFonte(Exception):
    """A fonte oficial nao respondeu ou respondeu algo inesperado."""


@functools.lru_cache(maxsize=None)
def _baixar(ano: int) -> bytes:
    """Cacheado em memoria por ano: o arquivo cobre o mercado inteiro, entao
    uma coleta com varios tickers no mesmo ano baixa o arquivo uma vez so."""
    url = BASE.format(ano=ano)
    requisicao = urllib.request.Request(
        url, headers={"User-Agent": "SimuladorInvestimentos/1.0 (uso pessoal)"}
    )
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(requisicao, timeout=TIMEOUT) as resposta:
                return resposta.read()
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            ultimo_erro = erro
            if tentativa == TENTATIVAS:
                raise FalhaFonte(f"B3 COTAHIST {ano}: {erro}") from erro
    raise FalhaFonte(f"B3 COTAHIST {ano}: {ultimo_erro}")  # pragma: no cover


def _linhas_ano(ano: int):
    bruto = _baixar(ano)
    try:
        arquivo = zipfile.ZipFile(io.BytesIO(bruto))
        nome_membro = next(n for n in arquivo.namelist() if n.upper().endswith(".TXT"))
    except (zipfile.BadZipFile, StopIteration) as erro:
        raise FalhaFonte(f"B3 COTAHIST {ano}: arquivo inesperado ({erro})") from erro
    with arquivo.open(nome_membro) as membro:
        for linha in io.TextIOWrapper(membro, encoding="latin-1"):
            if linha[:2] == "01":
                yield linha


def fechamentos_diarios(ticker: str, anos: int = ANOS_PADRAO) -> list:
    """Fechamentos diarios de um ticker no mercado a vista, lote padrao.

    [{'data': 'YYYY-MM-DD', 'fechamento': float}], crescente por data.
    """
    ticker = ticker.strip().upper()
    ano_atual = date.today().year
    inicio = max(ano_atual - anos, ano_atual - 10)

    pontos = []
    falhas = []
    for ano in range(inicio, ano_atual + 1):
        try:
            for linha in _linhas_ano(ano):
                if linha[12:24].strip() != ticker or linha[24:27] != "010":
                    continue
                pontos.append({
                    "data": f"{linha[2:6]}-{linha[6:8]}-{linha[8:10]}",
                    "fechamento": int(linha[108:121]) / 100,
                })
        except FalhaFonte as erro:
            falhas.append(str(erro))

    if not pontos:
        detalhe = "; ".join(falhas) if falhas else "ticker sem pregao no periodo"
        raise FalhaFonte(f"B3 COTAHIST: sem dados para {ticker} ({detalhe})")

    pontos.sort(key=lambda p: p["data"])
    return pontos


def fechamentos_mensais(ticker: str, anos: int = ANOS_PADRAO) -> list:
    """Ultimo pregao de cada mes, com a variacao percentual sobre o mes anterior.

    [{'data', 'fechamento', 'variacao_mes_pct'}], crescente. O primeiro ponto
    fica com `variacao_mes_pct: None` (nao ha mes anterior no periodo baixado).
    """
    diarios = fechamentos_diarios(ticker, anos)
    por_mes = {}
    for ponto in diarios:
        por_mes[ponto["data"][:7]] = ponto  # sobrescreve ate sobrar o ultimo pregao do mes

    mensal = []
    fechamento_anterior = None
    for chave in sorted(por_mes):
        ponto = por_mes[chave]
        variacao = None
        if fechamento_anterior is not None:
            variacao = round((ponto["fechamento"] / fechamento_anterior - 1) * 100, 4)
        mensal.append({
            "data": ponto["data"],
            "fechamento": ponto["fechamento"],
            "variacao_mes_pct": variacao,
        })
        fechamento_anterior = ponto["fechamento"]
    return mensal


def serie(ticker: str, meses: int = 60) -> list:
    """Protocolo padrao de fonte (ver PROTOCOLO_FONTE em coletor/atualizar.py),
    para consulta pontual de preco: 'valor' aqui e o fechamento em R$."""
    mensal = fechamentos_mensais(ticker, anos=max(3, -(-meses // 12)))
    return [{"data": p["data"], "valor": p["fechamento"]} for p in mensal[-meses:]]


def ultimo(ticker: str) -> dict:
    ponto = serie(ticker, meses=1)[-1]
    return ponto
