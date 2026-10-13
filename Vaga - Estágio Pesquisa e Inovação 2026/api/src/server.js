const express = require('express');
const rotas = require('./rotas');

const app = express();
const porta = Number(process.env.PORT || 3000);

app.use((req, res, next) => {
  const inicio = Date.now();
  const enviarJson = res.json.bind(res);
  res.json = (corpo) => {
    console.log(JSON.stringify({
      metodo: req.method,
      url: req.originalUrl,
      status: res.statusCode,
      duracao_ms: Date.now() - inicio,
      resposta: corpo,
    }));
    return enviarJson(corpo);
  };
  next();
});

app.use(rotas);

app.use((req, res) => {
  res.status(404).json({ erro: 'rota nao encontrada' });
});

app.use((erro, req, res, next) => {
  console.error(erro);
  res.status(500).json({ erro: 'erro interno' });
});

app.listen(porta, () => {
  console.log(`API ouvindo na porta ${porta}`);
});
