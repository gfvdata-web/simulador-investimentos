"""Valida os arquivos de dados contra o que o codigo realmente implementa.

Existe para que cadastrar ativo novo seja seguro: um typo em 'regime' ou uma
'chave_premissa' que nao existe viram erro aqui, e nao um numero errado na tela.

    python scripts/validar.py

Roda no CI antes de publicar. Sai com codigo 1 se achar erro.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# Espelham o que esta implementado no navegador. Ao criar um tipo ou regime
# novo em app/nucleo/, acrescente aqui tambem - e o proprio teste faz a
# checagem cruzada logo abaixo.
TIPOS_RENDIMENTO = {
    "pos_cdi", "pos_selic", "prefixado", "ipca_mais", "poupanca", "estimado",
    "fundo_fii", "etf_historico", "fundo_cvm_historico",
}
REGIMES = {
    "isento", "rf_regressivo", "etf_renda_variavel", "fundo_acoes", "acoes",
    "cripto", "fii", "fundo_longo_prazo",
}
CLASSES = {"renda_fixa", "renda_variavel", "cripto", "fundos"}
CENARIOS = {"pessimista", "base", "otimista"}
# Leem dados/mercado/fundos/<ticker>.json, nao 'estimativas'. tipo -> tipo do
# arquivo de fundo esperado (ver coletor/atualizar.py, FUNDOS).
TIPOS_FUNDO = {"fundo_fii": "fii", "etf_historico": "etf", "fundo_cvm_historico": "fi"}

CAMPOS_OBRIGATORIOS = [
    "id", "nome", "classe", "subclasse", "risco", "rendimento", "tributacao", "descricao",
]
CAMPOS_POR_TIPO = {
    "pos_cdi": ["percentual_cdi"],
    "prefixado": ["taxa_aa"],
    "ipca_mais": ["spread_aa"],
    "estimado": ["chave_premissa"],
    "fundo_fii": ["ticker"],
    "etf_historico": ["ticker"],
    "fundo_cvm_historico": ["ticker"],
}


def ler(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


def validar_catalogo(catalogo: dict, premissas: dict, erros: list, avisos: list) -> None:
    vistos = set()
    estimativas = premissas.get("estimativas", {})

    for ativo in catalogo.get("ativos", []):
        nome = ativo.get("id", "<sem id>")

        for campo in CAMPOS_OBRIGATORIOS:
            if campo not in ativo:
                erros.append(f"{nome}: falta o campo obrigatorio '{campo}'")

        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(ativo.get("id", ""))):
            erros.append(f"{nome}: id deve ser kebab-case (so minusculas, digitos e hifen)")
        if ativo.get("id") in vistos:
            erros.append(f"{nome}: id duplicado")
        vistos.add(ativo.get("id"))

        if ativo.get("classe") not in CLASSES:
            erros.append(f"{nome}: classe '{ativo.get('classe')}' desconhecida; use uma de {sorted(CLASSES)}")

        risco = ativo.get("risco")
        if not isinstance(risco, int) or not 1 <= risco <= 6:
            erros.append(f"{nome}: risco deve ser inteiro de 1 a 6, veio {risco!r}")

        rendimento = ativo.get("rendimento", {})
        tipo = rendimento.get("tipo")
        if tipo not in TIPOS_RENDIMENTO:
            erros.append(f"{nome}: tipo de rendimento '{tipo}' nao implementado")
        else:
            for campo in CAMPOS_POR_TIPO.get(tipo, []):
                if campo not in rendimento:
                    erros.append(f"{nome}: rendimento '{tipo}' exige o campo '{campo}'")
            if tipo == "estimado":
                chave = rendimento.get("chave_premissa")
                bloco = estimativas.get(chave)
                if bloco is None:
                    erros.append(f"{nome}: chave_premissa '{chave}' nao existe em premissas.json")
                else:
                    faltando = CENARIOS - set(bloco.get("retorno_aa", {}))
                    if faltando:
                        erros.append(f"{nome}: estimativa '{chave}' sem cenario(s) {sorted(faltando)}")
                    if not bloco.get("fonte"):
                        erros.append(f"{nome}: estimativa '{chave}' sem 'fonte' preenchida")
            if tipo in TIPOS_FUNDO:
                ticker = rendimento.get("ticker")
                caminho_fundo = RAIZ / "dados" / "mercado" / "fundos" / f"{ticker}.json"
                if not caminho_fundo.exists():
                    avisos.append(
                        f"{nome}: ticker '{ticker}' ainda sem dados/mercado/fundos/{ticker}.json "
                        "coletado (rode coletor/atualizar.py) - o ativo vai cair em 'erros' na pagina"
                    )
                else:
                    tipo_esperado = TIPOS_FUNDO[tipo]
                    tipo_arquivo = ler(caminho_fundo).get("tipo")
                    if tipo_arquivo != tipo_esperado:
                        erros.append(
                            f"{nome}: rendimento '{tipo}' espera ticker do tipo '{tipo_esperado}', mas "
                            f"dados/mercado/fundos/{ticker}.json diz '{tipo_arquivo}'"
                        )

        regime = ativo.get("tributacao", {}).get("regime")
        if regime not in REGIMES:
            erros.append(f"{nome}: regime tributario '{regime}' nao implementado")
        if regime == "fundo_longo_prazo" and not premissas.get("tributacao", {}).get("come_cotas_habilitado"):
            avisos.append(
                f"{nome}: usa 'fundo_longo_prazo', mas 'come_cotas_habilitado' está desligado em "
                "premissas.json - o número vai sair otimista demais (docs/05)"
            )

        for campo, valor in (ativo.get("taxas") or {}).items():
            if not isinstance(valor, (int, float)) or valor < 0:
                erros.append(f"{nome}: taxa '{campo}' deve ser numero >= 0, veio {valor!r}")
            elif valor > 5:
                avisos.append(f"{nome}: taxa '{campo}' = {valor}% a.a. parece alta demais "
                              "(o campo e em pontos percentuais ao ano)")

        if len(ativo.get("descricao", "")) < 20:
            avisos.append(f"{nome}: descricao muito curta; ela vira o tooltip na pagina")


def validar_premissas(premissas: dict, erros: list, avisos: list) -> None:
    trib = premissas.get("tributacao", {})

    tabela = trib.get("ir_regressivo_rf")
    if not tabela:
        erros.append("premissas: falta 'tributacao.ir_regressivo_rf'")
    else:
        if tabela[-1].get("ate_dias") is not None:
            erros.append("premissas: a ultima faixa de ir_regressivo_rf precisa ter ate_dias: null")
        limites = [f["ate_dias"] for f in tabela[:-1]]
        if limites != sorted(limites):
            erros.append("premissas: faixas de ir_regressivo_rf fora de ordem crescente")

    iof = trib.get("iof_regressivo_30d", [])
    if len(iof) != 30:
        erros.append(f"premissas: iof_regressivo_30d deve ter 30 entradas, tem {len(iof)}")
    elif iof[-1] != 0:
        erros.append("premissas: o 30o dia do IOF deve ser 0")

    for chave, bloco in premissas.get("estimativas", {}).items():
        if chave.startswith("_") or not isinstance(bloco, dict):
            continue
        if "retorno_aa" in bloco and not bloco.get("fonte"):
            erros.append(f"premissas: estimativa '{chave}' sem 'fonte'")

    for chave in ("cdi_aa", "selic_meta_aa", "ipca_12m", "poupanca_am"):
        if chave not in premissas.get("indicadores", {}):
            erros.append(f"premissas: falta o fallback de indicador '{chave}'")


def validar_mercado(erros: list, avisos: list) -> None:
    caminho = RAIZ / "dados" / "mercado" / "indicadores.json"
    if not caminho.exists():
        avisos.append("dados/mercado/indicadores.json ainda nao existe; rode coletor/atualizar.py")
        return
    retrato = ler(caminho)
    for chave, campo in retrato.get("campos", {}).items():
        if campo.get("valor") is None:
            avisos.append(f"mercado: indicador '{chave}' sem valor no ultimo retrato")

    dir_series = RAIZ / "dados" / "mercado" / "series"
    for arquivo in sorted(dir_series.glob("*.json")):
        serie = ler(arquivo)
        pontos = serie.get("pontos", [])
        if not pontos:
            erros.append(f"mercado: serie '{arquivo.stem}' sem pontos")
            continue
        datas = [p["data"] for p in pontos]
        if datas != sorted(datas):
            erros.append(f"mercado: serie '{arquivo.stem}' fora de ordem cronologica")
        if len(set(datas)) != len(datas):
            erros.append(f"mercado: serie '{arquivo.stem}' tem datas duplicadas")

    dir_fundos = RAIZ / "dados" / "mercado" / "fundos"
    for arquivo in sorted(dir_fundos.glob("*.json")):
        fundo = ler(arquivo)
        pontos = fundo.get("pontos", [])
        resumo = fundo.get("resumo")
        if not pontos:
            erros.append(f"mercado: fundo '{arquivo.stem}' sem pontos")
            continue
        datas = [p["data"] for p in pontos]
        if datas != sorted(datas):
            erros.append(f"mercado: fundo '{arquivo.stem}' fora de ordem cronologica")
        if len(set(datas)) != len(datas):
            erros.append(f"mercado: fundo '{arquivo.stem}' tem datas duplicadas")
        if not resumo:
            erros.append(f"mercado: fundo '{arquivo.stem}' sem 'resumo'")
        elif fundo.get("tipo") == "fii":
            for campo in ("dividend_yield_am_medio_pct", "valorizacao_patrimonial_am_media_pct"):
                if campo not in resumo:
                    erros.append(f"mercado: fundo '{arquivo.stem}' (fii) sem '{campo}' no resumo")
        elif fundo.get("tipo") in ("etf", "fi"):
            faltando = CENARIOS - set(resumo.get("retorno_aa", {}))
            if faltando:
                erros.append(
                    f"mercado: fundo '{arquivo.stem}' ({fundo.get('tipo')}) sem cenario(s) {sorted(faltando)}"
                )


def conferir_espelho_com_codigo(erros: list) -> None:
    """Garante que as listas deste arquivo nao fiquem para tras do codigo real."""
    pares = [
        ("app/nucleo/indexadores.js", r"case '([a-z_]+)':", TIPOS_RENDIMENTO, "tipo de rendimento"),
        ("app/nucleo/tributos.js", r"regime === '([a-z_]+)'", REGIMES, "regime tributario"),
    ]
    for caminho, padrao, esperados, rotulo in pares:
        fonte = (RAIZ / caminho).read_text(encoding="utf-8")
        encontrados = set(re.findall(padrao, fonte))
        novos = encontrados - esperados
        if novos:
            erros.append(
                f"{caminho} implementa {rotulo}(s) {sorted(novos)} que este validador nao conhece. "
                "Acrescente em scripts/validar.py e documente no docs/02."
            )


def main() -> int:
    erros: list = []
    avisos: list = []

    catalogo = ler(RAIZ / "dados" / "catalogo" / "ativos.json")
    premissas = ler(RAIZ / "dados" / "premissas" / "premissas.json")

    validar_catalogo(catalogo, premissas, erros, avisos)
    validar_premissas(premissas, erros, avisos)
    validar_mercado(erros, avisos)
    conferir_espelho_com_codigo(erros)

    total = len(catalogo.get("ativos", []))
    print(f"{total} ativos no catalogo")

    for aviso in avisos:
        print(f"  aviso  {aviso}")
    for erro in erros:
        print(f"  ERRO   {erro}")

    if erros:
        print(f"\n{len(erros)} erro(s). Corrija antes de publicar.")
        return 1
    print(f"\nTudo consistente{f' ({len(avisos)} aviso(s))' if avisos else ''}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
