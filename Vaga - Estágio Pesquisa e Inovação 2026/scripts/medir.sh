#!/usr/bin/env bash
# Mede a API sob carga e salva o resultado em resultados/<data>-<rotulo>/.
#
#   scripts/medir.sh <rotulo>              ex.: scripts/medir.sh 00-linha-de-base
#   VUS=50 DURACAO=120s scripts/medir.sh 03-mais-carga
#
# Gera resumo.txt (tempo de resposta e requisições/s, geral e por rota),
# recursos.txt (CPU e memória de cada container durante a carga), recursos.csv (amostras) e contexto.txt.

set -euo pipefail
cd "$(dirname "$0")/.."

ROTULO="${1:-}"
if [[ -z "$ROTULO" || ! "$ROTULO" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "uso: scripts/medir.sh <rotulo>   (letras, números, ponto, hífen ou sublinhado; ex.: 00-linha-de-base)" >&2
  exit 2
fi

VUS="${VUS:-20}"
DURACAO="${DURACAO:-60s}"
AQUECIMENTO="${AQUECIMENTO:-15s}"
PASTA="$(date +%Y%m%d-%H%M%S)-${ROTULO}"
SAIDA="resultados/${PASTA}"
USUARIO="$(id -u):$(id -g)"

if ! curl -fsS http://127.0.0.1:3000/saude >/dev/null 2>&1; then
  echo "A API não respondeu em http://127.0.0.1:3000/saude. Suba tudo com: docker compose up -d --build" >&2
  exit 1
fi

mkdir -p "$SAIDA"

{
  echo "rotulo: ${ROTULO}"
  echo "data: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "vus: ${VUS}"
  echo "duracao: ${DURACAO}"
  echo "aquecimento: ${AQUECIMENTO}"
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "commit: $(git rev-parse --short HEAD)"
    echo "arquivos alterados sem commit: $(git status --porcelain -- . | wc -l | tr -d ' ')"
  fi
  echo
  echo "limites dos containers:"
  for servico in api banco; do
    id="$(docker compose ps -q "$servico")"
    docker inspect --format "  ${servico}: cpus={{.HostConfig.NanoCpus}} (1e9 = 1 CPU) memoria={{.HostConfig.Memory}} bytes" "$id"
  done
} > "${SAIDA}/contexto.txt"

echo "Aquecendo por ${AQUECIMENTO} (não entra na medição)..."
docker compose run --rm --user "$USUARIO" -e VUS=5 -e DURACAO="$AQUECIMENTO" \
  carga run --quiet --no-summary /carga/teste-carga.js >/dev/null

IDS="$(docker compose ps -q api banco | tr '\n' ' ')"
echo "momento,container,cpu_percentual,memoria" > "${SAIDA}/recursos.csv"
(
  while true; do
    agora="$(date +%H:%M:%S)"
    # shellcheck disable=SC2086
    docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' $IDS 2>/dev/null \
      | sed "s/^/${agora},/" >> "${SAIDA}/recursos.csv" || true
  done
) &
COLETOR=$!
trap 'kill "$COLETOR" 2>/dev/null || true' EXIT

echo "Medindo: ${VUS} usuários virtuais por ${DURACAO}..."
docker compose run --rm --user "$USUARIO" -e VUS="$VUS" -e DURACAO="$DURACAO" -e ROTULO="$ROTULO" \
  -e SAIDA="/resultados/${PASTA}" carga run --quiet /carga/teste-carga.js

kill "$COLETOR" 2>/dev/null || true
wait "$COLETOR" 2>/dev/null || true

awk -F',' '
  function mib(valor,   numero, unidade) {
    numero = valor; unidade = valor
    gsub(/[^0-9.]/, "", numero); gsub(/[0-9. ]/, "", unidade)
    if (unidade == "GiB") return numero * 1024
    if (unidade == "KiB") return numero / 1024
    if (unidade == "B")   return numero / 1048576
    return numero
  }
  NR > 1 {
    nome = $2; cpu = $3; gsub(/%/, "", cpu)
    split($4, partes, " / "); memoria = mib(partes[1])
    amostras[nome]++; soma_cpu[nome] += cpu; soma_mem[nome] += memoria
    if (cpu > max_cpu[nome]) max_cpu[nome] = cpu
    if (memoria > max_mem[nome]) max_mem[nome] = memoria
  }
  END {
    printf "%-36s %8s %10s %10s %12s %12s\n", "container", "amostras", "cpu_media", "cpu_max", "mem_media", "mem_max"
    for (nome in amostras)
      printf "%-36s %8d %9.1f%% %9.1f%% %8.1f MiB %8.1f MiB\n", nome, amostras[nome], soma_cpu[nome] / amostras[nome], max_cpu[nome], soma_mem[nome] / amostras[nome], max_mem[nome]
    print ""
    print "cpu_percentual: 100% = 1 CPU inteira."
  }
' "${SAIDA}/recursos.csv" > "${SAIDA}/recursos.txt"

echo
echo "Uso de recursos durante a carga:"
cat "${SAIDA}/recursos.txt"
echo
echo "Resultado salvo em ${SAIDA}/"
