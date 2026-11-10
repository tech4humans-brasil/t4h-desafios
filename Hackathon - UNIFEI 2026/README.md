# Hackathon UNIFEI 2026 - Desafios Técnicos

No dia 14/11/2026, um sábado, times de alunos da UNIFEI têm 7 horas para construir um time de colaboradores digitais: agentes de IA que trabalham como colegas, cada um com um papel, conversando entre si para dividir as tarefas e revisar o trabalho um do outro. Cada time escolhe um tema, conecta os agentes ao servidor do hackathon e, no fim, apresenta o que construiu.

Este README traz o desafio, as regras e o que entregar. O [servidor MCP](Servidor%20MCP%20%28Compartilhado%29/) e cada tema têm o próprio README.

## Prazo e entrega

- **Quando:** 14/11/2026, na UNIFEI, com 7 horas de evento. Horário e sala: A definir.
- **Kit publicado até:** A definir.
- **Como entregar:** o link do repositório do time e uma apresentação de 5 minutos. Detalhes em [O que entregar](#o-que-entregar).
- **Dúvidas:** A definir.

## O desafio

Um colaborador digital é um agente de IA que trabalha como um colega: recebe um pedido, decide o que fazer, age usando ferramentas e registra por que fez cada coisa. O que separa um bom colaborador digital de um chatbot é saber o limite de cada ação:

| Nível | O que o agente faz | Exemplo |
| --- | --- | --- |
| Faz sozinho | Executa e registra o motivo | Responder uma dúvida que está no FAQ |
| Propõe | Registra uma proposta e só executa depois do OK de uma pessoa | Cancelar um pedido duplicado |
| Só escala | Não age: passa para uma pessoa, com o contexto pronto | Suspeita de golpe |

A proposta é montar os agentes como uma equipe de verdade: cada um com um papel, dividindo os pedidos, revisando o trabalho do outro antes de uma ação importante e chamando uma pessoa quando o caso não é deles.

**Para assistir antes:** [Stanford CS146S: How always-on agents work](https://youtu.be/L1OBRtfPS34), por leerob.

## Os temas

| Tema | O que o time de agentes faz | Situação |
| --- | --- | --- |
| [1 — Triagem N1 de chamados e incidentes](Triagem%20N1%20%28Chamados%20e%20incidentes%29/) | Faz o primeiro atendimento dos pedidos internos: entende, responde, encaminha e separa o incidente de verdade | Pronto |
| 2 — Admissão de novo colaborador | Conduz a entrada de uma pessoa nova até o primeiro dia, cobrando cada etapa | Em preparação |
| [3 — Gestão de equipamentos](Gest%C3%A3o%20de%20equipamentos%20%28Parque%20de%20TI%29/) | Cuida do parque de notebooks, monitores e periféricos: atende, aloca, compra e cobra devolução | Pronto |

## Antes de chegar

Traga o notebook com o kit já rodando: a primeira meia hora do dia não é para instalar nada.

1. **Crie uma conta no GitHub**, se ainda não tiver.
2. **Instale** Git e Docker Desktop. Sem Docker, Python 3.11 ou mais novo também serve. Os agentes podem ser na linguagem que o time quiser.
3. **Baixe o kit:**

   ```bash
   git clone https://github.com/tech4humans-brasil/t4h-desafios.git
   ```

   Tudo do evento fica nesta pasta, `Hackathon - UNIFEI 2026`.
4. **Suba o mundo e rode o agente de exemplo**, como explica o [README do servidor](Servidor%20MCP%20%28Compartilhado%29/). Se as chamadas dele aparecerem no painel, está tudo certo.

**Crédito de IA.** Cada time recebe no dia uma chave de API com crédito para o modelo de IA oferecido pela T4H. A chave fica num arquivo `.env` fora do Git: nunca a coloque no código nem no repositório.

## Regras

**Times.** De 4 a 5 pessoas. A escolha do tema é feita na abertura.

**O que pode**

- Qualquer linguagem, framework de agente, biblioteca e assistente de código.
- Qualquer modelo de IA; o crédito garantido é o que entregamos no dia.
- Criar dados extras de teste a partir dos do kit.

**O que não pode**

- Usar dados reais de pessoas ou empresas. Tudo no kit é fictício, e deve continuar assim.
- Alterar o servidor MCP do kit.
- Escrever no código a resposta de cada pedido do treino.
- Alguém do time intervir enquanto os agentes rodam. Pessoa só entra quando um agente propõe ou escala, e quem responde é o servidor.

## O que entregar

1. O link do repositório do time.
2. Um `README.md` que explica como rodar os agentes com um comando e qual é o papel de cada um.
3. Um motivo em toda ação: cada chamada ao servidor leva o `motivo` e o nome do agente que agiu, e as conversas entre os agentes também aparecem no log.
4. Uma apresentação de 5 minutos, com os agentes rodando ao vivo: como eles dividem o trabalho, um caso em que um agente corrigiu outro, um caso em que o time chamou uma pessoa e o que fariam com mais tempo.

## Estrutura

```
Hackathon - UNIFEI 2026/
├── README.md                                  # este arquivo: o desafio, as regras e a entrega
├── Servidor MCP (Compartilhado)/              # o mundo simulado, igual para todos os temas
│   ├── README.md                              # como funciona, como rodar e como conectar
│   ├── compose.yaml e Dockerfile              # para rodar com Docker
│   ├── mundo.py                               # sobe o servidor MCP e o painel
│   ├── agente_exemplo.py                      # agente que funciona, só que mal
│   ├── ver_log.py                             # resume o log de uma rodada
│   ├── hackathon/                             # o motor e as ferramentas de cada tema
│   └── dados/                                 # as bases fictícias de cada tema
├── Triagem N1 (Chamados e incidentes)/
│   └── README.md                              # Tema 1
└── Gestão de equipamentos (Parque de TI)/
    └── README.md                              # Tema 3
```

### [Servidor MCP (Compartilhado)](Servidor%20MCP%20%28Compartilhado%29/)

A empresa simulada onde os agentes trabalham, com o painel ao vivo:

- `README.md`: o que é, o ciclo de um pedido, as ferramentas, como rodar com Docker ou sem e como conectar o agente
- `compose.yaml` e `Dockerfile`: sobem o servidor sem instalar Python
- `mundo.py`: sobe o servidor MCP e o painel do tema escolhido
- `agente_exemplo.py`: um agente sem IA que escala tudo, para testar a conexão
- `ver_log.py`: resume o log de uma rodada
- `hackathon/` e `dados/`: o motor do mundo e as bases fictícias de cada tema

### 1. [Triagem N1 (Chamados e incidentes)](Triagem%20N1%20%28Chamados%20e%20incidentes%29/)

- `README.md`: a história, o que tem no mundo, o que o time precisa saber, os níveis de entrega e os erros graves

### 2. Admissão de novo colaborador (em preparação)

O tema entra aqui quando estiver pronto.

### 3. [Gestão de equipamentos (Parque de TI)](Gest%C3%A3o%20de%20equipamentos%20%28Parque%20de%20TI%29/)

- `README.md`: a história, o que tem no mundo, as regras, os níveis de entrega e os erros graves

## Como Utilizar

1. Leia este README: as regras valem para todos os temas
2. Leia o README do servidor e suba o mundo no seu notebook
3. Escolha um tema e leia o README da pasta dele
4. No dia, construa o time de agentes e teste no cenário de treino
5. Entregue o link do repositório e apresente o que o time construiu

## Observações Importantes

- Todos os dados do kit são fictícios. Não use dados reais de pessoas ou empresas
- Nunca commite a chave de API nem o arquivo `.env`
- Em caso de dúvidas, use o canal indicado em [Prazo e entrega](#prazo-e-entrega)

Boa sorte no hackathon!
