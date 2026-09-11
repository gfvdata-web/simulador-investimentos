"""Motor de projecao: transforma aportes + taxa em uma trajetoria mes a mes.

Convencoes (documentadas em docs/03-motor-de-calculo.md):
  - O mes 1 e o primeiro mes cheio de rendimento.
  - O capital inicial entra no comeco do mes 1 e rende os N meses.
  - Cada aporte mensal entra no comeco do seu mes e rende daquele mes em diante.
  - Cada entrada de dinheiro vira um LOTE proprio, porque a tabela regressiva
    de IR conta o prazo de cada aporte separadamente.
  - Prazo para fins de IR usa mes comercial de 30 dias.
"""
from __future__ import annotations

from . import indexadores, tributos

MAX_MESES = 600


def projetar(
    ativo: dict,
    indicadores_atuais: dict,
    premissas: dict,
    valor_inicial: float,
    aporte_mensal: float,
    meses: int,
    cenario: str = "base",
    considerar_ir: bool = True,
    considerar_inflacao: bool = True,
) -> dict:
    if meses < 1 or meses > MAX_MESES:
        raise ValueError(f"Prazo deve estar entre 1 e {MAX_MESES} meses")
    if valor_inicial < 0 or aporte_mensal < 0:
        raise ValueError("Valores de aporte nao podem ser negativos")
    if valor_inicial <= 0 and aporte_mensal <= 0:
        raise ValueError("Informe um valor inicial ou um aporte mensal")

    taxa = indexadores.resolver(ativo, indicadores_atuais, premissas, cenario)
    taxa_am = taxa["taxa_am"]

    lotes = []
    serie = [{"mes": 0, "bruto": round(valor_inicial, 2), "investido": round(valor_inicial, 2)}]
    investido = valor_inicial
    if valor_inicial > 0:
        lotes.append({"mes_entrada": 1, "principal": valor_inicial, "valor_final": valor_inicial})

    for mes in range(1, meses + 1):
        if aporte_mensal > 0:
            lotes.append({"mes_entrada": mes, "principal": aporte_mensal, "valor_final": aporte_mensal})
            investido += aporte_mensal

        for lote in lotes:
            lote["valor_final"] *= 1 + taxa_am

        bruto = sum(l["valor_final"] for l in lotes)
        serie.append({"mes": mes, "bruto": round(bruto, 2), "investido": round(investido, 2)})

    bruto_final = sum(l["valor_final"] for l in lotes)
    rendimento_bruto = bruto_final - investido

    for lote in lotes:
        lote["dias"] = (meses - lote["mes_entrada"] + 1) * tributos.DIAS_MES_COMERCIAL

    regime = ativo["tributacao"]["regime"]
    if considerar_ir:
        imposto = tributos.tributar(regime, lotes, bruto_final, premissas["tributacao"])
    else:
        imposto = {"iof": 0.0, "ir": 0.0, "total": 0.0, "aliquota_efetiva": 0.0,
                   "detalhe": "Impostos desligados nesta simulacao"}

    liquido = bruto_final - imposto["total"]

    inflacao = _inflacao(premissas, indicadores_atuais, cenario, meses)
    liquido_real = liquido / inflacao["fator"] if considerar_inflacao else liquido

    return {
        "ativo_id": ativo["id"],
        "nome": ativo["nome"],
        "classe": ativo["classe"],
        "risco": ativo.get("risco"),
        "taxa": taxa,
        "meses": meses,
        "investido": round(investido, 2),
        "bruto": round(bruto_final, 2),
        "rendimento_bruto": round(rendimento_bruto, 2),
        "impostos": imposto,
        "liquido": round(liquido, 2),
        "rendimento_liquido": round(liquido - investido, 2),
        "liquido_real": round(liquido_real, 2),
        "ganho_real": round(liquido_real - investido, 2),
        "rentabilidade_bruta_pct": _pct(bruto_final, investido),
        "rentabilidade_liquida_pct": _pct(liquido, investido),
        "rentabilidade_real_pct": _pct(liquido_real, investido),
        "inflacao": inflacao,
        "serie": serie,
        "lotes": len(lotes),
    }


def comparar(
    ativos: list,
    indicadores_atuais: dict,
    premissas: dict,
    **parametros,
) -> dict:
    resultados = []
    erros = []
    for ativo in ativos:
        try:
            resultados.append(projetar(ativo, indicadores_atuais, premissas, **parametros))
        except (ValueError, KeyError) as erro:
            erros.append({"ativo_id": ativo.get("id"), "erro": str(erro)})

    resultados.sort(key=lambda r: r["liquido"], reverse=True)
    for posicao, resultado in enumerate(resultados, start=1):
        resultado["ranking"] = posicao
        if resultados:
            resultado["diferenca_para_1o"] = round(resultado["liquido"] - resultados[0]["liquido"], 2)

    return {"resultados": resultados, "erros": erros}


def _inflacao(premissas: dict, indicadores_atuais: dict, cenario: str, meses: int) -> dict:
    bloco = premissas.get("estimativas", {}).get("ipca_projetado_aa", {})
    if isinstance(bloco, dict):
        ipca_aa = float(bloco.get(cenario, bloco.get("base", indicadores_atuais["ipca_12m"])))
    else:
        ipca_aa = float(bloco or indicadores_atuais["ipca_12m"])
    fator = (1 + ipca_aa / 100) ** (meses / 12)
    return {
        "ipca_aa_projetado": round(ipca_aa, 4),
        "fator": fator,
        "perda_poder_compra_pct": round((1 - 1 / fator) * 100, 2),
        "cenario": cenario,
    }


def _pct(final: float, investido: float) -> float:
    if investido <= 0:
        return 0.0
    return round((final / investido - 1) * 100, 2)
