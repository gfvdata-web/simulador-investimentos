"""Servidor local do Simulador de Investimentos.

Zero dependencias: usa apenas a biblioteca padrao do Python. Serve a pagina
estatica de /web e expoe a API em /api/*.

Uso:
    python -m backend.app            # http://127.0.0.1:8765
    python -m backend.app --porta 9000 --sem-navegador

O servidor escuta apenas em 127.0.0.1: nada deste projeto fica exposto na rede.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import traceback
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend import dados
    from backend.engine import motor
    from backend.fontes import bcb_sgs
else:
    from . import dados
    from .engine import motor
    from .fontes import bcb_sgs

RAIZ = Path(__file__).resolve().parents[1]
DIR_WEB = RAIZ / "web"
PORTA_PADRAO = 8765
LIMITE_CORPO = 256 * 1024


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIR_WEB), **kwargs)

    # --- roteamento -------------------------------------------------------
    def do_GET(self):
        rota = urlparse(self.path).path
        if rota.startswith("/api/"):
            self._tratar_api_get(rota)
            return
        super().do_GET()

    def do_POST(self):
        rota = urlparse(self.path).path
        if rota == "/api/simular":
            self._proteger(self._simular)
        else:
            self._json({"erro": f"Rota nao encontrada: {rota}"}, 404)

    def _tratar_api_get(self, rota: str):
        rotas = {
            "/api/saude": self._saude,
            "/api/indicadores": self._indicadores,
            "/api/ativos": self._ativos,
            "/api/premissas": self._premissas,
            "/api/historico": self._historico,
        }
        alvo = rotas.get(rota)
        if alvo is None:
            self._json({"erro": f"Rota nao encontrada: {rota}"}, 404)
            return
        self._proteger(alvo)

    # --- endpoints --------------------------------------------------------
    def _saude(self):
        self._json({"status": "ok", "versao": "0.1.0", "web": DIR_WEB.exists()})

    def _indicadores(self):
        forcar = self._query().get("atualizar", ["0"])[0] == "1"
        self._json(dados.indicadores(forcar_atualizacao=forcar))

    def _ativos(self):
        self._json(dados.catalogo())

    def _premissas(self):
        self._json(dados.premissas())

    def _historico(self):
        consulta = self._query()
        serie = consulta.get("serie", ["cdi"])[0]
        meses = int(consulta.get("meses", ["60"])[0])
        try:
            self._json(dados.historico(serie, meses))
        except bcb_sgs.FalhaFonte as erro:
            self._json({"erro": "Fonte oficial indisponivel", "detalhe": str(erro)}, 503)

    def _simular(self):
        corpo = self._corpo_json()
        ids = corpo.get("ativos") or []
        if not ids:
            self._json({"erro": "Selecione ao menos um ativo"}, 400)
            return

        catalogo = dados.ativos_por_id()
        desconhecidos = [i for i in ids if i not in catalogo]
        if desconhecidos:
            self._json({"erro": f"Ativos desconhecidos: {', '.join(desconhecidos)}"}, 400)
            return

        premissas = dados.premissas()
        padroes = premissas.get("defaults_simulacao", {})
        try:
            parametros = {
                "valor_inicial": float(corpo.get("valor_inicial", padroes.get("valor_inicial", 100))),
                "aporte_mensal": float(corpo.get("aporte_mensal", padroes.get("aporte_mensal", 0))),
                "meses": int(corpo.get("meses", padroes.get("meses", 12))),
                "cenario": str(corpo.get("cenario", padroes.get("cenario", "base"))),
                "considerar_ir": bool(corpo.get("considerar_ir", padroes.get("considerar_ir", True))),
                "considerar_inflacao": bool(
                    corpo.get("considerar_inflacao", padroes.get("considerar_inflacao", True))
                ),
            }
        except (TypeError, ValueError) as erro:
            self._json({"erro": f"Parametro invalido: {erro}"}, 400)
            return

        indicadores = dados.indicadores()
        try:
            saida = motor.comparar(
                [catalogo[i] for i in ids], indicadores, premissas, **parametros
            )
        except ValueError as erro:
            self._json({"erro": str(erro)}, 400)
            return

        saida["parametros"] = parametros
        saida["indicadores"] = {
            k: v for k, v in indicadores.items() if not k.startswith("_")
        }
        saida["procedencia"] = indicadores["_origem"]
        saida["dados_degradados"] = indicadores["_degradado"]
        self._json(saida)

    # --- utilidades -------------------------------------------------------
    def _query(self) -> dict:
        return parse_qs(urlparse(self.path).query)

    def _corpo_json(self) -> dict:
        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho <= 0:
            return {}
        if tamanho > LIMITE_CORPO:
            raise ValueError("Corpo da requisicao grande demais")
        return json.loads(self.rfile.read(tamanho).decode("utf-8"))

    def _json(self, dados_resposta, status: int = 200):
        corpo = json.dumps(dados_resposta, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _proteger(self, funcao):
        try:
            funcao()
        except json.JSONDecodeError:
            self._json({"erro": "JSON invalido no corpo da requisicao"}, 400)
        except (ValueError, KeyError) as erro:
            self._json({"erro": str(erro)}, 400)
        except Exception as erro:  # noqa: BLE001 - servidor local, log completo ajuda
            traceback.print_exc()
            self._json({"erro": "Erro interno", "detalhe": str(erro)}, 500)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, formato, *args):
        sys.stderr.write("  %s\n" % (formato % args))


def executar(porta: int = PORTA_PADRAO, abrir_navegador: bool = True):
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    url = f"http://127.0.0.1:{porta}/"
    print("Simulador de Investimentos")
    print(f"  servindo  {url}")
    print(f"  pagina    {DIR_WEB}")
    print("  Ctrl+C para parar\n")
    if abrir_navegador:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor local do simulador")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    parser.add_argument("--sem-navegador", action="store_true")
    args = parser.parse_args()
    executar(args.porta, abrir_navegador=not args.sem_navegador)
