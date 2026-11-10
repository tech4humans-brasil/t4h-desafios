# Tema 3 — Gestão de equipamentos (ficha técnica)

Como o servidor se comporta neste tema. O enunciado do desafio está no documento oficial do evento.

## Como subir

Na pasta do [servidor MCP](../Servidor%20MCP%20%28Compartilhado%29/):

```bash
TEMA=equipamentos docker compose up mundo
```

Ou, sem Docker: `python mundo.py --tema equipamentos`. O cenário de treino tem ~50 eventos ao longo de 22 dias de expediente, a partir de 01/12/2026.

## As bases

| Base | Chave | O que tem | Registrar | Atualizar |
| --- | --- | --- | --- | --- |
| `eventos` | `id` | Tudo o que chegou para o time | Não | `status`, `observacao` |
| `inventario` | `patrimonio` | ~150 itens: tipo, marca, modelo, série, status, situação e com quem está | Não | `status`, `situacao`, `com_quem`, `desde`, `numero_serie`, `marca`, `modelo`, `observacao` |
| `colaboradores` | `id` | ~40 pessoas, com área, cargo, e-mail, entrada e saída | Não | Não |
| `catalogo_compra` | `tipo` | Preço e prazo de entrega de cada tipo de item | Não | Não |
| `regras` | `regra` | Kit por área, prazos, devolução, empréstimo, limite de compra e estoque mínimo | Não | Não |
| `compras` | `id` | Pedidos feitos no portal do fornecedor | Não | Não |

Validações em `atualizar` no `inventario`:

- `status`: `disponível`, `reservado`, `alocado`, `uso interno` ou `baixado`. `situacao`: `novo`, `usado`, `quebrado`, `danificado` ou `perdido`.
- `reservado` ou `alocado` exige `com_quem` (id, nome ou e-mail do colaborador) e um item `disponível`, ou já reservado para a mesma pessoa, em situação `novo` ou `usado`. Senão, 409 ou 422.
- Um item `alocado` só volta para `disponível` ou `uso interno` depois que voltou de fato: a pessoa avisou que devolveu.
- Passar um item para outra pessoa sem registrar a devolução antes dá 409.

## Portal do fornecedor (só tela)

`http://localhost:8765/legado/fornecedor`: o catálogo com preços, um formulário (quem está comprando, item, quantidade de 1 a 10, evento relacionado) e uma página de revisão onde o pedido é confirmado. Cada compra gera um pedido `FORN-...`, entra na base `compras` e chega no prazo do fornecedor. Não existe API para comprar.

## O que o mundo faz sozinho

- **Entregas:** a compra chega na data prevista; os itens novos entram no inventário como `disponível` e um evento avisa os patrimônios.
- **Primeiro dia:** no dia de entrada de cada pessoa, o mundo confere se o kit dela está reservado ou alocado. Os reservados passam a alocados, e o que faltar vira alerta (grave se faltar notebook).
- **Devoluções:** uma mensagem para um colaborador falando de devolução ou equipamento gera resposta. Quem já saiu devolve (ou não); quem ainda trabalha estranha a cobrança.
- **Saídas:** quem saiu durante o cenário e continua com itens gera alerta depois de 5 e de 10 dias úteis.
- **Limite de compra:** compra acima do limite gera um alerta informativo no painel.
- **Mensagens para fora:** qualquer mensagem para um endereço fora de `@t4h.exemplo` gera um alerta grave.
