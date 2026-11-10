"""Sobe o mundo simulado do Hackathon UNIFEI 2026: servidor MCP + painel ao vivo.

Uso:
    python mundo.py --tema triagem
    python mundo.py --tema equipamentos
    python mundo.py --tema triagem --erros 0 --seed 42
    TEMA=equipamentos ERROS=0 python mundo.py
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import socket
import sys
import webbrowser
from datetime import datetime

import anyio
import uvicorn
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings
import mcp_types as types

from hackathon.nucleo import Mundo
from hackathon.painel import rotas
from hackathon.temas.admissao import Admissao
from hackathon.temas.equipamentos import Equipamentos
from hackathon.temas.triagem import Triagem

AQUI = pathlib.Path(__file__).resolve().parent
TEMAS = {"triagem": Triagem, "admissao": Admissao, "equipamentos": Equipamentos}


def env(nome: str, padrao=None):
    valor = os.environ.get(nome, "").strip()
    return valor if valor else padrao


def sair(mensagem: str) -> None:
    print(f"\n  Erro: {mensagem}\n", file=sys.stderr)
    raise SystemExit(2)


def porta_ocupada(host: str, porta: int) -> bool:
    with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, porta))
        except OSError:
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mundo simulado do Hackathon UNIFEI 2026. Toda opção também pode vir de variável de ambiente (entre colchetes)."
    )
    parser.add_argument("--tema", default=env("TEMA"), choices=sorted(TEMAS), help="triagem (Tema 1), admissao (Tema 2) ou equipamentos (Tema 3) [TEMA]")
    parser.add_argument("--cenario", default=env("CENARIO"), help="arquivo do cenário (padrão: o de treino do tema) [CENARIO]")
    parser.add_argument("--dados", default=env("DADOS"), help="pasta com as bases do tema (padrão: dados/<tema>) [DADOS]")
    parser.add_argument("--porta", type=int, default=int(env("PORTA", 8765)), help="porta (padrão 8765) [PORTA]")
    parser.add_argument("--host", default=env("HOST", "127.0.0.1"), help="endereço de escuta; 0.0.0.0 aceita conexões de fora da máquina [HOST]")
    parser.add_argument("--erros", type=float, default=float(env("ERROS", 0.15)), help="chance de falha por chamada, de 0 a 1 (padrão 0.15) [ERROS]")
    parser.add_argument("--seed", type=int, default=int(env("SEED")) if env("SEED") else None, help="semente: repete os mesmos sorteios [SEED]")
    parser.add_argument(
        "--segundos-por-dia",
        type=float,
        default=float(env("SEGUNDOS_POR_DIA")) if env("SEGUNDOS_POR_DIA") else None,
        help="quanto dura um dia de expediente, em segundos reais [SEGUNDOS_POR_DIA]",
    )
    parser.add_argument("--log", default=env("LOG"), help="arquivo do log (padrão: logs/<tema>-<data>.jsonl) [LOG]")
    parser.add_argument("--sem-navegador", action="store_true", default=bool(env("SEM_NAVEGADOR")), help="não abre o painel no navegador [SEM_NAVEGADOR=1]")
    parser.add_argument(
        "--sem-cenario", action="store_true", default=bool(env("SEM_CENARIO")), help="não traz os eventos do cenário: só os do painel [SEM_CENARIO=1]"
    )
    args = parser.parse_args()

    if not args.tema:
        parser.error("informe o tema: --tema triagem, admissao ou equipamentos (ou a variável TEMA)")
    if not 0 <= args.erros <= 1:
        parser.error("--erros vai de 0 a 1 (0.15 = 15% das chamadas falham)")
    if args.segundos_por_dia is not None and args.segundos_por_dia <= 0:
        parser.error("--segundos-por-dia precisa ser maior que zero")
    if not 1 <= args.porta <= 65535:
        parser.error("--porta vai de 1 a 65535")

    tema = TEMAS[args.tema]
    dados = pathlib.Path(args.dados) if args.dados else AQUI / "dados" / args.tema
    cenario_arquivo = pathlib.Path(args.cenario) if args.cenario else dados / "treino.json"
    if not dados.is_dir():
        sair(f"a pasta de dados {dados} não existe.")
    try:
        cenario = json.loads(cenario_arquivo.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sair(f"o cenário {cenario_arquivo} não existe.")
    except json.JSONDecodeError as e:
        sair(f"o cenário {cenario_arquivo} não é um JSON válido ({e}).")
    faltam = [k for k in ("inicio", "dias", "pedidos") if k not in cenario]
    if faltam:
        sair(f"o cenário {cenario_arquivo} não tem: {', '.join(faltam)}.")
    if cenario.get("tema") and cenario["tema"] != args.tema:
        sair(f"o cenário {cenario_arquivo.name} é do tema '{cenario['tema']}', não de '{args.tema}'.")
    if porta_ocupada(args.host, args.porta):
        sair(f"a porta {args.porta} já está em uso. Feche o outro servidor ou use --porta (ou PORTA) com outro número.")
    args.segundos_por_dia = args.segundos_por_dia or tema.segundos_por_dia_padrao
    args.porta_publica = int(env("PORTA_PUBLICA", args.porta))  # no Docker, a porta do lado de fora
    args.log = args.log or str(AQUI / "logs" / f"{args.tema}-{datetime.now():%Y%m%d-%H%M%S}.jsonl")

    mundo = Mundo(tema, cenario, dados, args)

    async def listar(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[f.como_tool() for f in mundo.ferramentas.values()])

    async def chamar(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        return await mundo.chamar(params.name, params.arguments)

    servidor = Server(
        "hackathon-unifei-2026",
        version="1.0.0",
        instructions=(
            f"{tema.titulo}. Mundo simulado do Hackathon UNIFEI 2026, com dados fictícios. "
            "Pegue eventos com proximo_evento, veja as bases com listar_bases e aja com consultar, registrar, atualizar, "
            "responder_evento e enviar_mensagem. Toda chamada leva 'agente'. Alguns sistemas só têm tela, em /legado. "
            "O servidor às vezes falha de propósito: trate os erros."
        ),
        on_list_tools=listar,
        on_call_tool=chamar,
    )
    seguranca = None
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        # No Docker o servidor escuta em 0.0.0.0 e recebe Host de outros nomes (localhost, mundo).
        seguranca = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    app = servidor.streamable_http_app(custom_starlette_routes=rotas(mundo), host=args.host, transport_security=seguranca)
    url = f"http://localhost:{args.porta_publica}"

    print(f"\n  {tema.titulo} · cenário {cenario.get('nome', cenario_arquivo.name)}", file=sys.stderr)
    print(f"  Painel:       {url}/", file=sys.stderr)
    print(f"  Servidor MCP: {url}/mcp", file=sys.stderr)
    print(f"  Só tela:      {url}/legado", file=sys.stderr)
    print(f"  Log:          {mundo.log}", file=sys.stderr)
    print(f"  Um dia de expediente dura {args.segundos_por_dia:.0f} s · chance de falha {mundo.prob_erro:.0%}", file=sys.stderr)
    print("  O relógio começa quando o primeiro agente chamar uma ferramenta.\n", file=sys.stderr)

    print("  Para parar: Ctrl+C.\n", file=sys.stderr)

    async def abrir_navegador(servidor_http: uvicorn.Server) -> None:
        while not servidor_http.started:
            await anyio.sleep(0.2)
        if not args.sem_navegador:
            webbrowser.open(f"{url}/")

    async def rodar() -> None:
        config = uvicorn.Config(app, host=args.host, port=args.porta, log_level="warning")
        servidor_http = uvicorn.Server(config)
        async with anyio.create_task_group() as grupo:
            grupo.start_soon(mundo.rodar)
            grupo.start_soon(abrir_navegador, servidor_http)
            await servidor_http.serve()
            grupo.cancel_scope.cancel()

    anyio.run(rodar)


if __name__ == "__main__":
    main()
