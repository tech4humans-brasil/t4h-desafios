const { Client } = require('pg');

const config = {
  host: process.env.DB_HOST || 'localhost',
  port: Number(process.env.DB_PORT || 5432),
  user: process.env.DB_USER || 'loja',
  database: process.env.DB_NAME || 'loja',
};

async function consultar(sql, parametros = []) {
  const cliente = new Client(config);
  await cliente.connect();
  try {
    const resultado = await cliente.query(sql, parametros);
    return resultado.rows;
  } finally {
    await cliente.end();
  }
}

module.exports = { consultar };
