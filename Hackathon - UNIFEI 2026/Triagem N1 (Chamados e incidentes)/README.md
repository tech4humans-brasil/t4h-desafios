# Tema 1 — Triagem N1 (ficha técnica)

Como o servidor se comporta neste tema. O enunciado do desafio está no documento oficial do evento.

## Como subir

Na pasta do [servidor MCP](../Servidor%20MCP%20%28Compartilhado%29/):

```bash
TEMA=triagem docker compose up --build mundo
```

Ou, sem Docker: `python mundo.py --tema triagem`. O cenário de treino tem ~60 eventos ao longo de 5 dias de expediente, a partir de 07/12/2026. Por padrão, um dia de expediente dura 4 minutos e o cenário inteiro, 20.

## As bases

| Base | Chave | O que tem | Registrar | Atualizar |
| --- | --- | --- | --- | --- |
| `eventos` | `id` | Tudo o que chegou para o time | Não | `status`, `observacao` |
| `faq` | `id` | 15 respostas prontas | Não | Não |
| `catalogo` | `tipo` | 8 tipos de chamado, com time, campos obrigatórios, aprovação e prazo | Não | Não |
| `times` | `time` | Times da empresa, o que atendem e o e-mail de cada um | Não | Não |
| `chamados` | `id` | Chamados que já existiam e os que o time abrir | Sim | `status`, `observacao`, `pedidos`, `aprovador` |
| `incidentes` | `id` | Incidentes abertos pelo time | Sim | `status`, `observacao`, `pedidos`, `criticidade` |

Validações:

- `registrar` em `chamados` exige `tipo` do catálogo e todos os campos obrigatórios do tipo, dentro de `campos` ou soltos em `dados`. O tipo Férias é recusado: férias só pelo sistema de férias. Campos que o servidor não usa voltam em `campos_ignorados`.
- `registrar` em `incidentes` exige `criticidade` P0, P1 ou P2 e um `resumo`.
- `status` de chamado ou incidente: `aberto`, `em andamento`, `aguardando`, `aguardando aprovação`, `resolvido` ou `cancelado` (com ou sem acento).
- `pedidos` recebe um id de evento (ou uma lista) e acrescenta à lista do chamado. O evento precisa existir, e ligar um evento a um chamado conta como atendimento dele.
- `observacao` aceita até 2.000 caracteres.

## Sistema de férias (só tela)

`http://localhost:8765/legado/ferias`: um formulário com quem está lançando, e-mail do colaborador, primeiro e último dia (formato DD/MM/AAAA, validado) e evento relacionado. Cada lançamento gera um protocolo `FER-...` e aparece na tabela da própria tela. A tela recusa datas no passado e férias que se sobrepõem a outras da mesma pessoa. Não existe API para isso.

## O que o mundo faz sozinho

- **Respostas:** `responder_evento` com `aguardar_resposta: true`, ou `enviar_mensagem` para quem mandou o evento, faz a pessoa responder depois, como evento novo. Se faltava informação, a resposta traz o que faltava.
- **Cobranças:** alguns eventos, quando ficam sem nenhuma ação por um tempo, geram uma cobrança de quem pediu e um alerta no painel.
- **Mensagens para fora:** responder ou mandar mensagem para um endereço fora de `@t4h.exemplo` gera um alerta grave no painel, e ninguém de fora responde.
- **Times:** mensagens para o e-mail de um time (base `times`) são entregues, mas o time não responde. Endereço que não é de um time nem de quem mandou um evento dá 404.
- **Aprovações:** nenhum gestor responde pelo servidor. Como o time pede e registra uma aprovação é decisão do time.
