# Estrutura e nomes

## Layout

```
.
├── README.md                      # índice: uma linha por projeto na tabela "Projetos"
└── <Projeto>/
    ├── README.md                  # obrigatório, gerado a partir do template da skill
    ├── <material geral>.pdf       # opcional: workshop, apresentação, edital
    └── <Área> (<Trilha>)/
        ├── Desafio <Nome>.pdf     # enunciado, obrigatório
        └── <materiais de apoio>   # planilhas, tutoriais, datasets
```

- Todo projeto fica em uma pasta na raiz. Não crie projetos aninhados.
- Todo projeto tem um `README.md` próprio. O `README.md` da raiz não descreve desafios, só aponta para os projetos.
- Toda área tem pelo menos um arquivo de enunciado.

## Nomes

- **Projeto**: `<Programa ou Vaga> - <Contexto> <Ano>`. Exemplos: `Techlab - CEU 2025` e `Vaga - Dev Backend Pleno 2026`. Se houver mais de uma edição no mesmo ano, use `2026.1` e `2026.2`.
- **Área**: `<Área> (<Trilha ou tecnologia>)`. Exemplos: `Agent (DevOps)` e `Low Code (Process Automation)`.
- **Enunciado**: `Desafio <Nome>.pdf`.
- Nomes em português, com acentuação normal e espaços, seguindo o padrão das pastas existentes. Não use `/`, `:` nem `#` em nomes de arquivo.
- Se o nome escolhido já existir na raiz, peça outro. Não sobrescreva projetos.

## Índice da raiz

- A tabela **Projetos** do `README.md` da raiz tem as colunas `Projeto | Descrição | Áreas`.
- O link do projeto usa o caminho com espaços codificados (`%20`), por exemplo `[TechLab CEU 2025](Techlab%20-%20CEU%202025/)`.
- O projeto mais recente fica na primeira linha.
- Se você criar, renomear ou remover um projeto, ou mudar as áreas dele, atualize a tabela no mesmo commit.

## README do projeto

O README do projeto segue o template [template-readme-projeto.md](../skills/novo-projeto-desafio/template-readme-projeto.md) e tem sempre estas seções:

- descrição da vaga ou do processo
- prazo e forma de entrega
- estrutura de pastas
- uma seção por área, com a lista de arquivos e o que cada um contém
- como utilizar e observações
