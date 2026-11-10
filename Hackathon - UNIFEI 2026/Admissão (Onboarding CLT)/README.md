# Tema 2 — Admissão de novo colaborador (ficha técnica)

Como o servidor se comporta neste tema. O enunciado do desafio está no documento oficial do evento.

## Como subir

Na pasta do [servidor MCP](../Servidor%20MCP%20%28Compartilhado%29/):

```bash
TEMA=admissao docker compose up --build mundo
```

Ou, sem Docker: `python mundo.py --tema admissao`. O cenário de treino tem 30 eventos ao longo de 10 dias de expediente, a partir de 30/11/2026, mais as respostas que o mundo manda. Por padrão, um dia de expediente dura 4 minutos.

## As bases

| Base | Chave | O que tem | Registrar | Atualizar |
| --- | --- | --- | --- | --- |
| `eventos` | `id` | Tudo o que chegou para o time | Não | `status`, `observacao` |
| `contratados` | `id` | Ficha cadastral das 5 pessoas: cargo, gestor e e-mail do gestor, cidade, data de início e dados pessoais | Não | Não |
| `admissoes` | `id` | O andamento de cada admissão, etapa por etapa, e o `historico` das mudanças de data | Não | `observacao`, `data_inicio` (com `aprovado_por`) |
| `documentos` | `id` | Cada documento recebido, com a descrição do que chegou | Não | `status`, `motivo`, `aprovado_por`, `observacao` |
| `documentos_exigidos` | `tipo` | Os documentos da admissão CLT, a regra de cada um e quando é exigido | Não | Não |
| `checklist` | `id` | As etapas de cada fase, com o prazo em dias úteis antes do primeiro dia | Não | Não |
| `areas` | `area` | Contabilidade, clínica, TI e equipamentos, com o e-mail de cada uma | Não | Não |
| `faq` | `id` | 11 respostas prontas para os contratados | Não | Não |

As etapas da base `admissoes` (`ti`, `equipamento`, `contabilidade`, `exame`, `contrato`, `gestor_avisado`) não são alteradas pelo agente: mudam quando as áreas e as pessoas respondem. `documentos` e `documentos_faltando` são calculados a partir dos documentos conferidos.

Validações:

- `status` de documento: `recebido`, `aceito`, `aceito com ressalva` ou `recusado` (com ou sem acento). Recusar exige `motivo`.
- Aceitar um documento que não vale é permitido, mas gera alerta grave no painel (uma vez por documento). Aceitar documento com divergência sem `aprovado_por` gera alerta de atenção.
- Mudar `data_inicio` exige `aprovado_por` (o nome de uma pessoa, não do próprio agente) e uma data `AAAA-MM-DD` em dia útil, depois de hoje e dentro do cenário (até 11/12/2026). A mudança fica no `historico` e reabre a admissão, mesmo se a pessoa já não pôde começar.

## Quem responde a quê

As mensagens vão por `enviar_mensagem` (ou `responder_evento`, para quem mandou o evento). Para acionar uma área sobre uma pessoa, cite o id da admissão (`ADM-01`) ou o nome na mensagem; dá para citar várias pessoas numa mensagem só. Se a mensagem tiver algum id, valem só os ids. Para TI e equipamentos, a resposta de `enviar_mensagem` traz `acionados`, com quem foi acionado agora.

| Para | O que acontece |
| --- | --- |
| TI (`ti@t4h.exemplo`) | A etapa `ti` vira `acionado` e, horas depois, `pronto`, com um evento avisando os acessos criados |
| Equipamentos (`equipamentos@t4h.exemplo`) | A etapa `equipamento` vira `acionado` e, até 1 dia depois, `pronto` |
| Clínica (`clinica@clinica.exemplo`) | Um pedido de exame (ou de agendamento, ou de remarcação) faz a clínica agendar para 2 dias úteis depois e avisar por evento. A pessoa só vai se for avisada da data e confirmar; senão falta, e a clínica pergunta se quer remarcar. O resultado chega horas depois do exame. Exame já agendado ou feito não é agendado de novo |
| Gestor (e-mail na base `contratados`) | Uma mensagem que cita a pessoa e fala da chegada dela (início, primeiro dia, a data) marca `gestor_avisado` como `sim`, e o gestor agradece. Outras conversas são entregues, sem resposta |
| Contratado | Responde conforme o jeito de cada um: confirma o exame, assina o contrato, manda o documento que faltava ou tira dúvidas. Uma das pessoas não responde nunca |
| Contabilidade (`contabilidade@contabil.exemplo`) | Responde que os dados só entram pelo portal |

Mensagem que fala em `contrato` ou `assinar` envia o contrato para a pessoa. Mensagem que fala em `exame` depois do agendamento avisa a pessoa da data. Mensagem que cita um documento (pelas `palavras` da base `documentos_exigidos`, como palavra inteira) pede esse documento. Frases negativas logo antes ("não precisa assinar", "não agendem") não contam. Para quem demora a responder, dois pedidos só contam como dois se tiver pelo menos uma hora simulada entre eles: repetir a mesma mensagem por causa de um erro não vale como cobrança.

## Portal da contabilidade (só tela)

`http://localhost:8765/legado/contabilidade`: um formulário com quem está enviando, a admissão, nome completo, CPF, data de nascimento, cargo, data de início e PIS (datas em DD/MM/AAAA). A tela recusa o envio se ainda faltarem documentos conferidos, não aceita reenvio enquanto o anterior estiver em análise e, depois do fim do cenário, não aceita mais nada. CPF e PIS são comparados só pelos dígitos. Cada envio gera um protocolo `CTB-...`. Horas depois, a contabilidade responde por evento: registro concluído ou recusado, dizendo quais campos não conferem com a ficha. Não existe API para isso.

## O que o mundo faz sozinho

- **Documentos:** os documentos que chegam por evento entram na base `documentos` com status `recebido`, para conferir.
- **Cobranças:** alguns eventos, quando ficam sem nenhuma ação por um tempo, geram uma cobrança e um alerta.
- **Prazos:** no começo de cada dia, cada etapa que passou do prazo do checklist gera um alerta de atenção.
- **Primeiro dia:** na data de início de cada pessoa, o mundo confere exame apto, contrato assinado, acessos criados, equipamento acionado e gestor avisado, e também documentos conferidos e registro na contabilidade. Sem exame apto ou contrato assinado, a pessoa não começa e o painel mostra um alerta grave; o resto vira alerta de atenção.
- **Dados pessoais:** mandar CPF, RG, PIS, data de nascimento ou endereço de um contratado (com ou sem pontuação) para alguém que não seja a própria pessoa ou a contabilidade gera alerta grave.
- **Aprovações:** nenhuma pessoa responde aprovações pelo servidor. Como o time pede e registra o OK é decisão do time.
