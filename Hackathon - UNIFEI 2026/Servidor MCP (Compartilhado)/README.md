# Mundo do hackathon (servidor MCP)

É o mundo onde os seus agentes trabalham. Ele entrega os pedidos ao longo do dia, guarda as bases de dados do tema, reage ao que os agentes fazem e mostra tudo ao vivo num painel no navegador. O seu time só precisa construir os agentes.

Tudo aqui é fictício: pessoas, e-mails, produtos e equipamentos.

## Como subir

```bash
cd "Hackathon - UNIFEI 2026/Servidor MCP (Compartilhado)"
python -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python mundo.py --tema triagem   # ou: python mundo.py --tema equipamentos
```

O painel abre sozinho no navegador. Os endereços:

| O quê | Endereço |
| --- | --- |
| Painel ao vivo | `http://127.0.0.1:8765/` |
| Servidor MCP (Streamable HTTP) | `http://127.0.0.1:8765/mcp` |

O relógio só começa quando o primeiro agente chama uma ferramenta. Todos os agentes do time usam o mesmo servidor, então todos veem o mesmo mundo.

## Como conectar os seus agentes

Qualquer cliente MCP que fale Streamable HTTP funciona. Dois jeitos comuns:

```python
from mcp import Client

async with Client("http://127.0.0.1:8765/mcp") as cliente:
    ferramentas = await cliente.list_tools()
    pedido = await cliente.call_tool("proximo_pedido", {"agente": "triador"})
```

```bash
claude mcp add --transport http hackathon http://127.0.0.1:8765/mcp
```

Para conferir se está tudo certo, rode o agente de exemplo num segundo terminal: `python agente_exemplo.py`. Ele escala tudo para uma pessoa, sem usar IA. Funciona, só que mal.

## As regras de toda chamada

- Toda chamada leva o campo `agente`, com o nome do agente do seu time que está agindo.
- Toda ação, ou seja, tudo que muda o mundo, leva também o campo `motivo`.
- Ações que precisam do OK de uma pessoa só passam com o id de uma proposta aprovada. Primeiro o agente chama `propor`; a decisão chega depois na caixa de entrada.
- As ferramentas de cada tema aparecem na lista do MCP, com a descrição e os parâmetros de cada uma.

## O que o mundo faz sozinho

- Os pedidos chegam ao longo do expediente simulado, não todos de uma vez.
- As pessoas respondem: quem pediu manda o que faltava, cobra quando fica sem resposta e devolve (ou não) o equipamento cobrado.
- O gestor aprova ou recusa propostas e chamados depois de algumas horas simuladas.
- No Tema 3, compras chegam no prazo do fornecedor e o mundo confere o kit de cada pessoa no primeiro dia dela.

## As falhas

Por padrão, 15% das chamadas falham ou demoram, como num sistema de verdade:

| Falha | O que o agente precisa fazer |
| --- | --- |
| Erro 503 | Tentar de novo |
| Lento | Esperar; a resposta chega certa, só que depois de alguns segundos |
| Erro 504 | Conferir antes de repetir, porque a ação pode ter sido feita ou não |
| Erro 409 | Consultar de novo antes de agir |

Erros de regra (400, 403, 404, 422) não são sorteados: dizem o que estava errado no pedido do agente.

## Opções

| Opção | Para quê |
| --- | --- |
| `--erros 0` | Desliga as falhas simuladas (o padrão é `0.15`) |
| `--segundos-por-dia 60` | Muda quanto dura um dia de expediente. O padrão é 240 s no Tema 1 (5 dias em 20 min) e 60 s no Tema 3 (22 dias em 22 min) |
| `--seed 42` | Repete os mesmos sorteios a cada rodada |
| `--porta 9000` | Muda a porta |
| `--sem-navegador` | Não abre o painel sozinho |
| `--cenario arquivo.json` e `--dados pasta/` | Usa outro cenário ou outras bases, como a banca faz no fim do dia |

## Ver o log

Cada rodada grava tudo em `logs/<tema>-<data>.jsonl`: chamadas, respostas, conversas e alertas. Para ler o mais recente:

```bash
python ver_log.py
python ver_log.py --erros
python ver_log.py --agente triador
```

A banca lê este mesmo log no fim do dia.
