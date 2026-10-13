---
name: novo-projeto-desafio
description: Cadastra um novo projeto de desafios técnicos no repositório t4h-desafios, ou seja, um processo seletivo ou uma vaga da Tech for Humans com seus enunciados e materiais de apoio. Use quando a pessoa disser "cadastrar desafio para a vaga X", "novo processo seletivo", "nova edição do TechLab", "subir os desafios da vaga", "criar projeto de desafio" ou trouxer PDFs e planilhas de um desafio novo. Conduz a entrevista, valida o conteúdo contra as regras de repositório público, cria pastas e README, atualiza o índice e abre o PR. Para incluir uma área em um projeto existente, use adicionar-desafio.
---

# Novo projeto de desafios

Cadastra um projeto (processo seletivo ou vaga) seguindo as rules em `.claude/rules/`. Leia as três rules antes de começar. O repositório é **público**, então nada é commitado sem passar pelo checklist de [conteudo-publico.md](../../rules/conteudo-publico.md) e sem confirmação da pessoa.

## 1. Preparar

1. Confirme que está na raiz do repositório e que o working tree está limpo (`git status --short`). Se houver mudanças pendentes, pergunte o que fazer com elas antes de continuar.
2. Atualize a `main` (`git switch main && git pull --ff-only`).
3. Liste os projetos existentes (pastas na raiz) para evitar nomes duplicados.

## 2. Entrevistar

Pergunte só o que ainda não foi informado. Se puder, agrupe as perguntas em uma só mensagem.

| Dado | Uso |
| --- | --- |
| Vaga ou programa, contexto e ano/edição | Nome da pasta e título |
| Descrição curta do processo (1 ou 2 frases, para candidatos) | Intro do README e coluna "Descrição" do índice |
| Áreas ou desafios: nome, trilha/tecnologia e caminho dos arquivos (enunciado e materiais de apoio) | Subpastas e seções de área |
| Materiais gerais (workshop, apresentação, edital) | Arquivos na raiz do projeto |
| Prazo de entrega | Seção "Prazo e entrega" |
| Forma de entrega (repositório próprio, formulário, e-mail de grupo) | Seção "Prazo e entrega" |
| Canal de dúvidas, que deve ser genérico e não um contato pessoal | Seção "Prazo e entrega" |

Se a pessoa não souber prazo, forma de entrega ou canal, escreva `A definir` e avise que o README vai ao ar assim.

## 3. Propor nomes e estrutura

1. Monte o nome do projeto no padrão `<Programa ou Vaga> - <Contexto> <Ano>` e os nomes das áreas no padrão `<Área> (<Trilha>)`, conforme [estrutura-e-nomes.md](../../rules/estrutura-e-nomes.md).
2. Renomeie os enunciados para `Desafio <Nome>.pdf` quando não estiverem nesse padrão.
3. Mostre a árvore final e peça confirmação antes de criar qualquer arquivo.

## 4. Validar o conteúdo

Para cada arquivo de origem:

1. Confirme que o arquivo existe e meça o tamanho (`du -h`). Se passar de 50 MB, pare e peça uma versão menor.
2. Aplique as verificações de [conteudo-publico.md](../../rules/conteudo-publico.md): dados pessoais reais em planilhas, segredos em texto e gabarito ou solução em PDFs.
3. Pergunte explicitamente: "Algum desses arquivos tem gabarito, solução de referência ou critério interno de correção?"

Se algo falhar, mostre o achado (arquivo e trecho) e não continue até a pessoa resolver.

## 5. Criar

1. Crie a branch `desafios/<slug-do-projeto>`, com o slug em minúsculas, sem acento e com hífens.
2. Crie as pastas e **copie** os arquivos de origem (`cp`, nunca `mv`), já com os nomes finais.
3. Gere `<Projeto>/README.md` a partir de [template-readme-projeto.md](template-readme-projeto.md): preencha todos os `{{...}}`, monte a árvore com os arquivos reais e remova o bloco de comentário do final. Não deixe nenhum placeholder.
4. Adicione a linha do projeto **no topo** da tabela "Projetos" do `README.md` da raiz.
5. Confira se os links novos apontam para caminhos que existem: decodifique cada link e teste com `test -e`.

## 6. Publicar

1. Mostre o `git status` e um resumo: projeto, áreas, arquivos e linha do índice.
2. Com a confirmação da pessoa, faça o commit (`feat: add <Projeto> challenges`), o push da branch e abra o PR com `gh pr create`. A descrição do PR lista projeto, áreas e arquivos e confirma o checklist de conteúdo público.
3. Devolva o link do PR. Não faça merge.
