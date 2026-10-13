// Teste de carga da API da loja (k6).
// Cada usuário virtual (VU) faz requisições em sequência, sem pausa, sorteando a rota pelo peso.
// O sorteio usa uma semente fixa por VU: duas execuções com os mesmos parâmetros pedem as mesmas URLs.

import http from 'k6/http';
import { check } from 'k6';

const URL_BASE = __ENV.URL_BASE || 'http://localhost:3000';
const VUS = Number(__ENV.VUS || 20);
const DURACAO = __ENV.DURACAO || '60s';
const ROTULO = __ENV.ROTULO || 'sem-rotulo';
const SAIDA = __ENV.SAIDA || '';
const SEMENTE = Number(__ENV.SEMENTE || 42);

const TERMOS = ['cadeira', 'mesa', 'lumin', 'teclado', 'monitor', 'ergo', 'sem fio', 'portatil', 'modelo 12', 'slim', 'reforcada', 'webcam'];
const STATUS = ['pago', 'entregue', 'cancelado', 'pendente'];
const PRIMEIRO_DIA = Date.UTC(2024, 0, 1);

let aleatorio;

function gerador(semente) {
  let estado = semente >>> 0;
  return () => {
    estado = (estado + 0x6d2b79f5) >>> 0;
    let t = estado;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function inteiro(min, max) {
  return min + Math.floor(aleatorio() * (max - min + 1));
}

function escolher(lista) {
  return lista[inteiro(0, lista.length - 1)];
}

function dia(deslocamento) {
  return new Date(PRIMEIRO_DIA + deslocamento * 86400000).toISOString().slice(0, 10);
}

const ROTAS = [
  { nome: 'cliente', peso: 25, caminho: () => `/clientes/${inteiro(1, 100000)}` },
  { nome: 'cliente-por-email', peso: 15, caminho: () => `/clientes?email=cliente${inteiro(1, 100000)}%40exemplo.com` },
  { nome: 'pedidos-do-cliente', peso: 20, caminho: () => `/clientes/${inteiro(1, 100000)}/pedidos` },
  { nome: 'pedidos-por-status', peso: 15, caminho: () => `/pedidos?status=${escolher(STATUS)}&pagina=${inteiro(1, 1000)}` },
  { nome: 'busca-produtos', peso: 15, caminho: () => `/produtos/busca?q=${encodeURIComponent(escolher(TERMOS))}` },
  {
    nome: 'vendas-por-dia',
    peso: 8,
    caminho: () => {
      const inicio = inteiro(0, 724);
      return `/relatorios/vendas-por-dia?inicio=${dia(inicio)}&fim=${dia(inicio + 6)}`;
    },
  },
  { nome: 'top-produtos', peso: 2, caminho: () => '/relatorios/top-produtos?limite=10' },
];

const PESO_TOTAL = ROTAS.reduce((soma, rota) => soma + rota.peso, 0);

function sortearRota() {
  let sorteio = aleatorio() * PESO_TOTAL;
  for (const rota of ROTAS) {
    sorteio -= rota.peso;
    if (sorteio < 0) return rota;
  }
  return ROTAS[ROTAS.length - 1];
}

const thresholds = {};
for (const rota of ROTAS) {
  // Limites que sempre passam: existem só para o k6 calcular as métricas de cada rota.
  thresholds[`http_req_duration{rota:${rota.nome}}`] = ['max>=0'];
  thresholds[`http_req_failed{rota:${rota.nome}}`] = ['rate>=0'];
}

export const options = {
  scenarios: {
    carga: { executor: 'constant-vus', vus: VUS, duration: DURACAO, gracefulStop: '30s' },
  },
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max', 'count'],
  thresholds,
};

export default function () {
  if (!aleatorio) aleatorio = gerador(SEMENTE * 1000 + __VU);

  const rota = sortearRota();
  const resposta = http.get(`${URL_BASE}${rota.caminho()}`, {
    tags: { rota: rota.nome, name: rota.nome },
    timeout: '60s',
  });
  check(resposta, { 'status 200': (r) => r.status === 200 });
}

function ms(valor) {
  return valor === undefined ? '-' : `${valor.toFixed(1)} ms`;
}

function linha(colunas, larguras) {
  return colunas.map((coluna, i) => String(coluna).padEnd(larguras[i])).join('  ');
}

export function handleSummary(data) {
  const larguras = [20, 8, 12, 12, 12, 8];
  const tabela = [linha(['rota', 'req', 'mediana', 'p95', 'p99', 'erros'], larguras)];

  for (const rota of ROTAS) {
    const duracao = data.metrics[`http_req_duration{rota:${rota.nome}}`];
    const falhas = data.metrics[`http_req_failed{rota:${rota.nome}}`];
    if (!duracao) continue;
    tabela.push(linha([
      rota.nome,
      duracao.values.count,
      ms(duracao.values.med),
      ms(duracao.values['p(95)']),
      ms(duracao.values['p(99)']),
      `${((falhas ? falhas.values.rate : 0) * 100).toFixed(1)}%`,
    ], larguras));
  }

  const geral = data.metrics.http_req_duration.values;
  const requisicoes = data.metrics.http_reqs.values;
  const falhas = data.metrics.http_req_failed.values;

  const texto = [
    `Medição: ${ROTULO}`,
    `Carga: ${VUS} usuários virtuais por ${DURACAO}`,
    '',
    `Requisições:        ${requisicoes.count}`,
    `Requisições/s:      ${requisicoes.rate.toFixed(2)}`,
    `Tempo de resposta:  mediana ${ms(geral.med)} | p95 ${ms(geral['p(95)'])} | p99 ${ms(geral['p(99)'])}`,
    `Erros:              ${(falhas.rate * 100).toFixed(2)}%`,
    '',
    'Por rota:',
    ...tabela,
    '',
  ].join('\n');

  const saidas = { stdout: texto };
  if (SAIDA) {
    saidas[`${SAIDA}/resumo.txt`] = texto;
    saidas[`${SAIDA}/resumo-k6.json`] = JSON.stringify(data, null, 2);
  }
  return saidas;
}
