# Hackathon UNIFEI 2026 - Desafios Técnicos

Kit técnico do Hackathon UNIFEI 2026: um servidor MCP que simula uma empresa fictícia, com eventos chegando ao longo de um expediente simulado, bases de dados, sistemas só com tela e um painel ao vivo. Os times constroem agentes de IA que se conectam a esse servidor.

O enunciado dos desafios, as regras e o que entregar estão no documento oficial do evento, entregue aos participantes. Este README cobre só a parte técnica.

## Prazo e entrega

- **Quando:** 14/11/2026, na UNIFEI.
- **Como entregar:** conforme o documento oficial do evento.
- **Dúvidas:** A definir.

## Estrutura

```
Hackathon - UNIFEI 2026/
├── README.md                                  # este arquivo
├── Servidor MCP (Compartilhado)/              # o servidor, igual para todos os temas
│   ├── README.md                              # como rodar e como funciona
│   ├── compose.yaml e Dockerfile              # para rodar com Docker
│   ├── mundo.py                               # sobe o servidor MCP, o painel e as telas
│   ├── ver_log.py                             # resume o log de uma rodada
│   ├── hackathon/                             # o motor, o painel, as telas e os temas
│   └── dados/                                 # as bases fictícias de cada tema
├── Triagem N1 (Chamados e incidentes)/
│   └── README.md                              # ficha técnica do Tema 1
├── Admissão (Onboarding CLT)/
│   └── README.md                              # ficha técnica do Tema 2
└── Gestão de equipamentos (Parque de TI)/
    └── README.md                              # ficha técnica do Tema 3
```

### [Servidor MCP (Compartilhado)](Servidor%20MCP%20%28Compartilhado%29/)

- `README.md`: como rodar com Docker ou sem, quem chama quem, as ferramentas, os eventos, as telas sem API, as falhas e o log
- `compose.yaml` e `Dockerfile`: sobem o servidor sem instalar Python
- `mundo.py`: sobe o servidor do tema escolhido
- `ver_log.py`: resume o log de uma rodada
- `hackathon/` e `dados/`: o código do mundo e as bases fictícias

### 1. [Triagem N1 (Chamados e incidentes)](Triagem%20N1%20%28Chamados%20e%20incidentes%29/)

- `README.md`: como subir o tema, as bases, o sistema de férias (só tela) e o que o mundo faz sozinho

### 2. [Admissão (Onboarding CLT)](Admiss%C3%A3o%20%28Onboarding%20CLT%29/)

- `README.md`: como subir o tema, as bases, quem responde a quê, o portal da contabilidade (só tela) e o que o mundo faz sozinho

### 3. [Gestão de equipamentos (Parque de TI)](Gest%C3%A3o%20de%20equipamentos%20%28Parque%20de%20TI%29/)

- `README.md`: como subir o tema, as bases, o portal do fornecedor (só tela) e o que o mundo faz sozinho

## Como Utilizar

1. Clone o repositório: `git clone https://github.com/tech4humans-brasil/t4h-desafios.git`
2. Entre em `Hackathon - UNIFEI 2026/Servidor MCP (Compartilhado)` e siga o README para subir o servidor
3. Abra o painel em `http://localhost:8765` para conferir que o servidor está no ar
4. Leia a ficha técnica do tema escolhido

## Observações Importantes

- Todos os dados são fictícios: pessoas, e-mails, documentos, produtos e equipamentos
- Nunca commite chaves de API nem arquivos `.env`
- Não altere o servidor: os agentes do time é que precisam se adaptar a ele
