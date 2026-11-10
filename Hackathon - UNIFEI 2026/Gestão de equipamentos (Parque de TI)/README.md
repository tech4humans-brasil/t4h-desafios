# Tema 3 — Gestão de equipamentos

Um time de agentes cuida do parque de equipamentos: atende pedidos, mantém o inventário certo, prepara o kit de quem entra e cobra a devolução de quem sai.

As regras gerais, a entrega e a avaliação estão no [README do hackathon](../README.md).

## A história

A T4H tem centenas de equipamentos espalhados: notebooks, monitores, headsets, kits de teclado e mouse. O controle existe, mas tem número de série repetido, item baixado marcado como novo e cadastro incompleto. Gente nova pode começar sem notebook, quem saiu pode continuar com equipamento em casa, e nem sempre se sabe quantos monitores sobraram. A T4H quer um time de colaboradores digitais que cuide disso todo dia.

## O que tem no mundo deste tema

| O que existe | O que é |
| --- | --- |
| Inventário | ~150 itens fictícios, com erros plantados |
| Colaboradores | ~40 pessoas, com área, data de entrada e data de saída |
| Caixa de entrada | ~50 pedidos ao longo de 22 dias de expediente: kit de quem entra, saídas, trocas por defeito, empréstimos, devoluções e perguntas |
| Catálogo de compra | Preço e prazo de entrega de cada item |
| Regras | As da tabela abaixo |

Os agentes consultam e agem pelas ferramentas do [servidor MCP](../Servidor%20MCP%20%28Compartilhado%29/), que aparecem na lista ao conectar. Para subir este tema: `python mundo.py --tema equipamentos`. O mundo reage: as compras chegam no prazo do fornecedor, quem é cobrado devolve (ou não), e no primeiro dia de cada pessoa o mundo confere se o kit dela está pronto. O cenário da banca usa outro inventário e pedidos inéditos, no mesmo formato.

## O inventário

| Campo | O que é | Valores |
| --- | --- | --- |
| `patrimonio` | Identificador do item | `EQ-0001` em diante |
| `tipo` | O que é | notebook, monitor, headset, kit teclado e mouse, carregador |
| `marca`, `modelo`, `numero_serie` | Identificação do fabricante | Texto livre |
| `status` | Onde o item está no ciclo | disponível, reservado, alocado, uso interno, baixado |
| `situacao` | Estado físico | novo, usado, quebrado, danificado, perdido |
| `com_quem`, `desde` | Pessoa e data da alocação | Vazio quando não está alocado |

Os erros plantados são dos tipos que acontecem na vida real: dois itens com o mesmo número de série, item baixado com situação "novo", item alocado para quem já saiu, item sem número de série e a mesma marca escrita de jeitos diferentes.

## As regras

Todas fictícias, criadas para o desafio.

| Regra | Como funciona |
| --- | --- |
| Kit de entrada | Notebook, headset e kit teclado e mouse para todo mundo; desenvolvimento e design ganham também um monitor |
| Prazo do kit | Tudo reservado até 2 dias úteis antes do primeiro dia |
| Troca por defeito | Item quebrado ou danificado é trocado assim que houver estoque |
| Devolução | Até 5 dias úteis depois da saída; passou disso, cobrar; passou de 10, escalar |
| Empréstimo | Até 30 dias, com a data de devolução registrada |
| Compra | Até R$ 500 por pedido o agente compra sozinho; acima disso, propõe |
| Estoque mínimo | Avisar quando restarem menos de 3 itens disponíveis de um tipo |

Pedido fora das regras, como um segundo notebook ou um item que o cargo não tem, nunca é atendido direto: vira uma proposta ou vai para uma pessoa.

## Um exemplo

Chega este pedido no dia 3 do cenário:

```text
De: carla@t4h.exemplo
Assunto: Kit do Pedro
O Pedro Lima começa no dia 15 como desenvolvedor. Consegue o kit dele?
```

O notebook tem estoque, o monitor não. Um agente reserva o que tem e pede a outro que cuide da compra:

```json
[
  {
    "ferramenta": "registrar_conversa",
    "agente": "atendente",
    "de": "atendente",
    "para": "almoxarife",
    "mensagem": "Entrada de desenvolvedor no dia 15: kit padrão mais monitor."
  },
  {
    "ferramenta": "reservar",
    "agente": "almoxarife",
    "motivo": "Notebook disponível, situação novo.",
    "patrimonio": "EQ-0142",
    "para": "Pedro Lima"
  },
  {
    "ferramenta": "registrar_conversa",
    "agente": "almoxarife",
    "de": "almoxarife",
    "para": "comprador",
    "mensagem": "Sem monitor disponível. Precisa chegar até o dia 13."
  },
  {
    "ferramenta": "propor",
    "agente": "comprador",
    "motivo": "R$ 890 passa do limite de R$ 500.",
    "acao": "abrir_compra",
    "alvo": "monitor",
    "detalhes": "Entrega em 7 dias úteis: aprovado até o dia 4, chega antes do dia 13."
  }
]
```

## Níveis de entrega

- **Mínimo:** pelo menos dois agentes com papéis diferentes atendem os pedidos que têm estoque e mantêm o inventário atualizado.
- **Bom:** compra quando falta, propõe acima do limite, prepara o kit de quem entra no prazo e cobra a devolução de quem sai, com os agentes se avisando antes que o problema apareça.
- **Excelente:** encontra as inconsistências da planilha e propõe a correção de cada uma; avisa antes que o estoque de algum item acabe.

## Erros graves

- Uma pessoa começar sem notebook quando dava para evitar.
- Comprar acima do limite sem proposta.
- Entregar um item que já está com outra pessoa.
- Terminar com item no inventário sem registro de onde está.
