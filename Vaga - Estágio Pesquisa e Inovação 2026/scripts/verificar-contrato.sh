#!/usr/bin/env bash
# Confere se as rotas continuam devolvendo o mesmo de antes.
#
#   scripts/verificar-contrato.sh gravar     # uma vez, com a aplicação original, antes de mudar qualquer coisa
#   scripts/verificar-contrato.sh comparar   # depois de cada mudança

set -euo pipefail
cd "$(dirname "$0")/.."

MODO="${1:-}"
if [[ "$MODO" != "gravar" && "$MODO" != "comparar" ]]; then
  echo "uso: scripts/verificar-contrato.sh gravar | comparar" >&2
  exit 2
fi

if [[ "$MODO" == "gravar" && -f contrato/base.json && "${FORCAR:-}" != "1" ]]; then
  echo "contrato/base.json já existe. Ele precisa ser da aplicação original; para regravar mesmo assim, use FORCAR=1." >&2
  exit 2
fi

docker compose run --rm --user "$(id -u):$(id -g)" contrato "$MODO"
