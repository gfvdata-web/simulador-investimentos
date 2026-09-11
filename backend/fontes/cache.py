"""Cache em arquivo JSON para respostas de fontes externas.

Motivo: as APIs oficiais sao gratuitas mas nao devem ser marteladas a cada
clique na pagina. Tudo que vem da rede passa por aqui e ganha um TTL.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_CACHE = RAIZ / "dados" / "cache"


def _caminho(chave: str) -> Path:
    seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in chave)
    return DIR_CACHE / f"{seguro}.json"


def ler(chave: str, ttl_segundos: int):
    """Devolve o valor cacheado ainda valido, ou None."""
    caminho = _caminho(chave)
    if not caminho.exists():
        return None
    try:
        pacote = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - pacote.get("gravado_em", 0) > ttl_segundos:
        return None
    return pacote.get("valor")


def gravar(chave: str, valor) -> None:
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    pacote = {"gravado_em": time.time(), "valor": valor}
    _caminho(chave).write_text(
        json.dumps(pacote, ensure_ascii=False), encoding="utf-8"
    )


def idade_segundos(chave: str):
    caminho = _caminho(chave)
    if not caminho.exists():
        return None
    try:
        pacote = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return time.time() - pacote.get("gravado_em", 0)
