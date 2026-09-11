"""Coletor de dados de mercado.

Le as fontes oficiais e grava um retrato em dados/mercado/. A pagina do
simulador nunca fala com a internet: ela le esses arquivos, que sao versionados
no git. Isso deixa cada simulacao auditavel (da para ver no historico do
repositorio exatamente qual CDI foi usado em cada dia) e faz o site funcionar
mesmo se a fonte estiver fora do ar.

    python coletor/atualizar.py
    python coletor/atualizar.py --meses 120 --so cdi_aa,ipca_12m

PARA ACRESCENTAR UM INDICADOR OU UMA SERIE, edite so os registros INDICADORES e
SERIES logo abaixo. O retrato gravado carrega rotulo e unidade de cada item, e a
pagina se monta a partir disso - nao ha lista de indicadores escrita na mao do
lado do navegador. Fonte nova: crie o modulo em coletor/fontes/ seguindo o
protocolo documentado em PROTOCOLO_FONTE e registre em FONTES.

Se uma fonte falhar, o dado anterior e PRESERVADO: dado velho com data visivel e
melhor que dado ausente, e muito melhor que dado inventado.
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

MESES_PADRAO = 120

# Convencao do arquivo: identificadores e comentarios sem acento (o CI roda com
# locale imprevisivel), mas 'rotulo' e texto que aparece na tela do usuario e
# leva acentuacao normal - ele viaja como dado UTF-8 para o JSON.

PROTOCOLO_FONTE = """
Um modulo de fonte precisa expor:
    FalhaFonte              excecao levantada quando a fonte nao responde
    ultimo(nome) -> dict    {'data': 'YYYY-MM-DD', 'valor': float}
    serie(nome, meses)      [{'data': ..., 'valor': ...}], crescente por data
    NOME                    nome legivel da fonte, usado na tela
Nada de inventar valor: se falhar, levante FalhaFonte.
"""

FONTES = {
    "bcb": bcb_sgs,
}

# --- Indicadores: o valor "de hoje" de cada referencia do mercado -----------
# agregacao: 'ultimo' pega o ponto mais recente; 'acumulado_12m' compoe os 12
# ultimos pontos mensais em uma taxa anual.
INDICADORES = {
    "cdi_aa": {
        "fonte": "bcb", "serie": "cdi_aa", "agregacao": "ultimo",
        "rotulo": "CDI", "unidade": "% a.a.", "referencia_fonte": 4389,
    },
    "selic_meta_aa": {
        "fonte": "bcb", "serie": "selic_meta_aa", "agregacao": "ultimo",
        "rotulo": "Selic meta", "unidade": "% a.a.", "referencia_fonte": 432,
    },
    "ipca_12m": {
        "fonte": "bcb", "serie": "ipca_mensal", "agregacao": "acumulado_12m",
        "rotulo": "IPCA 12 meses", "unidade": "%", "referencia_fonte": 433,
    },
    "poupanca_am": {
        "fonte": "bcb", "serie": "poupanca_mensal", "agregacao": "ultimo",
        "rotulo": "Poupança", "unidade": "% a.m.", "referencia_fonte": 196,
    },
}

# --- Series historicas mensais publicadas para a aba de historico ----------
SERIES = {
    "cdi": {
        "fonte": "bcb", "serie": "cdi_mensal", "referencia_fonte": 4391,
        "rotulo": "CDI acumulado no mês", "rotulo_curto": "CDI",
    },
    "selic": {
        "fonte": "bcb", "serie": "selic_mensal", "referencia_fonte": 4390,
        "rotulo": "Selic acumulada no mês", "rotulo_curto": "Selic",
    },
    "ipca": {
        "fonte": "bcb", "serie": "ipca_mensal", "referencia_fonte": 433,
        "rotulo": "IPCA mensal", "rotulo_curto": "IPCA",
    },
    "poupanca": {
        "fonte": "bcb", "serie": "poupanca_mensal", "referencia_fonte": 196,
        "rotulo": "Rendimento da poupança", "rotulo_curto": "Poupança",
    },
}


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def gravar(caminho: Path, conteudo: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def modulo_da(definicao: dict):
    nome = definicao["fonte"]
    if nome not in FONTES:
        raise KeyError(f"Fonte '{nome}' nao registrada em FONTES")
    return FONTES[nome]


def coletar_indicadores(quais: set, relatorio: list) -> dict:
    campos = {}
    for chave, definicao in INDICADORES.items():
        if quais and chave not in quais:
            continue
        modulo = modulo_da(definicao)
        # Metadados vao para o arquivo mesmo quando a coleta falha: a pagina
        # precisa saber rotular o campo para poder avisar que ele esta vazio.
        meta = {
            "rotulo": definicao["rotulo"],
            "unidade": definicao["unidade"],
            "fonte": modulo.NOME,
            "referencia_fonte": definicao.get("referencia_fonte"),
        }
        try:
            if definicao["agregacao"] == "acumulado_12m":
                bruto = modulo.acumulado_12m(definicao["serie"])
            else:
                ponto = modulo.ultimo(definicao["serie"])
                bruto = {"valor": ponto["valor"], "referencia": ponto["data"]}
            campos[chave] = {**meta, "valor": bruto["valor"],
                             "origem": "fonte oficial", "referencia": bruto["referencia"]}
            relatorio.append(f"  ok    {chave} = {bruto['valor']} {definicao['unidade']}")
        except modulo.FalhaFonte as erro:
            campos[chave] = {**meta, "valor": None, "origem": "indisponivel", "detalhe": str(erro)}
            relatorio.append(f"  FALHA {chave}: {erro}")
    return campos


def herdar_do_anterior(campos: dict, anterior: dict, relatorio: list) -> dict:
    """Campo que falhou fica com o valor do retrato anterior, marcado como tal."""
    for chave, campo in campos.items():
        if campo.get("valor") is not None:
            continue
        antigo = (anterior.get("campos") or {}).get(chave)
        if antigo and antigo.get("valor") is not None:
            campos[chave] = {
                **campo,
                "valor": antigo["valor"],
                "referencia": antigo.get("referencia"),
                "origem": "retrato anterior (fonte indisponivel na ultima coleta)",
                "coletado_em": anterior.get("coletado_em"),
            }
            relatorio.append(f"  herda {chave} do retrato de {anterior.get('coletado_em')}")
    return campos


def coletar_series(meses: int, quais: set, relatorio: list, anterior: dict) -> list:
    manifesto = []
    indice_anterior = {s["id"]: s for s in (anterior.get("series") or [])}

    for nome, definicao in SERIES.items():
        if quais and nome not in quais:
            continue
        caminho = DIR_SERIES / f"{nome}.json"
        modulo = modulo_da(definicao)
        entrada = {
            "id": nome,
            "rotulo": definicao["rotulo"],
            "rotulo_curto": definicao["rotulo_curto"],
            "arquivo": f"series/{nome}.json",
            "fonte": modulo.NOME,
            "referencia_fonte": definicao.get("referencia_fonte"),
        }
        try:
            pontos = modulo.serie(definicao["serie"], meses=meses)
        except modulo.FalhaFonte as erro:
            relatorio.append(f"  FALHA serie {nome}: {erro} (arquivo anterior preservado)")
            if caminho.exists() and nome in indice_anterior:
                manifesto.append(indice_anterior[nome])
            continue

        gravar(caminho, {**entrada, "coletado_em": agora(), "pontos": pontos})
        manifesto.append({**entrada, "pontos": len(pontos),
                          "primeiro": pontos[0]["data"], "ultimo": pontos[-1]["data"]})
        relatorio.append(f"  ok    serie {nome}: {len(pontos)} pontos ate {pontos[-1]['data']}")

    return manifesto


def main() -> int:
    parser = argparse.ArgumentParser(description="Atualiza os dados de mercado")
    parser.add_argument("--meses", type=int, default=MESES_PADRAO,
                        help=f"quantos meses de historico buscar (padrao {MESES_PADRAO})")
    parser.add_argument("--so", default="",
                        help="coleta so estes indicadores/series, separados por virgula")
    args = parser.parse_args()
    quais = {p.strip() for p in args.so.split(",") if p.strip()}

    caminho = DIR_MERCADO / "indicadores.json"
    anterior = {}
    if caminho.exists():
        try:
            anterior = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    relatorio = [f"Coleta iniciada em {agora()}"]
    campos = herdar_do_anterior(coletar_indicadores(quais, relatorio), anterior, relatorio)
    series = coletar_series(args.meses, quais, relatorio, anterior)

    # Coleta parcial (--so) nao pode apagar o que ja estava no retrato.
    if quais:
        campos = {**(anterior.get("campos") or {}), **campos}
        ids = {s["id"] for s in series}
        series = series + [s for s in (anterior.get("series") or []) if s["id"] not in ids]

    vivos = sum(1 for c in campos.values() if c.get("valor") is not None)
    gravar(caminho, {
        "coletado_em": agora(),
        "completo": vivos == len(campos) and len(series) == len(SERIES),
        "campos": campos,
        "series": series,
    })
    relatorio.append(f"  {vivos}/{len(campos)} indicadores com valor, {len(series)} serie(s)")

    print("\n".join(relatorio))
    if vivos == 0:
        print("\nNenhum indicador coletado. Falhando para o Actions avisar.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
