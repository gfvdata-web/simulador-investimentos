"""Cliente da API SGS do Banco Central do Brasil.

Fonte oficial, publica e de acesso livre:
    https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados

Series usadas (todas verificaveis no portal do BCB):
    4389 - CDI anualizado, base 252 (% a.a.)
    4391 - CDI acumulado no mes (% a.m.)
    432  - Meta Selic definida pelo Copom (% a.a.)
    4390 - Selic acumulada no mes (% a.m.)
    433  - IPCA - variacao mensal (% a.m.)
    196  - Poupanca, rendimento mensal, regra nova (% a.m.)
    226  - TR - taxa referencial mensal (% a.m.)

Regra do projeto: este modulo NUNCA inventa numero. Se a rede falhar ele
avisa quem chamou, e o chamador decide o que fazer.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, timedelta

BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
TIMEOUT = 20
TENTATIVAS = 3

SERIES = {
    "cdi_aa": 4389,
    "cdi_mensal": 4391,
    "selic_meta_aa": 432,
    "selic_mensal": 4390,
    "ipca_mensal": 433,
    "poupanca_mensal": 196,
    "tr_mensal": 226,
}


class FalhaFonte(Exception):
    """A fonte oficial nao respondeu ou respondeu algo inesperado."""


def _buscar(codigo: int, sufixo: str) -> list:
    url = BASE.format(codigo=codigo) + sufixo
    requisicao = urllib.request.Request(
        url, headers={"User-Agent": "SimuladorInvestimentos/1.0 (uso pessoal)"}
    )
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(requisicao, timeout=TIMEOUT) as resposta:
                bruto = resposta.read().decode("utf-8")
            break
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            ultimo_erro = erro
            if tentativa == TENTATIVAS:
                raise FalhaFonte(f"SGS {codigo}: {erro}") from erro
    else:  # pragma: no cover
        raise FalhaFonte(f"SGS {codigo}: {ultimo_erro}")

    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise FalhaFonte(f"SGS {codigo}: resposta nao e JSON") from erro
    if not isinstance(dados, list) or not dados:
        raise FalhaFonte(f"SGS {codigo}: serie vazia")
    return dados


def serie(nome: str, meses: int = 60) -> list:
    """Serie historica normalizada: [{'data': 'YYYY-MM-DD', 'valor': float}].

    Usa a consulta por intervalo de datas, e nao `/ultimos/N`: para as series
    mensais o endpoint `/ultimos/N` responde 400 para qualquer N acima de ~12.
    Ver docs/04-fontes-de-dados.md.
    """
    if nome not in SERIES:
        raise FalhaFonte(f"Serie desconhecida: {nome}")

    hoje = date.today()
    inicio = hoje - timedelta(days=int(meses * 31) + 31)
    sufixo = (
        f"?formato=json&dataInicial={inicio:%d/%m/%Y}&dataFinal={hoje:%d/%m/%Y}"
    )

    normalizada = []
    for item in _buscar(SERIES[nome], sufixo):
        try:
            dia, mes, ano = item["data"].split("/")
            normalizada.append(
                {
                    "data": f"{ano}-{mes}-{dia}",
                    "valor": float(str(item["valor"]).replace(",", ".")),
                }
            )
        except (KeyError, ValueError):
            continue
    if not normalizada:
        raise FalhaFonte(f"Serie {nome} veio sem pontos validos")

    # A API nao garante ordenacao: series mensais costumam vir da mais recente
    # para a mais antiga, as diarias ao contrario. Ordenamos sempre crescente
    # para que [-1] seja, de fato, o ponto mais recente.
    normalizada.sort(key=lambda p: p["data"])
    return normalizada


def ultimo(nome: str) -> dict:
    """Ponto mais recente. Aqui `/ultimos/1` e confiavel e evita baixar a serie."""
    if nome not in SERIES:
        raise FalhaFonte(f"Serie desconhecida: {nome}")
    item = _buscar(SERIES[nome], "/ultimos/1?formato=json")[-1]
    dia, mes, ano = item["data"].split("/")
    return {"data": f"{ano}-{mes}-{dia}", "valor": float(str(item["valor"]).replace(",", "."))}


def ipca_acumulado_12m() -> dict:
    """Compoe os 12 ultimos IPCAs mensais em uma taxa acumulada (% a.a.)."""
    pontos = serie("ipca_mensal", meses=13)[-12:]
    fator = 1.0
    for ponto in pontos:
        fator *= 1 + ponto["valor"] / 100
    return {"valor": round((fator - 1) * 100, 4), "referencia": pontos[-1]["data"]}
