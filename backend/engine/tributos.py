"""Camada fiscal brasileira aplicada sobre o resultado bruto da projecao.

Regimes suportados:
  isento              LCI, LCA, CRI, CRA, poupanca, debenture incentivada
  rf_regressivo       CDB, Tesouro Direto, RDB, LC (IR 22,5% -> 15% + IOF < 30d)
  etf_renda_variavel  ETFs de acoes: 15% sobre o ganho, SEM isencao mensal
  acoes               15% sobre o ganho, isento ate R$ 20.000 vendidos no mes
  cripto              15% sobre o ganho, isento ate R$ 35.000 vendidos no mes
  fundo_longo_prazo   come-cotas semestral (ainda nao modelado, ver docs/05)

Nada aqui e conselho tributario. As regras refletem a legislacao geral para
pessoa fisica e devem ser reconferidas antes de qualquer decisao real.
"""
from __future__ import annotations

DIAS_MES_COMERCIAL = 30


def aliquota_ir_rf(dias: int, tabela: list) -> float:
    for faixa in tabela:
        limite = faixa.get("ate_dias")
        if limite is None or dias <= limite:
            return faixa["aliquota"]
    return tabela[-1]["aliquota"]


def aliquota_iof(dias: int, tabela: list) -> float:
    """IOF regressivo sobre o RENDIMENTO nos 30 primeiros dias."""
    if dias >= 30 or dias < 1:
        return 0.0
    return float(tabela[dias - 1]) if dias - 1 < len(tabela) else 0.0


def tributar(regime: str, lotes: list, valor_venda_total: float, regras: dict) -> dict:
    """Calcula IOF e IR de uma posicao encerrada.

    `lotes` = [{'principal': float, 'valor_final': float, 'dias': int}], um por
    aporte, porque na tabela regressiva cada aporte tem seu proprio prazo.
    """
    rendimento_total = sum(l["valor_final"] - l["principal"] for l in lotes)

    if regime == "isento":
        return _zero("Isento de IR para pessoa fisica")
    if rendimento_total <= 0:
        return _zero("Sem rendimento tributavel no periodo")

    if regime == "rf_regressivo":
        iof_total = 0.0
        ir_total = 0.0
        for lote in lotes:
            ganho = lote["valor_final"] - lote["principal"]
            if ganho <= 0:
                continue
            iof = ganho * aliquota_iof(lote["dias"], regras["iof_regressivo_30d"]) / 100
            base = ganho - iof
            ir_total += base * aliquota_ir_rf(lote["dias"], regras["ir_regressivo_rf"]) / 100
            iof_total += iof
        tabela = regras["ir_regressivo_rf"]
        maior = max(l["dias"] for l in lotes)
        menor = min(l["dias"] for l in lotes)
        if maior == menor:
            faixa = f"{aliquota_ir_rf(maior, tabela):g}%"
        else:
            faixa = (
                f"{aliquota_ir_rf(maior, tabela):g}% a {aliquota_ir_rf(menor, tabela):g}%"
                " (aportes com prazos diferentes)"
            )
        return _montar(iof_total, ir_total, rendimento_total, f"IR regressivo: {faixa}")

    if regime in ("etf_renda_variavel", "acoes", "cripto"):
        if regime == "acoes":
            limite = regras.get("isencao_venda_acoes_mensal", 0)
            aliquota = regras["ir_renda_variavel_aliquota"]
            if valor_venda_total <= limite:
                return _zero(_texto_isencao(valor_venda_total, limite))
        elif regime == "cripto":
            limite = regras.get("isencao_venda_cripto_mensal", 0)
            aliquota = regras["ir_cripto_aliquota"]
            if valor_venda_total <= limite:
                return _zero(_texto_isencao(valor_venda_total, limite))
        else:
            aliquota = regras["ir_renda_variavel_aliquota"]
        ir = rendimento_total * aliquota / 100
        return _montar(0.0, ir, rendimento_total, f"{aliquota:g}% sobre o ganho de capital")

    if regime == "fundo_longo_prazo":
        ir = rendimento_total * 15 / 100
        return _montar(0.0, ir, rendimento_total, "15% (come-cotas ainda nao modelado)")

    raise ValueError(f"Regime tributario desconhecido: {regime}")


def _texto_isencao(venda: float, limite: float) -> str:
    return (
        f"Venda de R$ {venda:,.2f} abaixo da isencao mensal de R$ {limite:,.0f}"
    ).replace(",", "@").replace(".", ",").replace("@", ".")


def _montar(iof: float, ir: float, rendimento: float, detalhe: str) -> dict:
    total = iof + ir
    return {
        "iof": round(iof, 2),
        "ir": round(ir, 2),
        "total": round(total, 2),
        "aliquota_efetiva": round(total / rendimento * 100, 2) if rendimento > 0 else 0.0,
        "detalhe": detalhe,
    }


def _zero(detalhe: str) -> dict:
    return {"iof": 0.0, "ir": 0.0, "total": 0.0, "aliquota_efetiva": 0.0, "detalhe": detalhe}
