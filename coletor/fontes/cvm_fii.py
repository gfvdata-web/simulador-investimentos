"""Cliente do Portal de Dados Abertos da CVM - Informe Mensal de FII.

Fonte oficial, publica e de acesso livre:
    https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip

O arquivo "complemento" desse pacote traz, por CNPJ de fundo/classe e mes,
tres fatos que a propria CVM calcula (nao um palpite deste projeto):
    Percentual_Dividend_Yield_Mes            dividendo distribuido / cota, no mes
    Percentual_Rentabilidade_Patrimonial_Mes variacao do valor patrimonial da cota
    Percentual_Rentabilidade_Efetiva_Mes      os dois combinados

Cada arquivo cobre um ano inteiro do mercado inteiro (todos os FIIs), entao
uma consulta filtra por CNPJ depois de baixar o ano. Historico disponivel
desde 2016.

Regra do projeto: este modulo NUNCA inventa numero. Se a rede falhar ou o
CNPJ nao aparecer no arquivo, ele avisa quem chamou.
"""
from __future__ import annotations

import csv
import functools
import io
import urllib.error
import urllib.request
import zipfile
from datetime import date

NOME = "CVM - Dados Abertos (Informe Mensal FII)"
BASE = "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip"
TIMEOUT = 40
TENTATIVAS = 3
PRIMEIRO_ANO = 2016


class FalhaFonte(Exception):
    """A fonte oficial nao respondeu ou respondeu algo inesperado."""


@functools.lru_cache(maxsize=None)
def _baixar(ano: int) -> bytes:
    """Cacheado em memoria por ano: uma coleta chama isto uma vez por FII, mas
    o arquivo do ano e o mercado inteiro - sem isto, 8 FIIs baixariam o mesmo
    zip 8 vezes."""
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
                raise FalhaFonte(f"CVM informe mensal FII {ano}: {erro}") from erro
    raise FalhaFonte(f"CVM informe mensal FII {ano}: {ultimo_erro}")  # pragma: no cover


def _linhas_complemento(ano: int):
    """Itera as linhas do CSV 'complemento' de um ano, ja como dict por coluna."""
    bruto = _baixar(ano)
    try:
        arquivo = zipfile.ZipFile(io.BytesIO(bruto))
        nome_membro = next(n for n in arquivo.namelist() if "complemento" in n.lower())
    except (zipfile.BadZipFile, StopIteration) as erro:
        raise FalhaFonte(f"CVM informe mensal FII {ano}: arquivo inesperado ({erro})") from erro
    with arquivo.open(nome_membro) as membro:
        texto = io.TextIOWrapper(membro, encoding="latin-1", newline="")
        yield from csv.DictReader(texto, delimiter=";")


def _numero(linha: dict, chave: str):
    bruto = (linha.get(chave) or "").strip()
    return float(bruto) if bruto else None


def _percentual(fracao):
    """CVM publica fracao (0.004342); o projeto usa ponto percentual (0.4342)."""
    return round(fracao * 100, 4) if fracao is not None else None


def _normalizar(linha: dict) -> dict:
    return {
        "data": linha["Data_Referencia"].strip(),
        "dividend_yield_pct": _percentual(_numero(linha, "Percentual_Dividend_Yield_Mes")),
        "valorizacao_patrimonial_pct": _percentual(
            _numero(linha, "Percentual_Rentabilidade_Patrimonial_Mes")
        ),
        "rentabilidade_efetiva_pct": _percentual(
            _numero(linha, "Percentual_Rentabilidade_Efetiva_Mes")
        ),
    }


def informe_mensal(cnpj: str, meses: int = 36) -> list:
    """Serie mensal normalizada de um FII, pelo CNPJ do fundo/classe.

    [{'data': 'YYYY-MM-DD', 'dividend_yield_pct', 'valorizacao_patrimonial_pct',
      'rentabilidade_efetiva_pct'}], crescente por data. `meses` controla quantos
    anos de arquivo baixar (cada arquivo e anual) e quantos pontos finais ficam.
    """
    cnpj = cnpj.strip()
    anos_necessarios = -(-max(meses, 1) // 12) + 1  # arredonda pra cima, +1 de folga
    ano_atual = date.today().year
    inicio = max(PRIMEIRO_ANO, ano_atual - anos_necessarios)

    pontos = []
    falhas = []
    for ano in range(inicio, ano_atual + 1):
        try:
            for linha in _linhas_complemento(ano):
                if linha.get("CNPJ_Fundo_Classe", "").strip() != cnpj:
                    continue
                pontos.append(_normalizar(linha))
        except FalhaFonte as erro:
            falhas.append(str(erro))

    if not pontos:
        detalhe = "; ".join(falhas) if falhas else "CNPJ nao encontrado no informe mensal"
        raise FalhaFonte(f"CVM: sem dados para o CNPJ {cnpj} ({detalhe})")

    pontos.sort(key=lambda p: p["data"])
    return pontos[-meses:] if meses else pontos


def ultimo(cnpj: str) -> dict:
    """Ponto mais recente disponivel para o CNPJ."""
    return informe_mensal(cnpj, meses=3)[-1]
