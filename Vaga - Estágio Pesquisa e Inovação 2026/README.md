# Vaga Estágio Pesquisa e Inovação 2026 - Desafios Técnicos

Desafio de seleção para a vaga de estágio em Pesquisa e Inovação da Tech for Humans. Você recebe uma aplicação lenta, pesquisa o estado da arte, melhora a aplicação com evidência e entrega um artigo e um vídeo explicando por que chegou nessa solução. O enunciado completo, com as entregas e os critérios de avaliação, está em [`Desafio Performance.pdf`](Desafio%20Performance.pdf).

A aplicação é a API de uma loja fictícia, em Node.js (Express) com PostgreSQL 16, rodando em containers. Ela funciona, mas fica lenta sob carga e gasta mais recursos do que deveria. Todos os dados são sintéticos e gerados na primeira subida: 100 mil clientes, 20 mil produtos, 500 mil pedidos e 1,5 milhão de itens de pedido.

## Prazo e entrega

- **Prazo:** 14 dias corridos a partir da largada

## Estrutura

```
Vaga - Estágio Pesquisa e Inovação 2026/
├── Desafio Performance.pdf    # enunciado
├── docker-compose.yml         # API, banco e as ferramentas de medição
├── api/                       # código da API (Express + pg) e Dockerfile
├── banco/                     # scripts que criam as tabelas e geram os dados
├── carga/teste-carga.js       # teste de carga (k6)
├── contrato/verificar.js      # confere se as respostas da API continuam iguais
├── scripts/
│   ├── medir.sh               # roda a carga e salva o resultado
│   └── verificar-contrato.sh  # grava e compara as respostas da API
└── resultados/                # cada medição cria uma pasta aqui
```

## Requisitos

- Docker Desktop, ou Docker Engine com Compose v2 (`docker compose version`)
- Cerca de 2 GB livres em disco
- `bash` e `curl`. No Windows, use WSL 2 ou Git Bash.

Não precisa instalar Node.js, PostgreSQL nem k6: tudo roda em containers.

## Subir a aplicação

Rode os comandos dentro desta pasta:

```bash
docker compose up -d --build
curl http://127.0.0.1:3000/saude      # {"status":"ok"}
```

Na primeira vez o banco gera os dados antes de aceitar conexões, o que leva de 1 a 3 minutos. Para acompanhar: `docker compose logs -f banco` e espere a linha `Banco pronto.`

## Rotas

| Rota | Parâmetros | Devolve |
| --- | --- | --- |
| `GET /saude` | | `{"status":"ok"}` |
| `GET /clientes/:id` | | Um cliente |
| `GET /clientes?email=` | `email`, sem diferenciar maiúsculas | Lista de clientes com esse e-mail |
| `GET /clientes/:id/pedidos` | | Pedidos do cliente, do mais recente para o mais antigo, com itens e total |
| `GET /pedidos?status=&pagina=` | `status`: `pago`, `entregue`, `cancelado` ou `pendente`; `pagina` a partir de 1 | Página de 20 pedidos, do mais recente para o mais antigo, e o total do status |
| `GET /produtos/busca?q=` | `q` com pelo menos 3 caracteres | Até 20 produtos cujo nome contém o termo |
| `GET /relatorios/vendas-por-dia?inicio=&fim=` | datas `AAAA-MM-DD`, período de até 31 dias | Pedidos, itens e receita por dia, sem pedidos cancelados |
| `GET /relatorios/top-produtos?limite=` | `limite` de 1 a 50, padrão 10 | Produtos com maior receita, sem pedidos cancelados |

Valores em dinheiro estão em centavos. Datas saem em UTC.

## O que você pode mudar

- O código da API, o `Dockerfile` e os limites dos containers no `docker-compose.yml`
- As consultas, os índices e a configuração do banco

**O que não pode mudar:** o que cada rota devolve, incluindo status HTTP, campos, valores e ordem. O verificador de contrato existe para provar isso.

## Como medir

O ciclo é sempre o mesmo: meça antes, mude uma coisa e meça depois.

**1. Grave o contrato, uma única vez, antes de mudar qualquer coisa:**

```bash
scripts/verificar-contrato.sh gravar
```

Ele chama 42 casos de teste e salva as respostas da aplicação original em `contrato/base.json`. Faça commit desse arquivo.

**2. Meça a linha de base:**

```bash
scripts/medir.sh 00-linha-de-base
```

O script faz um aquecimento de 15 segundos, que não entra no resultado, e depois roda 20 usuários virtuais por 60 segundos, cada um fazendo requisições em sequência, sem pausa. Enquanto isso, coleta o uso de CPU e memória dos containers. O resultado vai para `resultados/<data>-<rotulo>/`:

| Arquivo | Conteúdo |
| --- | --- |
| `resumo.txt` | Requisições por segundo, erros e tempo de resposta (mediana, p95, p99), no geral e por rota |
| `recursos.txt` | CPU e memória, média e máximo, de cada container durante a carga |
| `recursos.csv` | As amostras de CPU e memória usadas no `recursos.txt` |
| `contexto.txt` | Parâmetros da medição, commit e limites dos containers |
| `resumo-k6.json` | Todas as métricas do k6 |

**3. Para cada mudança:**

```bash
docker compose up -d --build            # aplica mudanças na API, no Dockerfile ou no compose
scripts/verificar-contrato.sh comparar  # precisa terminar em "Contrato mantido"
scripts/medir.sh 01-<o-que-mudou>
```

Os parâmetros da carga podem ser alterados por variáveis de ambiente. Use os mesmos valores em todas as medições que você for comparar.

| Variável | Padrão | O que controla |
| --- | --- | --- |
| `VUS` | `20` | Usuários virtuais simultâneos |
| `DURACAO` | `60s` | Duração da medição |
| `AQUECIMENTO` | `15s` | Duração do aquecimento |
| `SEMENTE` | `42` | Semente do sorteio das URLs. A mesma semente repete as mesmas requisições |

Exemplo: `VUS=50 DURACAO=120s scripts/medir.sh 05-carga-maior`

**Para a comparação ser justa:** meça sempre na mesma máquina, com os outros programas pesados fechados, e rode cada medição mais de uma vez. Entre uma execução e outra, a diferença pode passar de 30%.

## Acessar o banco

```bash
docker compose exec banco psql -U loja -d loja
```

Também dá para conectar de fora, por exemplo com DBeaver ou pgAdmin: host `127.0.0.1`, porta `5432`, usuário `loja`, banco `loja`, sem senha. A porta só aceita conexões da sua máquina.

Os logs da API ficam em `docker compose logs -f api`.

## Voltar ao estado original

```bash
docker compose down -v      # apaga o banco
docker compose up -d --build
```

Tudo o que você fizer direto no `psql` se perde quando o banco é apagado. Para que outra pessoa consiga repetir o seu experimento, registre essas mudanças em um arquivo `.sql` dentro de `banco/`. Os arquivos dessa pasta rodam em ordem alfabética, só quando o banco é criado do zero.

## Entregar o experimento

1. Faça um fork deste repositório, ou copie esta pasta para um repositório público seu.
2. Faça commit das suas mudanças, do `contrato/base.json` e das pastas de `resultados/`. Prefira um commit por mudança.
3. Coloque o link do repositório no artigo.

## Problemas comuns

- **Porta 5432 ou 3000 em uso:** pare o outro serviço ou troque o lado esquerdo do mapeamento em `ports:` no `docker-compose.yml`. Se trocar a porta da API, o `scripts/medir.sh` também precisa usar a nova porta.
- **`medir.sh` diz que a API não respondeu:** veja se o banco já terminou de gerar os dados (`docker compose logs banco`).
- **Erro `bash\r` ou `$'\r': command not found` no Windows:** o Git converteu as quebras de linha. Rode `git config core.autocrlf false` e clone de novo.

## Observações Importantes

- Leia o enunciado inteiro antes de começar
- Mantenha-se dentro do prazo
- Em caso de dúvidas, use o canal indicado em [Prazo e entrega](#prazo-e-entrega)

Boa sorte no seu desafio!
