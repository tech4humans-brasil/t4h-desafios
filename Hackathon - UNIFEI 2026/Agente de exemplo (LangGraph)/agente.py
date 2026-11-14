"""Agente de exemplo em LangGraph: conecta no servidor MCP do Hackathon e responde a um "oi".

    python agente.py

Configuração no arquivo .env (veja .env.example).
"""

import asyncio
import os
from datetime import timedelta

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

MCP_URL = os.getenv("MCP_URL", "http://localhost:8765/mcp")
MODELO = os.getenv("MODELO", "openai:gpt-4o-mini")
NOME_AGENTE = os.getenv("NOME_AGENTE", "exemplo-langgraph")


async def main(modelo=None) -> None:
    # 1. Conecta no servidor MCP e transforma as ferramentas dele em ferramentas do LangChain
    cliente = MultiServerMCPClient(
        {"mundo": {"transport": "streamable_http", "url": MCP_URL, "timeout": timedelta(seconds=60)}}
    )
    ferramentas = await cliente.get_tools()
    print(f"Conectado a {MCP_URL}: {len(ferramentas)} ferramentas ({', '.join(f.name for f in ferramentas)})")

    # 2. O modelo vem pelo gateway LiteLLM, que fala o protocolo da OpenAI
    modelo = modelo or init_chat_model(
        MODELO,
        base_url=os.environ["LITELLM_URL"],
        api_key=os.environ["LITELLM_API_KEY"],
    )

    # 3. Monta o agente (um grafo LangGraph: modelo <-> ferramentas) e manda um "oi"
    agente = create_agent(
        modelo,
        ferramentas,
        system_prompt=f"Você é um agente do hackathon. Ao chamar qualquer ferramenta, use agente='{NOME_AGENTE}'.",
    )
    resultado = await agente.ainvoke({"messages": [{"role": "user", "content": "oi"}]})
    print(resultado["messages"][-1].text)


if __name__ == "__main__":
    asyncio.run(main())
