# Agente de exemplo (LangGraph)

O menor agente possível em [LangGraph](https://langchain-ai.github.io/langgraph/) conectado ao servidor MCP do Hackathon: carrega as ferramentas do servidor, recebe um "oi" e responde. Serve para conferir que o ambiente funciona e como base para o time construir o resto.

## Como rodar

1. Suba o servidor (veja o [README do servidor](../Servidor%20MCP%20%28Compartilhado%29/README.md)):

   ```bash
   TEMA=triagem docker compose up --build mundo
   ```

2. Em outro terminal, dentro desta pasta, com Python 3.11 ou mais novo, num ambiente virtual separado do servidor (o servidor usa o SDK `mcp` 2.x e o `langchain-mcp-adapters` usa a 1.x):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # no Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env             # no Windows: copy .env.example .env
   ```

3. Preencha no `.env` o endereço e a chave do gateway LiteLLM, entregues pela organização, e rode:

   ```bash
   python agente.py
   ```

A saída esperada é a lista de ferramentas do servidor e a resposta do modelo ao "oi".

## Configuração (`.env`)

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `LITELLM_URL` | (obrigatória) | Endereço do gateway LiteLLM |
| `LITELLM_API_KEY` | (obrigatória) | Chave do time no gateway |
| `MODELO` | `openai:gpt-4o-mini` | Modelo no formato `provedor:modelo` do `init_chat_model` |
| `MCP_URL` | `http://localhost:8765/mcp` | Endereço do servidor MCP |
| `NOME_AGENTE` | `exemplo-langgraph` | Nome que o agente usa no campo `agente` das ferramentas (aparece no painel) |

## Como funciona

O `agente.py` faz três coisas:

1. `MultiServerMCPClient`, do `langchain-mcp-adapters`, conecta em `/mcp` e transforma as ferramentas do servidor em ferramentas do LangChain.
2. `init_chat_model` cria o modelo apontando para o LiteLLM, que fala o protocolo da OpenAI.
3. `create_agent` monta o grafo LangGraph (modelo e ferramentas em ciclo) e manda a mensagem "oi".

Daqui em diante é com o time: o laço que chama `proximo_evento` até `encerrado: true`, o tratamento das falhas do servidor, a memória, os papéis dos agentes e o resto descrito no README do servidor.
