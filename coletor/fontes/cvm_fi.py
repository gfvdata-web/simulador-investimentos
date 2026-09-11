"""Cliente do Portal de Dados Abertos da CVM - Informe Diario de Fundos (FI).

Fonte oficial, publica e de acesso livre:
    https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{aaaamm}.zip

Cobre fundos de investimento comuns (classe "FI"/"CLASSES - FIF" da CVM) - os
fundos comercializados direto por banco/gestora, sem ticker de bolsa (por isso
nao aparecem no COTAHIST da B3). Cada arquivo e MENSAL (nao anual, diferente de
FII e B3) e cobre o mercado inteiro; uma consulta filtra por CNPJ depois de
baixar o mes.

Diferente do informe de FII, aqui a CVM so publica o valor da cota
(VL_QUOTA) - o retorno estimado e calculado por este projeto a partir dessa
serie, mesmo metodo do ETF (ver b3_precos.py e docs/04): CAGR mensal composto
+/- desvio-padrao como cenario.

Janela mais curta que FII/ETF (12 meses, nao 36): cada mes baixado e um
arquivo do mercado inteiro (~10-15 MB), entao 36 meses seria pesado demais
pra rodar toda semana. Compromisso deliberado, nao limitacao de dado - ver
docs/04.

Regra do projeto: este modulo NUNCA inventa numero.
"""
from __future__ import annotations

import csv
import functools
import io
import urllib.error
import urllib.request
import zipfile
from datetime import date

NOME = "CVM - Dados Abertos (Informe Diário de Fundos)"
BASE = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{aaaamm}.zip"
TIMEOUT = 60
TENTATIVAS = 3


class FalhaFonte(Exception):
    """A fonte oficial nao respondeu ou respondeu algo inesperado."""


def _meses_fechados(quantidade: int) -> list:
    """Os `quantidade` meses fechados mais recentes (AAAAMM), sem o mes corrente
    - ele vem parcial e a CVM as vezes ainda nem publicou o arquivo dele."""
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    meses = []
    for _ in range(quantidade):
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
        meses.append(f"{ano}{mes:02d}")
    return list(reversed(meses))


@functools.lru_cache(maxsize=None)
def _baixar(aaaamm: str) -> bytes:
    """Cacheado em memoria por mes: o arquivo cobre o mercado inteiro, entao uma
    coleta com varios fundos no mesmo mes baixa o arquivo uma vez so."""
    url = BASE.format(aaaamm=aaaamm)
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
                raise FalhaFonte(f"CVM informe diario FI {aaaamm}: {erro}") from erro
    raise FalhaFonte(f"CVM informe diario FI {aaaamm}: {ultimo_erro}")  # pragma: no cover


def _linhas_mes(aaaamm: str):
    bruto = _baixar(aaaamm)
    try:
        arquivo = zipfile.ZipFile(io.BytesIO(bruto))
        nome_membro = arquivo.namelist()[0]
    except (zipfile.BadZipFile, IndexError) as erro:
        raise FalhaFonte(f"CVM informe diario FI {aaaamm}: arquivo inesperado ({erro})") from erro
    with arquivo.open(nome_membro) as membro:
        texto = io.TextIOWrapper(membro, encoding="latin-1", newline="")
        yield from csv.DictReader(texto, delimiter=";")


def cotas_diarias(cnpj: str, meses: int = 12) -> list:
    """Valor da cota diario de um fundo, pelo CNPJ.

    [{'data': 'YYYY-MM-DD', 'valor_cota': float}], crescente por data.
    """
    cnpj = cnpj.strip()
    pontos = []
    falhas = []
    for aaaamm in _meses_fechados(meses):
        try:
            for linha in _linhas_mes(aaaamm):
                if linha.get("CNPJ_FUNDO_CLASSE", "").strip() != cnpj:
                    continue
                pontos.append({
                    "data": linha["DT_COMPTC"].strip(),
                    "valor_cota": float(linha["VL_QUOTA"]),
                })
        except FalhaFonte as erro:
            falhas.append(str(erro))

    if not pontos:
        detalhe = "; ".join(falhas) if falhas else "CNPJ nao encontrado no informe diario"
        raise FalhaFonte(f"CVM: sem dados para o CNPJ {cnpj} ({detalhe})")

    pontos.sort(key=lambda p: p["data"])
    return pontos


def cotas_mensais(cnpj: str, meses: int = 12) -> list:
    """Ultima cota de cada mes, com a variacao percentual sobre o mes anterior."""
    diarios = cotas_diarias(cnpj, meses)
    por_mes = {}
    for ponto in diarios:
        por_mes[ponto["data"][:7]] = ponto  # sobrescreve ate sobrar a ultima cota do mes

    mensal = []
    anterior = None
    for chave in sorted(por_mes):
        ponto = por_mes[chave]
        variacao = None
        if anterior is not None:
            variacao = round((ponto["valor_cota"] / anterior - 1) * 100, 4)
        mensal.append({
            "data": ponto["data"],
            "valor_cota": ponto["valor_cota"],
            "variacao_mes_pct": variacao,
        })
        anterior = ponto["valor_cota"]
    return mensal
