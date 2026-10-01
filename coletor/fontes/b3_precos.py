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

Download: o arquivo anual tem ~90 MB e a conexao com a B3 cai no meio com
frequencia (IncompleteRead). Por isso ele vem em blocos e, se cair, a proxima
tentativa pede so o que falta (cabecalho Range; a B3 responde 206). Ha tambem
um prazo total por arquivo: o TIMEOUT vale para cada leitura, e um download
lento mas vivo ja estourou o limite de 6 h do Actions. Cada queda e cada
retomada saem no log (no Actions, como anotacao ::warning:: da execucao).
"""
from __future__ import annotations

import functools
import http.client
import io
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date

NOME = "B3 - Séries Históricas (COTAHIST)"
BASE = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP"
TIMEOUT = 60  # segundos por leitura
TENTATIVAS = 8  # cada uma retoma de onde a anterior parou
PRAZO_ARQUIVO_S = 20 * 60  # prazo total para baixar um arquivo anual
BLOCO = 1024 * 1024
ANOS_PADRAO = 3

ERROS_DOWNLOAD = (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError)


class FalhaFonte(Exception):
    """A fonte oficial nao respondeu ou respondeu algo inesperado."""


class ArquivoInexistente(FalhaFonte):
    """A B3 ainda nao publicou o arquivo do ano (HTTP 404, comum no inicio de janeiro)."""


def _avisar(mensagem: str) -> None:
    """Aviso no log; no Actions vira anotacao da execucao (aparece no resumo do run)."""
    prefixo = "::warning::" if os.environ.get("GITHUB_ACTIONS") == "true" else "aviso: "
    print(f"{prefixo}{mensagem}", file=sys.stderr, flush=True)


def _tamanho_total(resposta) -> int | None:
    """Tamanho do arquivo inteiro: Content-Range numa resposta 206, Content-Length numa 200."""
    faixa = resposta.headers.get("Content-Range")  # "bytes 1000-88999/89000"
    if faixa and "/" in faixa:
        total = faixa.rsplit("/", 1)[1]
        return int(total) if total.isdigit() else None
    tamanho = resposta.headers.get("Content-Length")
    return int(tamanho) if tamanho and tamanho.isdigit() else None


@functools.lru_cache(maxsize=None)
def _baixar(ano: int) -> bytes:
    """Cacheado em memoria por ano: o arquivo cobre o mercado inteiro, entao
    uma coleta com varios tickers no mesmo ano baixa o arquivo uma vez so."""
    url = BASE.format(ano=ano)
    dados = bytearray()
    total = None
    limite = time.monotonic() + PRAZO_ARQUIVO_S
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        cabecalhos = {"User-Agent": "SimuladorInvestimentos/1.0 (uso pessoal)"}
        if dados:
            cabecalhos["Range"] = f"bytes={len(dados)}-"
        requisicao = urllib.request.Request(url, headers=cabecalhos)
        try:
            with urllib.request.urlopen(requisicao, timeout=TIMEOUT) as resposta:
                if resposta.status != 206:
                    dados.clear()  # servidor ignorou o Range: recomeca do zero
                total = _tamanho_total(resposta) or total
                while bloco := resposta.read(BLOCO):
                    dados.extend(bloco)
                    if time.monotonic() > limite:
                        raise FalhaFonte(
                            f"B3 COTAHIST {ano}: download passou de {PRAZO_ARQUIVO_S // 60} min "
                            f"({len(dados)} de {total or '?'} bytes)"
                        )
            if total is None or len(dados) == total:
                if tentativa > 1:
                    _avisar(f"B3 COTAHIST {ano}: download completo na tentativa {tentativa} ({len(dados)} bytes)")
                return bytes(dados)
            ultimo_erro = "conexao fechada pelo servidor"
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                raise ArquivoInexistente(f"B3 COTAHIST {ano}: arquivo nao publicado (HTTP 404)") from erro
            ultimo_erro = erro
        except ERROS_DOWNLOAD as erro:  # inclui IncompleteRead: tenta de novo a partir do que ja chegou
            ultimo_erro = erro
        if time.monotonic() > limite:
            break
        if tentativa < TENTATIVAS:
            _avisar(
                f"B3 COTAHIST {ano}: tentativa {tentativa} caiu com {len(dados)} de {total or '?'} bytes "
                f"({ultimo_erro}); retomando"
            )
            time.sleep(min(2 ** tentativa, 30))
    raise FalhaFonte(
        f"B3 COTAHIST {ano}: {ultimo_erro} ({len(dados)} de {total or '?'} bytes apos {tentativa} tentativas)"
    )


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
    for ano in range(inicio, ano_atual + 1):
        # Qualquer FalhaFonte sobe (o download acontece antes da primeira linha):
        # um ano faltando no meio deixaria a serie com buraco, e a variacao mensal
        # atravessando o buraco - melhor falhar e quem chamou preservar o arquivo
        # anterior. Unica excecao: o ano corrente ainda sem arquivo publicado.
        try:
            for linha in _linhas_ano(ano):
                if linha[12:24].strip() != ticker or linha[24:27] != "010":
                    continue
                pontos.append({
                    "data": f"{linha[2:6]}-{linha[6:8]}-{linha[8:10]}",
                    "fechamento": int(linha[108:121]) / 100,
                })
        except ArquivoInexistente:
            if ano != ano_atual:
                raise

    if not pontos:
        raise FalhaFonte(f"B3 COTAHIST: sem dados para {ticker} (ticker sem pregao no periodo)")

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
