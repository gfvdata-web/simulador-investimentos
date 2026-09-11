"""Acesso aos arquivos JSON de catalogo e premissas, e a fusao deles com os
indicadores vivos do Banco Central.

Regra de ouro do projeto: numero de fonte oficial sempre vence o fallback do
arquivo, e a origem de cada numero viaja junto com ele ate a tela.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .fontes import bcb_sgs

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO_ATIVOS = RAIZ / "dados" / "catalogo" / "ativos.json"
CAMINHO_PREMISSAS = RAIZ / "dados" / "premissas" / "premissas.json"


def _ler(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def catalogo() -> dict:
    return _ler(CAMINHO_ATIVOS)


def ativos_por_id() -> dict:
    return {a["id"]: a for a in catalogo()["ativos"]}


def premissas() -> dict:
    return _ler(CAMINHO_PREMISSAS)


def indicadores(forcar_atualizacao: bool = False) -> dict:
    """Indicadores prontos para o motor, com a procedencia de cada campo.

    Formato: {'cdi_aa': 13.9, ..., '_origem': {'cdi_aa': {...}}, '_degradado': bool}
    """
    base = premissas()["indicadores"]
    ttl = 0 if forcar_atualizacao else bcb_sgs.TTL_PADRAO
    vivos = bcb_sgs.indicadores(ttl=ttl)

    final = {}
    procedencia = {}
    degradado = False

    mapa = {
        "cdi_aa": "cdi_aa",
        "selic_meta_aa": "selic_meta_aa",
        "ipca_12m": "ipca_12m",
        "poupanca_am": "poupanca_am",
    }
    for chave, campo in mapa.items():
        vivo = vivos["campos"].get(campo, {})
        if vivo.get("valor") is not None:
            final[chave] = vivo["valor"]
            procedencia[chave] = {
                "origem": "Banco Central (SGS)",
                "serie_sgs": vivo.get("serie_sgs"),
                "referencia": vivo.get("referencia"),
            }
        else:
            final[chave] = base[chave]
            procedencia[chave] = {
                "origem": "fallback de premissas.json",
                "referencia": premissas()["atualizado_em"],
                "detalhe": vivo.get("detalhe", "fonte indisponivel"),
            }
            degradado = True

    final["tr_am"] = base.get("tr_am", 0.0)
    final["_origem"] = procedencia
    final["_degradado"] = degradado
    final["_consultado_em"] = vivos["consultado_em"]
    return final


def historico(serie_nome: str, meses: int = 60) -> dict:
    """Serie historica mensal real, para a linha do tempo do simulador."""
    disponiveis = {
        "cdi": ("cdi_mensal", "CDI acumulado no mes", 4391),
        "selic": ("selic_mensal", "Selic acumulada no mes", 4390),
        "ipca": ("ipca_mensal", "IPCA mensal", 433),
        "poupanca": ("poupanca_mensal", "Rendimento da poupanca", 196),
    }
    if serie_nome not in disponiveis:
        raise ValueError(
            f"Serie '{serie_nome}' indisponivel. Opcoes: {', '.join(disponiveis)}"
        )
    chave, rotulo, codigo = disponiveis[serie_nome]
    # Pedimos um mes a mais porque o mes corrente vem parcial e sera descartado.
    pontos = bcb_sgs.serie(chave, ultimos=max(2, min(meses + 1, 360)))

    mes_atual = date.today().strftime("%Y-%m")
    pontos = [p for p in pontos if p["data"][:7] != mes_atual][-meses:]
    if not pontos:
        raise ValueError(f"Serie '{serie_nome}' sem meses fechados disponiveis")

    fator = 1.0
    acumulado = []
    for ponto in pontos:
        fator *= 1 + ponto["valor"] / 100
        acumulado.append({
            "data": ponto["data"],
            "mensal_pct": ponto["valor"],
            "acumulado_pct": round((fator - 1) * 100, 4),
            "indice_100": round(fator * 100, 4),
        })

    return {
        "serie": serie_nome,
        "rotulo": rotulo,
        "fonte": "Banco Central do Brasil - SGS",
        "serie_sgs": codigo,
        "pontos": acumulado,
        "acumulado_total_pct": acumulado[-1]["acumulado_pct"] if acumulado else 0.0,
    }
