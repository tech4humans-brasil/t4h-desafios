# Tema 1 — Triagem N1 de chamados e incidentes

Um time de agentes lê cada pedido interno que chega por e-mail, decide a ação certa e deixa para uma pessoa só o que é dela.

As regras gerais, a entrega e a avaliação estão no [README do hackathon](../README.md).

## A história

Na T4H, os pedidos internos chegam o dia todo: acesso a sistema, equipamento, férias, suporte aos produtos. Muitos vêm no tipo errado, sem informação ou repetidos, e no meio deles pode estar um sistema fora do ar que precisa de atenção já. O desafio é montar um time de agentes que faça essa primeira leitura.

## O que tem no mundo deste tema

| O que existe | O que é |
| --- | --- |
| Caixa de entrada | ~60 e-mails de treino que chegam ao longo de 5 dias de expediente: dúvidas, pedidos, duplicados, urgências falsas, pedidos incompletos e alguns incidentes de verdade |
| FAQ | 15 respostas prontas |
| Catálogo | Os 8 tipos de chamado da tabela abaixo |
| Times | Os times da empresa e o que cada um atende |
| Chamados já abertos | O que já estava em andamento antes do cenário, útil para achar duplicados |

Os agentes consultam e agem pelas ferramentas do [servidor MCP](../Servidor%20MCP%20%28Compartilhado%29/), que aparecem na lista ao conectar. Para subir este tema: `python mundo.py --tema triagem`. O mundo também reage: quem pediu responde quando o agente pede informação e cobra quando fica sem resposta, e o gestor aprova ou recusa chamados e propostas. O cenário da banca tem ~40 e-mails inéditos no mesmo formato.

## Os tipos de chamado

Todo pedido que vira chamado precisa de um tipo e dos campos obrigatórios dele. O agente nunca aprova: a aprovação é de uma pessoa.

| Tipo | Time | Campos obrigatórios | Aprovação | Prazo |
| --- | --- | --- | --- | --- |
| Acesso a sistema | Segurança | sistema, nível de acesso, justificativa | Gestor de quem pediu | 2 dias úteis |
| Retirada de acessos | Segurança | pessoa, data de saída | Gestor | 1 dia útil |
| Novo equipamento | Infraestrutura | item, motivo | Gestor | 10 dias úteis |
| Troca de equipamento | Infraestrutura | item, patrimônio, defeito | Não precisa | 5 dias úteis |
| Férias | Pessoas | data de início, data de fim | Gestor | 5 dias úteis |
| Reembolso | Financeiro | valor, data, comprovante | Gestor | 5 dias úteis |
| Suporte a produto | Produto | produto, o que aconteceu, desde quando | Não precisa | Pela criticidade |
| Outros pedidos | Operações | descrição | Não precisa | 5 dias úteis |

## Criticidade de incidente

Urgência no assunto do e-mail não é criticidade. A criticidade vem do impacto.

| Criticidade | Quando | O que o agente faz |
| --- | --- | --- |
| P0 | Produto fora do ar para todos os clientes | Abre o incidente e escala na hora |
| P1 | Função importante fora para muitos clientes | Abre o incidente e escala na hora |
| P2 | Falha parcial, com contorno | Abre o incidente |
| P3 | Falha para um cliente ou uma pessoa | Abre chamado de Suporte a produto |
| P4 | Dúvida ou pedido de melhoria | Responde ou abre chamado de Suporte a produto |
| Não é incidente | Pedido comum, mesmo que escrito como urgente | Trata como pedido pelo catálogo |

Suspeita de incidente de segurança (e-mail falso, vazamento, acesso indevido) e pedido com dado pessoal sensível vão sempre para uma pessoa, sem nenhuma outra ação.

## Um exemplo

Chega este e-mail do treino:

```text
De: marina@t4h.exemplo
Assunto: URGENTE!!! acesso
Preciso de acesso ao sistema financeiro hoje, é urgente!
```

Um agente faz a triagem e passa o caso para outro, que age:

```json
[
  {
    "ferramenta": "registrar_conversa",
    "agente": "triador",
    "de": "triador",
    "para": "atendente",
    "mensagem": "Acesso a sistema sem nível de acesso e justificativa. A urgência é só do assunto: não é incidente."
  },
  {
    "ferramenta": "pedir_informacao",
    "agente": "atendente",
    "motivo": "Faltam campos obrigatórios do tipo Acesso a sistema.",
    "pedido_id": "PED-017",
    "campos": ["nivel_de_acesso", "justificativa"],
    "mensagem": "Oi, Marina! Para liberar, preciso saber o nível de acesso (leitura ou edição) e para que você vai usar."
  }
]
```

## Níveis de entrega

- **Mínimo:** pelo menos dois agentes com papéis diferentes passam por todos os e-mails e decidem uma ação para cada um, com motivo.
- **Bom:** responde citando o FAQ, junta os duplicados, pede o que falta, acerta a criticidade e tem um agente revisando o trabalho dos outros antes de agir.
- **Excelente:** uma tela de abertura de chamado caindo no mesmo agente, ou um painel do que está esperando uma pessoa.

## Erros graves

- Deixar passar um incidente P0 ou P1, ou classificá-lo abaixo disso.
- Agir sozinho num caso de segurança ou de dado pessoal.
- Responder com informação que não está no FAQ.
