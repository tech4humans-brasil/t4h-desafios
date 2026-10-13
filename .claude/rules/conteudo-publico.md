# Conteúdo público

Este repositório é **público** no GitHub. Qualquer arquivo commitado fica visível para qualquer pessoa e continua no histórico do Git mesmo depois de apagado. Antes de adicionar um arquivo, confira os itens abaixo. Se algum falhar, **pare e avise a pessoa**, sem commitar.

## Proibido

- **Gabarito, solução de referência ou critérios internos de correção e pontuação.** Esses materiais ficam fora do repositório.
- **Dados pessoais reais**, como nome com CPF, e-mail, telefone ou salário de pessoas reais. Planilhas e datasets usam dados fictícios. CPF, quando aparecer, vem mascarado (ex.: `398.122.745-XX`), como nas planilhas de `Techlab - CEU 2025/Agent (DevOps)/Planilhas/`.
- **Dados ou nomes de clientes** da Tech for Humans e documentos internos, como processos, arquitetura, prints de sistemas internos e links para o Operoz, o Streamline ou o Knowledge.
- **Segredos**: tokens, senhas, chaves de API, connection strings e arquivos `.env`.
- **Contato pessoal** de colaboradores, como e-mail ou telefone individual. Para dúvidas, use um canal genérico (e-mail de grupo ou formulário).

## Como verificar

- **Planilhas (`.xlsx`)**: leia as strings com `unzip -p "<arquivo>.xlsx" xl/sharedStrings.xml` e procure CPF sem máscara (`\d{3}\.\d{3}\.\d{3}-\d{2}`), e-mails e telefones.
- **PDFs**: pergunte à pessoa se o arquivo é o enunciado entregue ao candidato e se não tem anexo de solução. Se `pdftotext` estiver disponível, procure "gabarito", "solução" e "resposta".
- **Texto e código de apoio**: procure padrões de segredo (`token`, `password`, `secret`, `api_key`, `BEGIN PRIVATE KEY`).

## Tamanho

- O GitHub avisa em arquivos acima de 50 MB e recusa acima de 100 MB. Arquivo acima de 50 MB não entra: peça uma versão comprimida ou um link externo público.
- Prefira PDF a `.pptx` e `.docx` para enunciados e apresentações.
