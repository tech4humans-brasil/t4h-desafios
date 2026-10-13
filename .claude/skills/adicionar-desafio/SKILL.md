---
name: adicionar-desafio
description: Inclui uma nova área ou um novo desafio, ou troca materiais, em um projeto que já existe no repositório t4h-desafios. Use quando a pessoa disser "adicionar uma área no TechLab 2025", "incluir desafio de dados na vaga X", "atualizar o enunciado do desafio Y", "subir mais uma planilha de apoio". Valida o conteúdo contra as regras de repositório público, atualiza o README do projeto e o índice e abre o PR. Para um processo seletivo ou vaga nova, use novo-projeto-desafio.
---

# Adicionar desafio a um projeto existente

Segue as rules em `.claude/rules/` e reaproveita o fluxo de [novo-projeto-desafio](../novo-projeto-desafio/SKILL.md). Aqui só ficam as diferenças.

## 1. Preparar

1. Working tree limpo e `main` atualizada, como na skill de novo projeto.
2. Liste os projetos na raiz e confirme com a pessoa qual será alterado. Leia o `README.md` desse projeto.

## 2. Entender a mudança

Pergunte qual destes casos se aplica:

- **Nova área**: nome, trilha/tecnologia e caminho dos arquivos (enunciado e materiais de apoio).
- **Novo material em área existente**: área de destino, arquivos e o que cada um contém.
- **Substituição de arquivo** (ex.: nova versão do enunciado): qual arquivo sai e qual entra. Se o processo seletivo já estiver em andamento, avise que candidatos podem estar com a versão anterior e confirme antes de substituir.

## 3. Validar e criar

1. Proponha os nomes conforme [estrutura-e-nomes.md](../../rules/estrutura-e-nomes.md) e mostre a árvore final do projeto para confirmação.
2. Aplique o checklist de [conteudo-publico.md](../../rules/conteudo-publico.md) aos arquivos **novos**, incluindo a pergunta sobre gabarito.
3. Crie a branch `desafios/<slug-do-projeto>-<assunto>` e copie os arquivos (`cp`).
4. Atualize o `README.md` do projeto: árvore de estrutura, nova seção de área (numerada em sequência) ou lista de arquivos da área.
5. Se a lista de áreas mudou, atualize a coluna "Áreas" da linha do projeto no `README.md` da raiz.
6. Verifique os links novos com `test -e`.

## 4. Publicar

Com a confirmação da pessoa: commit (`feat: add <Área> to <Projeto>`, ou `docs:` quando mudar só texto), push da branch e PR com `gh pr create`. Devolva o link do PR. Não faça merge.
