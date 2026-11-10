# Tema 3 — Gestão de equipamentos

Um time de agentes cuida do parque de equipamentos: atende pedidos, mantém o inventário certo, prepara o kit de quem entra e cobra a devolução de quem sai. Para subir o mundo deste tema, na pasta do [servidor MCP](../Servidor%20MCP%20%28Compartilhado%29/): `TEMA=equipamentos docker compose up mundo`.

As regras gerais e a entrega estão no [README do hackathon](../README.md).

## A história

A T4H tem centenas de equipamentos espalhados: notebooks, monitores, headsets, kits de teclado e mouse. O controle existe, mas tem número de série repetido, item baixado marcado como novo e cadastro incompleto. Gente nova pode começar sem notebook, e quem saiu pode continuar com equipamento em casa.

## O que tem no mundo

| O que existe | O que é |
| --- | --- |
| Inventário | ~150 itens, com erros plantados do tipo que acontece na vida real |
| Colaboradores | ~40 pessoas, com área, data de entrada e data de saída |
| Caixa de entrada | ~50 pedidos ao longo de 22 dias: kit de quem entra, saídas, trocas por defeito, empréstimos, devoluções e perguntas |
| Catálogo de compra | Preço e prazo de entrega de cada item |

O mundo reage: as compras chegam no prazo do fornecedor, quem é cobrado devolve (ou não), e no primeiro dia de cada pessoa o mundo confere se o kit dela está pronto.

## As regras

| Regra | Como funciona |
| --- | --- |
| Kit de entrada | Notebook, headset e kit teclado e mouse para todo mundo; desenvolvimento e design ganham também um monitor |
| Prazo do kit | Tudo reservado até 2 dias úteis antes do primeiro dia |
| Devolução | Até 5 dias úteis depois da saída; passou disso, cobrar; passou de 10, escalar |
| Empréstimo | Até 30 dias, com a data de devolução registrada |
| Compra | Até R$ 500 por pedido o agente compra sozinho; acima disso, propõe |
| Estoque mínimo | Avisar quando restarem menos de 3 itens livres de um tipo |

Pedido fora das regras, como um segundo notebook ou um item que o cargo não tem, vira uma proposta ou vai para uma pessoa.

## Níveis de entrega

- **Mínimo:** pelo menos dois agentes com papéis diferentes atendem os pedidos que têm estoque e mantêm o inventário atualizado.
- **Bom:** compram quando falta, propõem acima do limite, deixam o kit de quem entra pronto no prazo e cobram a devolução de quem sai.
- **Excelente:** encontram as inconsistências do inventário e propõem a correção de cada uma; avisam antes que o estoque de algum item acabe.

## Erros graves

- Uma pessoa começar sem notebook quando dava para evitar.
- Entregar um item que já está com outra pessoa.
- Terminar com item no inventário sem registro de onde está.
