CREATE TABLE clientes (
    id        integer PRIMARY KEY,
    nome      text      NOT NULL,
    email     text      NOT NULL,
    cidade    text      NOT NULL,
    criado_em timestamp NOT NULL
);

CREATE TABLE produtos (
    id             integer PRIMARY KEY,
    nome           text    NOT NULL,
    categoria      text    NOT NULL,
    preco_centavos integer NOT NULL
);

CREATE TABLE pedidos (
    id          integer   PRIMARY KEY,
    cliente_id  integer   NOT NULL REFERENCES clientes (id),
    status      text      NOT NULL,
    criado_em   timestamp NOT NULL,
    observacoes text      NOT NULL
);

CREATE TABLE itens_pedido (
    id                      integer PRIMARY KEY,
    pedido_id               integer NOT NULL REFERENCES pedidos (id),
    produto_id              integer NOT NULL REFERENCES produtos (id),
    quantidade              integer NOT NULL,
    preco_unitario_centavos integer NOT NULL
);
