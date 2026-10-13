// Verifica se a API continua devolvendo exatamente o mesmo que devolvia antes das suas mudanças.
//
//   node verificar.js gravar    -> chama cada caso e salva as respostas em base.json
//   node verificar.js comparar  -> chama de novo e compara com base.json (status e corpo, inclusive a ordem)

const fs = require('node:fs');
const path = require('node:path');

const URL_BASE = process.env.URL_BASE || 'http://localhost:3000';
const ARQUIVO_BASE = path.join(__dirname, 'base.json');

const CASOS = [
  '/clientes/1',
  '/clientes/2',
  '/clientes/500',
  '/clientes/99999',
  '/clientes/100000',
  '/clientes/100001',
  '/clientes/abc',
  '/clientes?email=cliente3%40exemplo.com',
  '/clientes?email=Cliente4%40Exemplo.com',
  '/clientes?email=CLIENTE10%40EXEMPLO.COM',
  '/clientes?email=ninguem%40exemplo.com',
  '/clientes',
  '/clientes/7/pedidos',
  '/clientes/42/pedidos',
  '/clientes/31337/pedidos',
  '/clientes/99999/pedidos',
  '/clientes/100001/pedidos',
  '/pedidos?status=pago',
  '/pedidos?status=entregue&pagina=3',
  '/pedidos?status=cancelado&pagina=250',
  '/pedidos?status=pendente&pagina=1',
  '/pedidos?status=pago&pagina=15000',
  '/pedidos?status=perdido',
  '/pedidos?status=pago&pagina=0',
  '/produtos/busca?q=cadeira',
  '/produtos/busca?q=lumin',
  '/produtos/busca?q=ERGO',
  '/produtos/busca?q=sem%20fio',
  '/produtos/busca?q=inexistente',
  '/produtos/busca?q=ab',
  '/relatorios/vendas-por-dia?inicio=2024-01-01&fim=2024-01-07',
  '/relatorios/vendas-por-dia?inicio=2024-02-27&fim=2024-03-02',
  '/relatorios/vendas-por-dia?inicio=2025-12-25&fim=2025-12-31',
  '/relatorios/vendas-por-dia?inicio=2023-12-30&fim=2024-01-02',
  '/relatorios/vendas-por-dia?inicio=2024-03-01&fim=2024-02-01',
  '/relatorios/vendas-por-dia?inicio=2024-01-01&fim=2024-03-01',
  '/relatorios/vendas-por-dia?inicio=2024-02-30&fim=2024-03-01',
  '/relatorios/top-produtos',
  '/relatorios/top-produtos?limite=5',
  '/relatorios/top-produtos?limite=50',
  '/relatorios/top-produtos?limite=0',
  '/relatorios/top-produtos?limite=51',
];

async function chamar(caminho) {
  const resposta = await fetch(`${URL_BASE}${caminho}`);
  const texto = await resposta.text();
  let corpo;
  try {
    corpo = JSON.parse(texto);
  } catch {
    corpo = texto;
  }
  return { status: resposta.status, corpo };
}

function primeiraDiferenca(esperado, obtido, caminho = '') {
  if (typeof esperado !== typeof obtido || Array.isArray(esperado) !== Array.isArray(obtido)) {
    return `${caminho || '(raiz)'}: esperado ${JSON.stringify(esperado)}, obtido ${JSON.stringify(obtido)}`;
  }
  if (esperado === null || obtido === null || typeof esperado !== 'object') {
    return esperado === obtido ? null : `${caminho || '(raiz)'}: esperado ${JSON.stringify(esperado)}, obtido ${JSON.stringify(obtido)}`;
  }
  if (Array.isArray(esperado) && esperado.length !== obtido.length) {
    return `${caminho || '(raiz)'}: esperado ${esperado.length} itens, obtido ${obtido.length}`;
  }
  const chavesEsperadas = Object.keys(esperado);
  const chavesObtidas = Object.keys(obtido);
  if (chavesEsperadas.join() !== chavesObtidas.join()) {
    return `${caminho || '(raiz)'}: esperado os campos [${chavesEsperadas}], obtido [${chavesObtidas}]`;
  }
  for (const chave of chavesEsperadas) {
    const diferenca = primeiraDiferenca(esperado[chave], obtido[chave], Array.isArray(esperado) ? `${caminho}[${chave}]` : `${caminho}.${chave}`);
    if (diferenca) return diferenca;
  }
  return null;
}

async function gravar() {
  const base = {};
  for (const caso of CASOS) {
    process.stdout.write(`gravando ${caso} ... `);
    base[caso] = await chamar(caso);
    console.log(base[caso].status);
  }
  fs.writeFileSync(ARQUIVO_BASE, `${JSON.stringify(base, null, 2)}\n`);
  console.log(`\n${CASOS.length} respostas gravadas em contrato/base.json`);
}

async function comparar() {
  if (!fs.existsSync(ARQUIVO_BASE)) {
    console.error('contrato/base.json não existe. Rode "gravar" com a aplicação original antes de qualquer mudança.');
    process.exit(2);
  }
  const base = JSON.parse(fs.readFileSync(ARQUIVO_BASE, 'utf8'));
  let falhas = 0;
  for (const caso of CASOS) {
    if (!(caso in base)) {
      console.log(`SEM BASE  ${caso}`);
      falhas += 1;
      continue;
    }
    const diferenca = primeiraDiferenca(base[caso], await chamar(caso));
    if (diferenca) {
      falhas += 1;
      console.log(`DIFERENTE ${caso}\n          ${diferenca}`);
    } else {
      console.log(`igual     ${caso}`);
    }
  }
  console.log(falhas === 0
    ? `\nContrato mantido: as ${CASOS.length} respostas são iguais às gravadas.`
    : `\nContrato quebrado: ${falhas} de ${CASOS.length} respostas mudaram.`);
  process.exit(falhas === 0 ? 0 : 1);
}

const modo = process.argv[2];
if (modo === 'gravar') {
  gravar().catch((erro) => { console.error(erro.message); process.exit(2); });
} else if (modo === 'comparar') {
  comparar().catch((erro) => { console.error(erro.message); process.exit(2); });
} else {
  console.error('uso: node verificar.js gravar | comparar');
  process.exit(2);
}
