# Tema 1 — Triagem N1 de chamados e incidentes

Um time de agentes faz o primeiro atendimento dos pedidos internos: entende cada e-mail, responde, encaminha, abre chamado ou incidente e deixa para uma pessoa só o que é dela. Para subir o mundo deste tema, na pasta do [servidor MCP](../Servidor%20MCP%20%28Compartilhado%29/): `TEMA=triagem docker compose up mundo`.

As regras gerais e a entrega estão no [README do hackathon](../README.md).

## A história

Na T4H, os pedidos internos chegam o dia todo: acesso a sistema, equipamento, férias, suporte aos produtos. Muitos vêm no tipo errado, sem informação ou repetidos, e no meio deles pode estar um sistema fora do ar que precisa de atenção já.

## O que tem no mundo

| O que existe | O que é |
| --- | --- |
| Caixa de entrada | ~60 e-mails ao longo de 5 dias: dúvidas, pedidos, duplicados, urgências falsas, pedidos incompletos e alguns incidentes de verdade |
| FAQ | 15 respostas prontas |
| Catálogo | 8 tipos de chamado, cada um com time, campos obrigatórios, aprovação e prazo |
| Times | Os times da empresa e o que cada um atende |
| Chamados já abertos | O que já estava em andamento, útil para achar duplicados |

O mundo reage: quem pediu responde quando o agente pede informação e cobra quando fica sem resposta, e o gestor aprova ou recusa chamados e propostas.

## O que o time precisa saber

- Chamado só abre com um tipo do catálogo e todos os campos obrigatórios dele.
- Urgência no assunto não é criticidade. A criticidade vem do impacto:

| Criticidade | Quando | O que fazer |
| --- | --- | --- |
| P0 | Produto fora do ar para todos os clientes | Abrir incidente e escalar na hora |
| P1 | Função importante fora para muitos clientes | Abrir incidente e escalar na hora |
| P2 | Falha parcial, com contorno | Abrir incidente |
| P3 e P4 | Falha para uma pessoa, dúvida ou melhoria | Chamado de Suporte a produto, ou resposta |

- Suspeita de golpe, vazamento ou acesso indevido e pedido com dado pessoal sensível vão sempre para uma pessoa.
- O agente nunca aprova nada: aprovação é de uma pessoa.

## Níveis de entrega

- **Mínimo:** pelo menos dois agentes com papéis diferentes passam por todos os e-mails e decidem uma ação para cada um, com motivo.
- **Bom:** respondem com o FAQ, juntam duplicados, pedem o que falta, acertam a criticidade e um agente revisa o trabalho dos outros antes de agir.
- **Excelente:** uma tela de abertura de chamado caindo no mesmo time de agentes, ou um painel do que está esperando uma pessoa.

## Erros graves

- Deixar passar um incidente P0 ou P1, ou classificá-lo abaixo disso.
- Agir sozinho num caso de segurança ou de dado pessoal.
- Responder com informação que não está no FAQ.
