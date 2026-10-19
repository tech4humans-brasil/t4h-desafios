# Vaga Estágio Pesquisa e Inovação 2026 - Desafios Técnicos

Desafio de seleção para a vaga de estágio em Pesquisa e Inovação da Tech for Humans. Você recebe uma aplicação lenta, pesquisa o estado da arte, melhora a aplicação com evidência e entrega um artigo, um repositório e um vídeo explicando por que chegou nessa solução. O enunciado completo, com as entregas e os critérios de avaliação, é enviado na largada. Este README cobre só como rodar e medir a aplicação.

A aplicação é a API de uma loja fictícia, em Node.js (Express) com PostgreSQL 16, rodando em containers. Ela funciona, mas fica lenta sob carga e gasta mais recursos do que deveria. Todos os dados são sintéticos e gerados na primeira subida: 100 mil clientes, 20 mil produtos, 500 mil pedidos e 1,5 milhão de itens de pedido.

## Prazo e entrega

- **Prazo:** 14 dias corridos a partir da largada
- **Entrega:** artigo, repositório e vídeo, enviados pelo formulário indicado no enunciado

## Estrutura

```
Vaga - Estágio Pesquisa e Inovação 2026/
├── AGENTS.md                  # instruções para agentes de IA (o CLAUDE.md aponta para ele)
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

O `up -d` só termina quando o banco está pronto para uso. Na primeira vez o banco gera os dados antes, o que leva de alguns segundos a 3 minutos, conforme a máquina. Para acompanhar, em outro terminal: `docker compose logs -f banco` (Ctrl+C para sair).

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

- O código da API e o `Dockerfile`
- O `docker-compose.yml`: limites de CPU e memória, configuração dos serviços e serviços novos, como um cache
- As consultas, os índices, a estrutura das tabelas e a configuração do banco

Mais recurso custa mais. Se você aumentar o limite de CPU ou de memória de um container, ou adicionar um serviço, o ganho vem junto com um custo maior, e a comparação precisa mostrar os dois. O `medir.sh` coleta CPU e memória de todos os serviços do `docker-compose.yml` e registra os limites de cada um em `contexto.txt`.

**O que não pode mudar:**

- O que cada rota devolve, incluindo status HTTP, campos, valores e ordem. O verificador de contrato existe para provar isso.
- As ferramentas de medição: `carga/`, `contrato/verificar.js` e `scripts/`, e o `contrato/base.json` depois de gravado. Mudar a régua invalida a comparação.
- Os dados: `banco/01-estrutura.sql` e `banco/02-dados.sql` ficam como estão. Mudanças no banco vão em arquivos novos, como `banco/03-indices.sql` (veja [Voltar ao estado original](#voltar-ao-estado-original)).

## Como medir

O ciclo é sempre o mesmo: meça antes, mude uma coisa e meça depois.

**1. Grave o contrato, uma única vez, antes de mudar qualquer coisa:**

```bash
scripts/verificar-contrato.sh gravar
```

Ele chama 42 casos de teste e salva as respostas da aplicação original em `contrato/base.json`. Faça commit desse arquivo antes de qualquer mudança.

**2. Meça a linha de base:**

```bash
scripts/medir.sh 00-linha-de-base
```

O script faz um aquecimento de 15 segundos, que não entra no resultado, e depois roda 20 usuários virtuais por 60 segundos, cada um fazendo requisições em sequência, sem pausa. Enquanto isso, coleta o uso de CPU e memória dos containers. Cada medição leva cerca de 1 min 30 s. O resultado vai para `resultados/<data>-<rotulo>/`:

| Arquivo | Conteúdo |
| --- | --- |
| `resumo.txt` | Requisições por segundo, erros e tempo de resposta (mediana, p95, p99), no geral e por rota |
| `recursos.txt` | CPU e memória, média e máximo, de cada container durante a carga |
| `recursos.csv` | As amostras de CPU e memória usadas no `recursos.txt` |
| `contexto.txt` | Parâmetros da medição, commit e limites dos containers |
| `contrato.txt` | Saída do verificador de contrato, rodado logo depois da carga. A última linha diz se o contrato foi mantido |
| `resumo-k6.json` | Todas as métricas do k6 |

Commite a linha de base antes da primeira mudança.

**3. Para cada mudança:**

1. Faça a mudança e commite. Assim o `contexto.txt` registra o commit medido e mostra `arquivos alterados sem commit: 0`.
2. Aplique e confira o contrato:

    ```bash
    docker compose up -d --build            # mudanças na API, no Dockerfile ou no compose
    # arquivo .sql novo em banco/: docker compose down -v && docker compose up -d --build
    scripts/verificar-contrato.sh comparar  # precisa terminar em "Contrato mantido"
    ```

3. Meça pelo menos 3 vezes com o mesmo rótulo: `scripts/medir.sh 01-<o-que-mudou>`.
4. Commite as pastas de `resultados/` dessa mudança em um commit separado.

Os parâmetros da carga podem ser alterados por variáveis de ambiente. Use os mesmos valores em todas as medições que você for comparar.

| Variável | Padrão | O que controla |
| --- | --- | --- |
| `VUS` | `20` | Usuários virtuais simultâneos |
| `DURACAO` | `60s` | Duração da medição |
| `AQUECIMENTO` | `15s` | Duração do aquecimento |
| `SEMENTE` | `42` | Semente do sorteio das URLs. A mesma semente repete as mesmas requisições |
| `PORTA_API` | `3000` | Porta da API na sua máquina, usada só para conferir se ela está no ar |

Exemplo: `VUS=50 DURACAO=120s scripts/medir.sh 05-carga-maior`

**Para a comparação ser justa:** meça sempre na mesma máquina, com os outros programas pesados fechados. Rode cada medição pelo menos 3 vezes e compare a mediana das execuções. Entre uma execução e outra, a diferença pode passar de 30%.

Na linha de base, algumas rotas são tão lentas que têm poucas requisições em 60 segundos. Nelas, os números por rota oscilam muito: use o resultado geral, ou aumente `DURACAO` em todas as medições.

## Acessar o banco

```bash
docker compose exec banco psql -U loja -d loja
```

Também dá para conectar de fora, por exemplo com DBeaver ou pgAdmin: host `127.0.0.1`, porta `5432`, usuário `loja`, banco `loja`, sem senha. A porta só aceita conexões da sua máquina.

Os logs da API ficam em `docker compose logs -f api`.

Para mudar parâmetros do PostgreSQL de um jeito que outra pessoa consiga repetir, passe cada um com `-c` no serviço `banco` do `docker-compose.yml`:

```yaml
  banco:
    image: postgres:16.4
    command: ["postgres", "-c", "shared_buffers=128MB"]
```

Aplique com `docker compose up -d`: o banco reinicia sem perder os dados. Para conferir o valor em uso: `docker compose exec banco psql -U loja -d loja -c 'SHOW shared_buffers;'`

## Voltar ao estado original

```bash
docker compose down -v      # apaga o banco
docker compose up -d --build
```

Tudo o que você fizer direto no `psql` se perde quando o banco é apagado. Para que outra pessoa consiga repetir o seu experimento, registre essas mudanças em um arquivo `.sql` dentro de `banco/`. Os arquivos dessa pasta rodam em ordem alfabética, só quando o banco é criado do zero.

## Entregar o experimento

1. Copie só esta pasta para a raiz de um repositório público seu. O resto do t4h-desafios é de outros processos seletivos e não faz parte do teste.
2. Faça commit das suas mudanças, do `contrato/base.json` e das pastas de `resultados/`, sem editar os arquivos gerados. Faça um commit por mudança, seguido do commit com os resultados dela.
3. Acrescente a este README uma seção com o problema e o resumo dos seus resultados. Mantenha as instruções de subir e medir, para que outra pessoa consiga repetir.
4. Coloque o link do repositório no artigo.

## Usar um agente de IA

O [AGENTS.md](AGENTS.md) resume, para agentes como Claude Code, Codex ou Cursor, como rodar e medir a aplicação e o que não pode ser mudado. Ele não traz o enunciado: passe o enunciado para o agente junto com o seu pedido.

Abra o agente dentro da sua cópia desta pasta. Na raiz do t4h-desafios, o `CLAUDE.md` e a pasta `.claude/` são de quem mantém o repositório e não valem para o desafio.

## Problemas comuns

- **Porta 5432 ou 3000 em uso:** pare o outro serviço ou troque o lado esquerdo do mapeamento em `ports:` no `docker-compose.yml`. Se trocar a porta da API, rode as medições com a nova porta, por exemplo `PORTA_API=3001 scripts/medir.sh 00-linha-de-base`.
- **`medir.sh` diz que a API não respondeu:** veja se o banco já terminou de gerar os dados (`docker compose logs banco`).
- **Erro `bash\r` ou `$'\r': command not found` no Windows:** o Git converteu as quebras de linha. Rode `git config core.autocrlf false` e clone de novo.

## Observações Importantes

- Leia o enunciado inteiro antes de começar
- Mantenha-se dentro do prazo
- Em caso de dúvidas, use o canal combinado na largada

Boa sorte no seu desafio!
