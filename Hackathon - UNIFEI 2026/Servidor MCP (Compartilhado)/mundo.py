"""Sobe o mundo simulado do Hackathon UNIFEI 2026: servidor MCP + painel ao vivo.

Uso:
    python mundo.py --tema triagem
    python mundo.py --tema equipamentos
    python mundo.py --tema triagem --erros 0 --seed 42
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
import webbrowser
from datetime import datetime

import anyio
import uvicorn
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings
import mcp_types as types

from hackathon.nucleo import Mundo
from hackathon.painel import rotas
from hackathon.temas.equipamentos import Equipamentos
from hackathon.temas.triagem import Triagem

AQUI = pathlib.Path(__file__).resolve().parent
TEMAS = {"triagem": Triagem, "equipamentos": Equipamentos}


def main() -> None:
    parser = argparse.ArgumentParser(description="Mundo simulado do Hackathon UNIFEI 2026")
    parser.add_argument("--tema", required=True, choices=sorted(TEMAS), help="triagem (Tema 1) ou equipamentos (Tema 3)")
    parser.add_argument("--cenario", help="arquivo do cenário (padrão: o de treino do tema)")
    parser.add_argument("--dados", help="pasta com as bases do tema (padrão: dados/<tema>)")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1", help="endereço de escuta (no Docker: 0.0.0.0)")
    parser.add_argument("--erros", type=float, default=0.15, help="chance de falha por chamada, de 0 a 1 (padrão 0.15)")
    parser.add_argument("--seed", type=int, default=None, help="semente: repete os mesmos sorteios")
    parser.add_argument("--segundos-por-dia", type=float, default=None, help="quanto dura um dia de expediente, em segundos reais")
    parser.add_argument("--log", default=None, help="arquivo do log (padrão: logs/<tema>-<data>.jsonl)")
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o painel no navegador")
    parser.add_argument("--sem-cenario", action="store_true", help="não traz os eventos do cenário: só os criados pelo painel")
    args = parser.parse_args()

    tema = TEMAS[args.tema]
    dados = pathlib.Path(args.dados) if args.dados else AQUI / "dados" / args.tema
    cenario_arquivo = pathlib.Path(args.cenario) if args.cenario else dados / "treino.json"
    cenario = json.loads(cenario_arquivo.read_text(encoding="utf-8"))
    args.segundos_por_dia = args.segundos_por_dia or tema.segundos_por_dia_padrao
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
    url = f"http://localhost:{args.porta}"

    print(f"\n  {tema.titulo} · cenário {cenario.get('nome', cenario_arquivo.name)}", file=sys.stderr)
    print(f"  Painel:       {url}/", file=sys.stderr)
    print(f"  Servidor MCP: {url}/mcp", file=sys.stderr)
    print(f"  Só tela:      {url}/legado", file=sys.stderr)
    print(f"  Log:          {mundo.log}", file=sys.stderr)
    print(f"  Um dia de expediente dura {args.segundos_por_dia:.0f} s · chance de falha {mundo.prob_erro:.0%}", file=sys.stderr)
    print("  O relógio começa quando o primeiro agente chamar uma ferramenta.\n", file=sys.stderr)

    if not args.sem_navegador:
        threading.Timer(1.5, lambda: webbrowser.open(f"{url}/")).start()

    async def rodar() -> None:
        config = uvicorn.Config(app, host=args.host, port=args.porta, log_level="warning")
        async with anyio.create_task_group() as grupo:
            grupo.start_soon(mundo.rodar)
            await uvicorn.Server(config).serve()
            grupo.cancel_scope.cancel()

    anyio.run(rodar)


if __name__ == "__main__":
    main()
