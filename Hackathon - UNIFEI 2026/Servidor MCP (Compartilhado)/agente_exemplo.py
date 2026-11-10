"""Agente de exemplo: funciona, só que mal.

Ele pega cada evento e só responde que recebeu, sem usar IA nenhuma. Serve para
mostrar como conectar ao servidor MCP, como mandar 'agente' e 'motivo' e como lidar
com as falhas simuladas. O trabalho do seu time é fazer muito melhor que isso.

Uso (com o mundo rodando em outro terminal):
    python agente_exemplo.py
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import Client

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/mcp"


async def chamar(cliente: Client, ferramenta: str, **argumentos) -> dict:
    """Chama uma ferramenta e tenta de novo quando a falha é passageira."""
    for tentativa in range(1, 4):
        resultado = await cliente.call_tool(ferramenta, argumentos)
        resposta = json.loads(resultado.content[0].text)
        if resposta["status"] == "ok":
            return resposta
        codigo = resposta.get("codigo")
        print(f"   ! {ferramenta} falhou ({codigo}): {resposta['mensagem']}")
        if codigo == 504:
            return resposta  # a ação pode ter sido feita: quem chamou decide se confere antes de repetir
        if codigo not in (503, 409):
            return resposta  # erro de regra: tentar de novo igual não adianta
        await asyncio.sleep(2 * tentativa)
    return resposta


async def main() -> None:
    for tentativa in range(1, 16):
        try:
            async with Client(URL) as cliente:
                await trabalhar(cliente)
            return
        except Exception as erro:  # o servidor ainda não subiu
            if tentativa == 15:
                raise
            print(f"Esperando o servidor em {URL}... ({type(erro).__name__})")
            await asyncio.sleep(2)


async def trabalhar(cliente: Client) -> None:
    ferramentas = await cliente.list_tools()
    print(f"Conectado. O servidor tem {len(ferramentas.tools)} ferramentas.")
    bases = await chamar(cliente, "listar_bases", agente="recepcao")
    print("Bases do mundo:", ", ".join(b["base"] for b in bases.get("bases", [])))
    while True:
        resposta = await chamar(cliente, "proximo_evento", agente="recepcao")
        evento = resposta.get("evento")
        if not evento:
            if resposta.get("encerrado"):
                print("O cenário terminou.")
                return
            await asyncio.sleep(2)
            continue

        print(f"\n{evento['id']} · {evento['assunto']}")
        await chamar(
            cliente,
            "registrar_conversa",
            agente="recepcao",
            de="recepcao",
            para="resposta",
            mensagem=f"Chegou o {evento['id']}. Não sei o que fazer, só vou avisar que recebemos.",
        )
        r = await chamar(
            cliente,
            "responder_evento",
            agente="resposta",
            motivo="O agente de exemplo ainda não sabe decidir nada.",
            evento_id=evento["id"],
            mensagem="Recebemos sua mensagem. Alguém vai olhar em breve.",
        )
        if r["status"] == "ok":
            print("   respondido")


if __name__ == "__main__":
    asyncio.run(main())
