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
avisa quem chamou, e o chamador decide se usa o fallback das premissas.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date

from . import cache

BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
TIMEOUT = 12
TTL_PADRAO = 6 * 60 * 60  # 6 horas

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


def _buscar(codigo: int, ultimos: int) -> list[dict]:
    url = BASE.format(codigo=codigo) + f"/ultimos/{ultimos}?formato=json"
    requisicao = urllib.request.Request(
        url, headers={"User-Agent": "SimuladorInvestimentos/1.0 (uso pessoal)"}
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=TIMEOUT) as resposta:
            bruto = resposta.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise FalhaFonte(f"SGS {codigo}: {erro}") from erro
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise FalhaFonte(f"SGS {codigo}: resposta nao e JSON") from erro
    if not isinstance(dados, list) or not dados:
        raise FalhaFonte(f"SGS {codigo}: serie vazia")
    return dados


def serie(nome: str, ultimos: int = 60, ttl: int = TTL_PADRAO) -> list[dict]:
    """Serie historica normalizada: [{'data': 'YYYY-MM-DD', 'valor': float}]."""
    if nome not in SERIES:
        raise FalhaFonte(f"Serie desconhecida: {nome}")
    chave = f"sgs-{nome}-{ultimos}"
    cacheado = cache.ler(chave, ttl)
    if cacheado is not None:
        return cacheado

    bruto = _buscar(SERIES[nome], ultimos)
    normalizada = []
    for item in bruto:
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
    cache.gravar(chave, normalizada)
    return normalizada


def ultimo(nome: str, ttl: int = TTL_PADRAO) -> dict:
    return serie(nome, ultimos=1, ttl=ttl)[-1]


def ipca_acumulado_12m(ttl: int = TTL_PADRAO) -> float:
    """Compoe os 12 ultimos IPCAs mensais em uma taxa acumulada (% a.a.)."""
    pontos = serie("ipca_mensal", ultimos=12, ttl=ttl)
    fator = 1.0
    for ponto in pontos:
        fator *= 1 + ponto["valor"] / 100
    return round((fator - 1) * 100, 4)


def indicadores(ttl: int = TTL_PADRAO) -> dict:
    """Fotografia atual dos indicadores. Cada campo carrega sua origem.

    Nunca levanta excecao: campos que falharem voltam com origem 'indisponivel'
    e valor None, para o chamador aplicar o fallback das premissas.
    """
    resultado = {"origem": "bcb", "consultado_em": date.today().isoformat(), "campos": {}}

    def tentar(chave, funcao):
        try:
            resultado["campos"][chave] = funcao()
        except FalhaFonte as erro:
            resultado["campos"][chave] = {
                "valor": None,
                "origem": "indisponivel",
                "detalhe": str(erro),
            }

    tentar("cdi_aa", lambda: _campo("cdi_aa", ultimo("cdi_aa", ttl), 4389))
    tentar("selic_meta_aa", lambda: _campo("selic_meta_aa", ultimo("selic_meta_aa", ttl), 432))
    tentar("poupanca_am", lambda: _campo("poupanca_am", ultimo("poupanca_mensal", ttl), 196))
    tentar(
        "ipca_12m",
        lambda: {
            "valor": ipca_acumulado_12m(ttl),
            "origem": "bcb",
            "serie_sgs": 433,
            "referencia": serie("ipca_mensal", 12, ttl)[-1]["data"],
        },
    )

    if all(c.get("origem") == "indisponivel" for c in resultado["campos"].values()):
        resultado["origem"] = "indisponivel"
    return resultado


def _campo(_nome: str, ponto: dict, codigo: int) -> dict:
    return {
        "valor": ponto["valor"],
        "origem": "bcb",
        "serie_sgs": codigo,
        "referencia": ponto["data"],
    }
