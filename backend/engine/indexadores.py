"""Traduz o bloco 'rendimento' de um ativo em uma taxa mensal efetiva.

Toda taxa entra aqui em % ao ano e sai como fracao ao mes. O resultado
carrega a explicacao de como foi obtido, para a tela nunca mostrar um
numero sem procedencia.
"""
from __future__ import annotations

MESES_ANO = 12


def aa_para_am(taxa_aa_pct: float) -> float:
    """12,00 (% a.a.) -> 0,009489 (fracao a.m.), por juro composto."""
    return (1 + taxa_aa_pct / 100) ** (1 / MESES_ANO) - 1


def am_para_aa(taxa_am_fracao: float) -> float:
    return ((1 + taxa_am_fracao) ** MESES_ANO - 1) * 100


def compor(taxa_a_pct: float, taxa_b_pct: float) -> float:
    """Composicao correta de duas taxas (ex.: IPCA + juro real)."""
    return ((1 + taxa_a_pct / 100) * (1 + taxa_b_pct / 100) - 1) * 100


def descontar(taxa_bruta_pct: float, taxa_custo_pct: float) -> float:
    """Retira um custo anual (administracao/custodia) de uma taxa anual."""
    if taxa_custo_pct <= 0:
        return taxa_bruta_pct
    return ((1 + taxa_bruta_pct / 100) / (1 + taxa_custo_pct / 100) - 1) * 100


def resolver(ativo: dict, indicadores: dict, premissas: dict, cenario: str = "base") -> dict:
    """Devolve a taxa efetiva do ativo e a explicacao de como chegou nela."""
    spec = ativo["rendimento"]
    tipo = spec["tipo"]
    estimativas = premissas.get("estimativas", {})

    cdi = indicadores["cdi_aa"]
    selic = indicadores["selic_meta_aa"]
    ipca = indicadores["ipca_12m"]
    poupanca_am = indicadores["poupanca_am"]

    if tipo == "pos_cdi":
        pct = spec["percentual_cdi"]
        bruta = cdi * pct / 100
        explicacao = f"{pct:g}% do CDI ({cdi:.2f}% a.a.)"
        natureza = "contratada"

    elif tipo == "pos_selic":
        spread = spec.get("spread_aa", 0.0)
        bruta = compor(selic, spread) if spread else selic
        explicacao = f"Selic {selic:.2f}% a.a." + (f" + {spread:g}%" if spread else "")
        natureza = "contratada"

    elif tipo == "prefixado":
        bruta = spec["taxa_aa"]
        explicacao = f"Taxa prefixada de {bruta:.2f}% a.a."
        natureza = "contratada"

    elif tipo == "ipca_mais":
        spread = spec["spread_aa"]
        ipca_proj = _cenario(estimativas.get("ipca_projetado_aa", {}), cenario, ipca)
        bruta = compor(ipca_proj, spread)
        explicacao = f"IPCA projetado {ipca_proj:.2f}% a.a. + {spread:g}% de juro real"
        natureza = "hibrida"

    elif tipo == "poupanca":
        bruta = am_para_aa(poupanca_am / 100)
        explicacao = f"Poupanca a {poupanca_am:.4f}% a.m., anualizado"
        natureza = "contratada"

    elif tipo == "estimado":
        chave = spec["chave_premissa"]
        bloco = estimativas.get(chave)
        if not bloco:
            raise ValueError(f"Sem premissa de retorno para '{chave}' em premissas.json")
        bruta = _cenario(bloco["retorno_aa"], cenario, None)
        explicacao = f"Retorno ESTIMADO de {bruta:.2f}% a.a. (cenario {cenario})"
        natureza = "estimada"

    else:
        raise ValueError(f"Tipo de rendimento nao suportado: {tipo}")

    taxas = ativo.get("taxas", {})
    custo = taxas.get("administracao_aa", 0.0) + taxas.get("custodia_aa", 0.0)
    liquida_de_taxas = descontar(bruta, custo)
    if custo:
        explicacao += f", menos {custo:g}% a.a. de taxas"

    return {
        "taxa_aa": round(liquida_de_taxas, 4),
        "taxa_aa_antes_taxas": round(bruta, 4),
        "taxa_am": aa_para_am(liquida_de_taxas),
        "custo_aa": round(custo, 4),
        "explicacao": explicacao,
        "natureza": natureza,
    }


def _cenario(bloco, cenario: str, padrao):
    if isinstance(bloco, (int, float)):
        return float(bloco)
    if isinstance(bloco, dict):
        if cenario in bloco:
            return float(bloco[cenario])
        if "base" in bloco:
            return float(bloco["base"])
    if padrao is None:
        raise ValueError("Cenario sem valor definido e sem padrao")
    return float(padrao)
