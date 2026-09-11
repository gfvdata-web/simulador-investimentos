"""Coletor de dados de mercado.

Le as fontes oficiais e grava um retrato em dados/mercado/. A pagina do
simulador nunca fala com a internet: ela le esses arquivos, que sao versionados
no git. Isso deixa cada simulacao auditavel (da para ver no historico do
repositorio exatamente qual CDI foi usado em cada dia) e faz o site funcionar
mesmo se a fonte estiver fora do ar.

Roda sozinho pelo GitHub Actions (.github/workflows/atualizar-dados.yml) e
tambem na mao:

    python coletor/atualizar.py
    python coletor/atualizar.py --meses 120 --verbose

Se uma fonte falhar, o arquivo anterior e PRESERVADO: dado velho com data
visivel e melhor que dado ausente, e muito melhor que dado inventado.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fontes import bcb_sgs  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
DIR_MERCADO = RAIZ / "dados" / "mercado"
DIR_SERIES = DIR_MERCADO / "series"

# Series historicas mensais publicadas para a pagina.
SERIES_HISTORICAS = {
    "cdi": ("cdi_mensal", "CDI acumulado no mes", 4391),
    "selic": ("selic_mensal", "Selic acumulada no mes", 4390),
    "ipca": ("ipca_mensal", "IPCA mensal", 433),
    "poupanca": ("poupanca_mensal", "Rendimento da poupanca", 196),
}

MESES_PADRAO = 120


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def gravar(caminho: Path, conteudo: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def coletar_indicadores(relatorio: list) -> dict:
    """Fotografia atual dos indicadores, cada campo com sua procedencia."""
    campos = {}

    def tentar(chave, funcao, codigo):
        try:
            campos[chave] = funcao()
            relatorio.append(f"  ok    {chave} = {campos[chave]['valor']} (SGS {codigo})")
        except bcb_sgs.FalhaFonte as erro:
            campos[chave] = {"valor": None, "origem": "indisponivel", "detalhe": str(erro)}
            relatorio.append(f"  FALHA {chave}: {erro}")

    def campo(nome_serie, codigo):
        ponto = bcb_sgs.ultimo(nome_serie)
        return {
            "valor": ponto["valor"],
            "origem": "Banco Central (SGS)",
            "serie_sgs": codigo,
            "referencia": ponto["data"],
        }

    tentar("cdi_aa", lambda: campo("cdi_aa", 4389), 4389)
    tentar("selic_meta_aa", lambda: campo("selic_meta_aa", 432), 432)
    tentar("poupanca_am", lambda: campo("poupanca_mensal", 196), 196)

    def ipca():
        bruto = bcb_sgs.ipca_acumulado_12m()
        return {
            "valor": bruto["valor"],
            "origem": "Banco Central (SGS)",
            "serie_sgs": 433,
            "referencia": bruto["referencia"],
        }

    tentar("ipca_12m", ipca, 433)
    return campos


def mesclar_com_anterior(campos: dict, caminho: Path, relatorio: list) -> dict:
    """Campo que falhou herda o valor do retrato anterior, marcado como vencido."""
    if not caminho.exists():
        return campos
    try:
        anterior = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return campos

    for chave, valor in campos.items():
        if valor.get("valor") is not None:
            continue
        antigo = anterior.get("campos", {}).get(chave)
        if antigo and antigo.get("valor") is not None:
            campos[chave] = {
                **antigo,
                "origem": "retrato anterior (fonte indisponivel na ultima coleta)",
                "coletado_em": anterior.get("coletado_em"),
            }
            relatorio.append(f"  herda {chave} do retrato de {anterior.get('coletado_em')}")
    return campos


def coletar_series(meses: int, relatorio: list) -> None:
    for nome, (chave, rotulo, codigo) in SERIES_HISTORICAS.items():
        caminho = DIR_SERIES / f"{nome}.json"
        try:
            pontos = bcb_sgs.serie(chave, meses=meses)
        except bcb_sgs.FalhaFonte as erro:
            relatorio.append(f"  FALHA serie {nome}: {erro} (arquivo anterior preservado)")
            continue

        gravar(caminho, {
            "serie": nome,
            "rotulo": rotulo,
            "fonte": "Banco Central do Brasil - SGS",
            "serie_sgs": codigo,
            "coletado_em": agora(),
            "pontos": pontos,
        })
        relatorio.append(f"  ok    serie {nome}: {len(pontos)} pontos ate {pontos[-1]['data']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Atualiza os dados de mercado")
    parser.add_argument("--meses", type=int, default=MESES_PADRAO,
                        help=f"quantos meses de historico buscar (padrao {MESES_PADRAO})")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    relatorio = [f"Coleta iniciada em {agora()}"]
    caminho_indicadores = DIR_MERCADO / "indicadores.json"

    campos = coletar_indicadores(relatorio)
    campos = mesclar_com_anterior(campos, caminho_indicadores, relatorio)

    vivos = sum(1 for c in campos.values() if c.get("valor") is not None)
    gravar(caminho_indicadores, {
        "coletado_em": agora(),
        "fonte": "Banco Central do Brasil - API SGS",
        "completo": vivos == len(campos),
        "campos": campos,
    })
    relatorio.append(f"  {vivos}/{len(campos)} indicadores com valor")

    coletar_series(args.meses, relatorio)

    print("\n".join(relatorio))

    if vivos == 0:
        print("\nNenhum indicador coletado. Falhando para o Actions avisar.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
