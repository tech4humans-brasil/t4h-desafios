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
- Git
- Cerca de 2 GB livres em disco
- `bash` e `curl`. No macOS e no Linux já vêm instalados. No Windows, use o WSL 2.

Não precisa instalar Node.js, PostgreSQL nem k6: tudo roda em containers.

Se você já usa Docker e Git no dia a dia, pule para [Criar a sua cópia do desafio](#4-criar-a-sua-cópia-do-desafio). Se é a primeira vez, siga o passo a passo abaixo, na ordem.

## Passo a passo do zero

Nenhum passo pressupõe experiência anterior. Cada um termina com um comando para você conferir se deu certo antes de seguir.

### 1. Abrir um terminal

Todos os comandos deste README são digitados no terminal: uma janela onde você escreve um comando, aperta Enter e lê a resposta.

- **macOS:** abra o app **Terminal** (Cmd+Espaço, digite "Terminal"). [Guia do Terminal da Apple](https://support.apple.com/pt-br/guide/terminal/apd5265185d-f365-44cb-8b09-71a064a42125/mac).
- **Windows:** instale o WSL 2, que roda um Linux (Ubuntu) dentro do Windows, seguindo o [guia da Microsoft](https://learn.microsoft.com/pt-br/windows/wsl/install). Na prática, abra o PowerShell como administrador, rode `wsl --install`, reinicie e crie um usuário e uma senha quando o Ubuntu abrir. Depois disso, abra sempre o app **Ubuntu** e rode todos os comandos lá dentro, não no PowerShell nem no Prompt de Comando.
- **Linux:** abra o terminal da sua distribuição (no Ubuntu, Ctrl+Alt+T).

Três comandos que você vai usar o tempo todo:

```bash
pwd          # mostra em que pasta você está
ls           # lista os arquivos da pasta
cd pasta     # entra em uma pasta; "cd .." volta uma pasta
```

Se o nome da pasta tiver espaços ou acentos, coloque entre aspas: `cd "Minha Pasta"`. Para começar do básico, a MDN tem um [curso rápido de linha de comando](https://developer.mozilla.org/en-US/docs/Learn_web_development/Getting_started/Environment_setup/Command_line) (em inglês).

### 2. Instalar e configurar o Git

O Git guarda o histórico das suas mudanças. Neste desafio ele é parte da medição: cada resultado registra o commit que foi medido.

- **macOS:** rode `git --version`. Se não estiver instalado, o próprio sistema oferece a instalação.
- **Windows (dentro do Ubuntu do WSL) e Linux:** `sudo apt update && sudo apt install -y git`
- Outras opções em [git-scm.com/downloads](https://git-scm.com/downloads).

Depois, diga ao Git quem você é. Isso aparece em cada commit:

```bash
git config --global user.name "Seu Nome"
git config --global user.email "seu-email@exemplo.com"
git --version     # confere: deve mostrar algo como "git version 2.x"
```

Referências: [configurar o Git (GitHub Docs)](https://docs.github.com/pt/get-started/git-basics/set-up-git) e o livro [Pro Git em português](https://git-scm.com/book/pt-br/v2), gratuito.

### 3. Instalar o Docker

O Docker roda programas dentro de **containers**: ambientes isolados que já vêm com tudo o que o programa precisa. É por isso que você não instala Node.js nem PostgreSQL: a API e o banco rodam cada um no seu container. Para entender a ideia em poucos minutos, leia a [visão geral do Docker](https://docs.docker.com/get-started/docker-overview/) (em inglês).

- **macOS:** instale o [Docker Desktop para Mac](https://docs.docker.com/desktop/setup/install/mac-install/). Escolha a versão do seu processador: Apple (M1, M2…) ou Intel.
- **Windows:** instale o [Docker Desktop para Windows](https://docs.docker.com/desktop/setup/install/windows-install/) e, nas configurações, confirme que a [integração com o WSL 2](https://docs.docker.com/desktop/features/wsl/) está ligada para o Ubuntu (Settings → Resources → WSL integration).
- **Linux:** instale o [Docker Engine](https://docs.docker.com/engine/install/) da sua distribuição, que já traz o Compose, e siga os [passos pós-instalação](https://docs.docker.com/engine/install/linux-postinstall/) para rodar `docker` sem `sudo`.

No macOS e no Windows, o Docker Desktop precisa estar aberto (ícone da baleia na barra) para os comandos funcionarem. Confira:

```bash
docker --version          # Docker version 2x.x.x
docker compose version    # Docker Compose version v2.x.x
docker run hello-world    # baixa uma imagem de teste e imprime "Hello from Docker!"
```

Se os três funcionarem, o Docker está pronto.

### 4. Criar a sua cópia do desafio

O desafio é só esta pasta. Você baixa o repositório t4h-desafios, copia a pasta para um lugar seu e transforma a cópia em um repositório Git próprio, que depois vai para o seu GitHub.

No Windows, rode isto dentro do Ubuntu e deixe os arquivos na sua pasta pessoal do Linux (`cd ~`), não em `C:\` (`/mnt/c/...`), onde tudo fica bem mais lento.

```bash
cd ~
git clone https://github.com/tech4humans-brasil/t4h-desafios.git
mkdir meu-desafio-performance
cp -R "t4h-desafios/Vaga - Estágio Pesquisa e Inovação 2026/." meu-desafio-performance/
cd meu-desafio-performance

git init -b main
git add .
git commit -m "chore: estado original do desafio"
ls        # deve mostrar AGENTS.md, CLAUDE.md, README.md, api, banco, carga, contrato, docker-compose.yml, resultados, scripts
```

A partir daqui, todos os comandos rodam dentro de `meu-desafio-performance` (o nome é livre). A pasta `t4h-desafios` pode ser apagada.

Para publicar no GitHub, crie um repositório público vazio (sem README) e siga [Adicionar código local ao GitHub](https://docs.github.com/pt/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github). Os comandos são estes, trocando `SEU-USUARIO` e `SEU-REPO`:

```bash
git remote add origin https://github.com/SEU-USUARIO/SEU-REPO.git
git push -u origin main
```

O GitHub não aceita a senha da conta no `git push`. Use o [GitHub CLI](https://cli.github.com/) (`gh auth login`) ou um [token de acesso pessoal](https://docs.github.com/pt/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) no lugar da senha.

Para editar o código, qualquer editor serve. Se for usar o VS Code no Windows, abra a pasta pelo Ubuntu com `code .` e veja [VS Code com WSL](https://code.visualstudio.com/docs/remote/wsl).

### 5. Subir a aplicação

Dentro da sua cópia:

```bash
docker compose up -d --build
```

O que esse comando faz:

- `up` cria e liga os containers descritos no `docker-compose.yml`: `banco` (PostgreSQL) e `api` (Node.js).
- `-d` roda em segundo plano e devolve o terminal para você.
- `--build` monta a imagem da API a partir do `api/Dockerfile`. Use sempre que mudar o código.

Na primeira vez, o Docker baixa as imagens (algumas centenas de MB, conforme a sua internet) e o banco gera os dados, o que leva de alguns segundos a 3 minutos, conforme a máquina. O comando só termina quando o banco está pronto. Para acompanhar a geração dos dados, em outro terminal: `docker compose logs -f banco` (Ctrl+C para sair). Você vai ver linhas como `Gerando 500.000 pedidos...`.

Confira se os dois containers estão de pé:

```bash
docker compose ps
```

```
NAME                          IMAGE                     ...   SERVICE   STATUS                    PORTS
desafio-performance-api-1     desafio-performance-api   ...   api       Up 3 seconds              127.0.0.1:3000->3000/tcp
desafio-performance-banco-1   postgres:16.4             ...   banco     Up 24 seconds (healthy)   127.0.0.1:5432->5432/tcp
```

O banco precisa aparecer como `(healthy)`. Referência dos comandos: [docker compose](https://docs.docker.com/reference/cli/docker/compose/) (em inglês).

### 6. Fazer as primeiras chamadas

A API responde em `http://127.0.0.1:3000`. O `curl` faz uma requisição HTTP pelo terminal e mostra a resposta:

```bash
curl http://127.0.0.1:3000/saude
# {"status":"ok"}

curl http://127.0.0.1:3000/clientes/1
# {"id":1,"nome":"Bruno Almeida","email":"cliente1@exemplo.com","cidade":"Fortaleza","criado_em":"2022-01-01T02:11:59.000Z"}

curl "http://127.0.0.1:3000/produtos/busca?q=mesa"
# [{"id":10061,"nome":"Mesa Basica Modelo 10061","categoria":"Moveis","preco_centavos":481580}, ...]

curl http://127.0.0.1:3000/clientes/abc
# {"erro":"id invalido"}
```

Quando a URL tiver `?` ou `&`, coloque entre aspas, como no terceiro exemplo. Também dá para abrir essas URLs no navegador. As outras rotas estão na tabela [Rotas](#rotas). Algumas, como os relatórios, demoram vários segundos: é essa lentidão que você vai investigar.

Para conhecer o `curl`, veja o [tutorial oficial](https://curl.se/docs/tutorial.html) (em inglês).

### 7. Gravar o contrato e medir a linha de base

Com a aplicação original no ar e antes de mudar qualquer coisa:

```bash
scripts/verificar-contrato.sh gravar
git add contrato/base.json
git commit -m "chore: grava contrato da aplicação original"

scripts/medir.sh 00-linha-de-base
```

O primeiro comando salva as respostas da aplicação original para comparar depois. O segundo mede o desempenho dela e termina em cerca de 1 min 30 s, mostrando onde salvou o resultado. Leia o `resumo.txt` dessa pasta com `cat resultados/<pasta>/resumo.txt`. O que cada arquivo significa e como seguir a partir daí está em [Como medir](#como-medir).

### 8. Parar e voltar depois

```bash
docker compose stop     # desliga os containers e mantém os dados
docker compose start    # liga de novo, sem gerar os dados outra vez
docker compose down     # remove os containers e mantém os dados
docker compose down -v  # remove containers e banco; a próxima subida gera os dados do zero
```

Se reiniciar o computador, abra o Docker Desktop e rode `docker compose up -d` dentro da sua cópia.

## Conceitos em um minuto

| Termo | O que é | Para ler mais |
| --- | --- | --- |
| Container e imagem | A imagem é o pacote com o programa e tudo de que ele precisa; o container é essa imagem rodando | [Docker overview](https://docs.docker.com/get-started/docker-overview/) |
| Docker Compose | Sobe vários containers juntos a partir do `docker-compose.yml` | [Docker Compose](https://docs.docker.com/compose/) |
| API e rota | Programa que responde a requisições HTTP; cada rota é um endereço, como `/clientes/1` | [Express](https://expressjs.com/) |
| Node.js e `pg` | Node.js roda JavaScript fora do navegador; `pg` é a biblioteca que a API usa para falar com o banco | [Introdução ao Node.js](https://nodejs.org/pt/learn/getting-started/introduction-to-nodejs), [node-postgres](https://node-postgres.com/) |
| PostgreSQL e `psql` | O banco de dados relacional da aplicação e o cliente de linha de comando dele | [Tutorial do PostgreSQL](https://www.postgresql.org/docs/16/tutorial.html), [psql](https://www.postgresql.org/docs/16/app-psql.html) |
| Teste de carga e k6 | Simula muitos usuários usando a API ao mesmo tempo; k6 é a ferramenta que faz isso aqui | [k6](https://grafana.com/docs/k6/latest/) |
| Mediana, p95 e p99 | Metade das requisições foi mais rápida que a mediana; 95% foram mais rápidas que o p95 e 99% que o p99 | [Métricas do k6](https://grafana.com/docs/k6/latest/using-k6/metrics/) |
| Commit | Um ponto salvo no histórico do Git, com as mudanças e uma mensagem | [Pro Git](https://git-scm.com/book/pt-br/v2) |

## Subir a aplicação

Resumo do [passo 5](#5-subir-a-aplicação), para quem já tem tudo instalado. Rode dentro desta pasta:

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

1. Copie só esta pasta para a raiz de um repositório público seu, como no [passo 4](#4-criar-a-sua-cópia-do-desafio). O resto do t4h-desafios é de outros processos seletivos e não faz parte do teste.
2. Faça commit das suas mudanças, do `contrato/base.json` e das pastas de `resultados/`, sem editar os arquivos gerados. Faça um commit por mudança, seguido do commit com os resultados dela.
3. Acrescente a este README uma seção com o problema e o resumo dos seus resultados. Mantenha as instruções de subir e medir, para que outra pessoa consiga repetir.
4. Coloque o link do repositório no artigo.

## Usar um agente de IA

O [AGENTS.md](AGENTS.md) resume, para agentes como Claude Code, Codex ou Cursor, como rodar e medir a aplicação e o que não pode ser mudado. Ele não traz o enunciado: passe o enunciado para o agente junto com o seu pedido.

Abra o agente dentro da sua cópia desta pasta. Na raiz do t4h-desafios, o `CLAUDE.md` e a pasta `.claude/` são de quem mantém o repositório e não valem para o desafio.

## Problemas comuns

- **`docker: command not found` ou `Cannot connect to the Docker daemon`:** no macOS e no Windows, abra o Docker Desktop e espere o ícone da baleia parar de animar. No Windows, confira também a integração com o WSL ([passo 3](#3-instalar-o-docker)). No Linux, ligue o serviço com `sudo systemctl start docker`.
- **`permission denied` ao rodar `docker` no Linux:** seu usuário ainda não está no grupo `docker`. Siga os [passos pós-instalação](https://docs.docker.com/engine/install/linux-postinstall/) e abra um terminal novo.
- **`unknown command: docker compose` ou `docker: 'compose' is not a docker command`:** o Docker está desatualizado. Instale a versão atual pelo [passo 3](#3-instalar-o-docker). O comando antigo `docker-compose`, com hífen, não serve.
- **`No such file or directory` ao entrar na pasta:** o nome tem espaços ou acentos e precisa de aspas, por exemplo `cd "Vaga - Estágio Pesquisa e Inovação 2026"`. Use `ls` para ver o nome exato.
- **`permission denied: scripts/medir.sh`:** os scripts perderam a permissão de execução, o que acontece quando a pasta é baixada como ZIP em vez de clonada. Rode `chmod +x scripts/*.sh`.
- **Porta 5432 ou 3000 em uso:** pare o outro serviço ou troque o lado esquerdo do mapeamento em `ports:` no `docker-compose.yml`. Se trocar a porta da API, rode as medições com a nova porta, por exemplo `PORTA_API=3001 scripts/medir.sh 00-linha-de-base`.
- **`medir.sh` diz que a API não respondeu:** veja se o banco já terminou de gerar os dados (`docker compose logs banco`).
- **Erro `bash\r` ou `$'\r': command not found` no Windows:** o Git converteu as quebras de linha. Isso acontece quando o repositório é clonado pelo Git do Windows em vez do Git do Ubuntu. Rode `git config --global core.autocrlf false` e clone de novo, de preferência dentro do Ubuntu, como no [passo 4](#4-criar-a-sua-cópia-do-desafio).

## Observações Importantes

- Leia o enunciado inteiro antes de começar
- Mantenha-se dentro do prazo
- Em caso de dúvidas, use o canal combinado na largada

Boa sorte no seu desafio!
