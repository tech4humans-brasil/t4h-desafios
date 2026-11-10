"""Agente de exemplo: funciona, só que mal.

Ele pega cada pedido e passa tudo para uma pessoa, sem usar IA nenhuma. Serve para
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
    async with Client(URL) as cliente:
        ferramentas = await cliente.list_tools()
        print(f"Conectado. O servidor tem {len(ferramentas.tools)} ferramentas.")
        while True:
            resposta = await chamar(cliente, "proximo_pedido", agente="recepcao")
            pedido = resposta.get("pedido")
            if not pedido:
                if resposta.get("encerrado"):
                    print("O cenário terminou.")
                    return
                await asyncio.sleep(2)
                continue

            print(f"\n{pedido['id']} · {pedido['assunto']}")
            await chamar(
                cliente,
                "registrar_conversa",
                agente="recepcao",
                de="recepcao",
                para="plantao",
                mensagem=f"Chegou o {pedido['id']}. Não sei tratar, vou passar para uma pessoa.",
            )
            r = await chamar(
                cliente,
                "escalar",
                agente="plantao",
                motivo="O agente de exemplo ainda não sabe decidir nada sozinho.",
                pedido_id=pedido["id"],
                resumo=f"{pedido['de']} escreveu: {pedido['assunto']}",
            )
            if r["status"] == "ok":
                print(f"   escalado ({r['protocolo']})")


if __name__ == "__main__":
    asyncio.run(main())
