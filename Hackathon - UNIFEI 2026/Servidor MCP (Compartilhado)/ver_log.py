"""Lê o log de uma rodada do mundo e mostra chamadas, conversas e alertas.

Uso:
    python ver_log.py logs/triagem-20261214-093000.jsonl
    python ver_log.py logs/<arquivo>.jsonl --agente triador
    python ver_log.py logs/<arquivo>.jsonl --erros
Sem arquivo, usa o log mais recente da pasta logs/.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter

AQUI = pathlib.Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Mostra o log de uma rodada do mundo do hackathon")
    parser.add_argument("log", nargs="?", help="arquivo .jsonl (padrão: o mais recente em logs/)")
    parser.add_argument("--agente", help="mostra só as chamadas deste agente")
    parser.add_argument("--erros", action="store_true", help="mostra só as chamadas com erro")
    args = parser.parse_args()

    if args.log:
        caminho = pathlib.Path(args.log)
    else:
        logs = sorted((AQUI / "logs").glob("*.jsonl"))
        if not logs:
            print("Ainda não há log. Suba o mundo com python mundo.py e conecte um agente.")
            return
        caminho = logs[-1]

    eventos = [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]
    chamadas = [e for e in eventos if e["tipo"] == "chamada"]
    if args.agente:
        chamadas = [e for e in chamadas if e["agente"] == args.agente]
    if args.erros:
        chamadas = [e for e in chamadas if e["resultado"] == "erro"]

    print(f"Log: {caminho.name}\n")
    for e in eventos:
        if e["tipo"] == "chamada" and e in chamadas:
            status = "OK" if e["resultado"] == "ok" else f"ERRO {e['codigo']}" + (" (simulada)" if e.get("falha") else "")
            print(f"{e['agora']}  {e['agente'] or '-':<14} {e['ferramenta']:<22} {status}")
            if e.get("motivo"):
                print(f"{'':22}motivo: {e['motivo']}")
        elif e["tipo"] == "conversa" and not (args.agente or args.erros):
            print(f"{e['agora']}  {e['de']} → {e['para']}: {e['mensagem']}")
        elif e["tipo"] == "alerta" and not (args.agente or args.erros):
            print(f"{e['agora']}  [{e['nivel'].upper()}] {e['mensagem']}")

    todas = [e for e in eventos if e["tipo"] == "chamada"]
    print(f"\n{len(todas)} chamadas, {sum(e['resultado'] == 'erro' for e in todas)} com erro")
    print("Por agente: " + ", ".join(f"{k or '-'} {v}" for k, v in Counter(e["agente"] for e in todas).most_common()))
    print("Por ferramenta: " + ", ".join(f"{k} {v}" for k, v in Counter(e["ferramenta"] for e in todas).most_common()))
    alertas = Counter(e["nivel"] for e in eventos if e["tipo"] == "alerta")
    print("Alertas: " + (", ".join(f"{k} {v}" for k, v in alertas.items()) or "nenhum"))


if __name__ == "__main__":
    main()
