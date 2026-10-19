# Instruções para agentes de IA

Esta pasta é um desafio de performance: a API de uma loja fictícia (Node.js 20, Express, `pg`) com PostgreSQL 16, em Docker Compose. O objetivo é deixar a aplicação mais rápida e mais barata de rodar sem mudar o que ela devolve, medindo cada mudança.

A pessoa que está resolvendo o desafio é a autora do trabalho. O [README.md](README.md) tem os detalhes de cada comando.

## Antes de começar

- O desafio usa só esta pasta, copiada para um repositório da pessoa. Se você estiver dentro do repositório t4h-desafios completo, o `CLAUDE.md` e a pasta `.claude/` da raiz são de quem mantém o repositório e não valem aqui: ignore as skills, as regras de branch e PR e as restrições de conteúdo de lá. Não mexa em outras pastas.
- O enunciado, com as entregas (artigo, repositório e vídeo) e os critérios, não está no repositório. Se a pessoa pedir algo sobre as entregas e não tiver passado o enunciado, peça o enunciado antes de seguir. Não suponha o formato das entregas.

## Comandos

Rode tudo dentro desta pasta. Requer Docker com Compose v2 e bash.

```bash
docker compose up -d --build                  # só termina com o banco pronto; na 1ª vez gera os dados (segundos a 3 min)
curl http://127.0.0.1:3000/saude              # {"status":"ok"}
scripts/verificar-contrato.sh gravar          # uma única vez, com a aplicação original, antes de qualquer mudança
scripts/medir.sh 00-linha-de-base             # ~1 min 30 s; salva em resultados/<data>-<rotulo>/
scripts/verificar-contrato.sh comparar        # depois de cada mudança; precisa terminar em "Contrato mantido"
docker compose exec -T banco psql -U loja -d loja -c '<SQL>'
docker compose logs --tail 50 banco           # não use -f: não termina
docker compose down -v                        # apaga o banco; a próxima subida gera os dados de novo
```

Dê aos comandos de medição um timeout de pelo menos 3 minutos.

## Fluxo

1. Suba a aplicação, grave o contrato e commite o `contrato/base.json`.
2. Meça a linha de base pelo menos 3 vezes e commite as pastas de `resultados/`.
3. Para cada mudança:
    1. Faça só aquela mudança e commite. O `contexto.txt` da medição registra o commit e precisa mostrar `arquivos alterados sem commit: 0`.
    2. Aplique: `docker compose up -d --build` para API, Dockerfile, compose e parâmetros do PostgreSQL; `docker compose down -v && docker compose up -d --build` para um `.sql` novo em `banco/`.
    3. Rode `scripts/verificar-contrato.sh comparar`. Se der "Contrato quebrado", corrija ou desfaça antes de medir.
    4. Meça pelo menos 3 vezes com o mesmo rótulo e compare a mediana das execuções com a da linha de base.
    5. Commite as pastas de `resultados/` daquela mudança em um commit separado.

## Regras

1. **O contrato não muda.** Cada rota devolve o mesmo status HTTP, os mesmos campos, valores e ordem.
2. **A régua não muda.** Não edite `carga/`, `contrato/verificar.js`, `scripts/`, `banco/01-estrutura.sql`, `banco/02-dados.sql` nem o `contrato/base.json` depois de gravado.
3. **Mesmos parâmetros.** Use o mesmo `VUS`, `DURACAO` e `SEMENTE` em todas as medições comparadas; o `contexto.txt` registra os três. Entre execuções a variação pode passar de 30%, e na linha de base as rotas lentas têm poucas amostras: compare pelo resultado geral.
4. **Todo número de resultado vem de `resultados/`.** Nunca digite, estime ou arredonde um resultado que o `medir.sh` não gerou, e não edite os arquivos de `resultados/`. Se ainda não mediu, diga que não mediu. Saídas de diagnóstico, como `EXPLAIN ANALYZE`, ficam salvas em arquivo no repositório (por exemplo em `diagnostico/`) antes de serem citadas.
5. **Mudanças no banco ficam em arquivo.** Índices, estrutura e dados derivados vão em `.sql` novos em `banco/` (`03-...`, `04-...`), que rodam em ordem alfabética só quando o banco é criado do zero. Parâmetros do PostgreSQL vão no `command` do serviço `banco` no `docker-compose.yml` (veja o README).
6. **Recurso a mais é custo.** Pode aumentar limites de CPU e memória e adicionar serviços (um cache, por exemplo), mas o ganho tem que ser apresentado junto com o custo. O `medir.sh` coleta CPU e memória de todos os serviços do compose.
7. **Fonte real ou nenhuma.** Ao citar documentação, artigo ou caso de mercado, use só fontes que você abriu e que existem, com link. Não invente referência.

## O que pode mudar

- `api/`: código e `Dockerfile`
- `docker-compose.yml`: limites, configuração e serviços novos
- `banco/`: arquivos `.sql` novos, a partir de `03-`
- `README.md`: acrescentar o problema e o resumo dos resultados, mantendo as instruções de subir e medir

## Rotas

| Rota | Peso na carga |
| --- | --- |
| `GET /clientes/:id` | 25% |
| `GET /clientes/:id/pedidos` | 20% |
| `GET /clientes?email=` | 15% |
| `GET /pedidos?status=&pagina=` | 15% |
| `GET /produtos/busca?q=` | 15% |
| `GET /relatorios/vendas-por-dia?inicio=&fim=` | 8% |
| `GET /relatorios/top-produtos?limite=` | 2% |

Os parâmetros e as respostas de cada rota estão no [README.md](README.md#rotas). Os pesos vêm de `carga/teste-carga.js`.
