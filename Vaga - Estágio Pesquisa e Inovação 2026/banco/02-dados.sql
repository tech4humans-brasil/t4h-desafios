-- Dados sintéticos e determinísticos: toda instalação gera exatamente as mesmas linhas.
-- Nenhum nome, e-mail ou cidade se refere a uma pessoa real.

\echo 'Gerando 100.000 clientes...'
INSERT INTO clientes (id, nome, email, cidade, criado_em)
SELECT
    i,
    (ARRAY['Ana','Bruno','Carla','Diego','Elisa','Fabio','Gabriela','Heitor','Isabela','Joao','Karina','Lucas',
           'Mariana','Nicolas','Olivia','Paulo','Queila','Rafael','Sofia','Tiago','Ursula','Vitor','Wanda','Yuri'])[1 + i % 24]
    || ' ' ||
    (ARRAY['Almeida','Barbosa','Cardoso','Duarte','Esteves','Ferreira','Gomes','Henriques','Isidoro','Jardim','Lima','Moreira',
           'Nogueira','Oliveira','Pereira','Queiroz','Ribeiro','Santos','Teixeira','Uchoa','Vieira','Xavier','Zanetti','Machado'])[1 + (i / 24) % 24],
    CASE WHEN i % 3 = 0 THEN 'Cliente' || i || '@Exemplo.com' ELSE 'cliente' || i || '@exemplo.com' END,
    (ARRAY['Sao Paulo','Rio de Janeiro','Belo Horizonte','Curitiba','Porto Alegre','Salvador',
           'Recife','Fortaleza','Brasilia','Manaus','Goiania','Florianopolis'])[1 + (i * 7) % 12],
    timestamp '2022-01-01' + ((i::bigint * 7919) % (730 * 86400)) * interval '1 second'
FROM generate_series(1, 100000) AS i;

\echo 'Gerando 20.000 produtos...'
INSERT INTO produtos (id, nome, categoria, preco_centavos)
SELECT
    i,
    (ARRAY['Cadeira','Mesa','Luminaria','Teclado','Mouse','Monitor','Headset','Mochila','Garrafa','Caderno',
           'Caneta','Webcam','Suporte','Cabo','Carregador','Estante','Tapete','Relogio','Fone','Agenda'])[1 + i % 20]
    || ' ' ||
    (ARRAY['Ergonomica','Compacta','Premium','Basica','Portatil','Sem Fio','Dobravel','Reforcada','Slim','Pro'])[1 + (i / 20) % 10]
    || ' Modelo ' || i,
    (ARRAY['Moveis','Moveis','Iluminacao','Perifericos','Perifericos','Perifericos','Audio','Acessorios','Acessorios','Papelaria',
           'Papelaria','Perifericos','Acessorios','Acessorios','Acessorios','Moveis','Moveis','Acessorios','Audio','Papelaria'])[1 + i % 20],
    990 + ((i::bigint * 7919) % 49000) * 10
FROM generate_series(1, 20000) AS i;

\echo 'Gerando 500.000 pedidos...'
INSERT INTO pedidos (id, cliente_id, status, criado_em, observacoes)
SELECT
    i,
    1 + ((i::bigint * 48271) % 100000),
    CASE
        WHEN (i * 37) % 100 < 60 THEN 'pago'
        WHEN (i * 37) % 100 < 85 THEN 'entregue'
        WHEN (i * 37) % 100 < 95 THEN 'cancelado'
        ELSE 'pendente'
    END,
    timestamp '2024-01-01' + ((i::bigint * 104729) % (731 * 86400)) * interval '1 second',
    repeat('Pedido registrado pelo canal online e confirmado por e-mail. ', 2 + i % 6)
FROM generate_series(1, 500000) AS i;

\echo 'Gerando itens dos pedidos (cerca de 1,5 milhao)...'
INSERT INTO itens_pedido (id, pedido_id, produto_id, quantidade, preco_unitario_centavos)
SELECT
    (p.id - 1) * 5 + n,
    p.id,
    pr.id,
    1 + (p.id + n) % 3,
    pr.preco_centavos
FROM pedidos p
CROSS JOIN LATERAL generate_series(1, 1 + p.id % 5) AS n
JOIN produtos pr ON pr.id = CASE
    WHEN (p.id + n) % 4 = 0 THEN 1 + ((p.id::bigint * 31 + n) % 200)
    ELSE 1 + ((p.id::bigint * 2654435761 + n * 40503) % 20000)
END;

ANALYZE;

\echo 'Banco pronto.'
