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
        logs = sorted((AQUI / "logs").glob("*.jsonl"), key=lambda c: c.stat().st_mtime)
        if not logs:
            print("Ainda não há log. Suba o mundo com python mundo.py e conecte um agente.")
            return
        caminho = logs[-1]

    if not caminho.exists():
        print(f"O arquivo {caminho} não existe.")
        return
    eventos, ruins = [], 0
    for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
        if not linha.strip():
            continue
        try:
            e = json.loads(linha)
        except json.JSONDecodeError:
            ruins += 1
            continue
        if isinstance(e, dict) and "tipo" in e:
            eventos.append(e)
    if ruins:
        print(f"({ruins} linha(s) ilegíveis ignoradas)")
    chamadas = [e for e in eventos if e["tipo"] == "chamada"]
    if args.agente:
        chamadas = [e for e in chamadas if e.get("agente") == args.agente]
    if args.erros:
        chamadas = [e for e in chamadas if e.get("resultado") == "erro"]
    ids = {id(e) for e in chamadas}

    print(f"Log: {caminho.name}\n")
    for e in eventos:
        if e["tipo"] == "chamada" and id(e) in ids:
            status = "OK" if e.get("resultado") == "ok" else f"ERRO {e.get('codigo')}" + (" (simulada)" if e.get("falha") else "")
            via = " (tela)" if e.get("via") == "tela" else ""
            print(f"{e.get('agora', '')}  {e.get('agente') or '-':<14} {e.get('ferramenta', ''):<22} {status}{via}")
            if e.get("motivo"):
                print(f"{'':22}motivo: {e['motivo']}")
        elif e["tipo"] == "conversa" and not (args.agente or args.erros):
            print(f"{e.get('agora', '')}  {e.get('de')} → {e.get('para')}: {e.get('mensagem')}")
        elif e["tipo"] == "alerta" and not (args.agente or args.erros):
            print(f"{e.get('agora', '')}  [{str(e.get('nivel', '')).upper()}] {e.get('mensagem')}")

    todas = chamadas
    filtro = " (filtradas)" if args.agente or args.erros else ""
    conversas = sum(e["tipo"] == "conversa" for e in eventos) if not (args.agente or args.erros) else 0
    extra = f" (mais {conversas} conversas registradas, que o painel conta junto)" if conversas else ""
    print(f"\n{len(todas)} chamadas{filtro}, {sum(e.get('resultado') == 'erro' for e in todas)} com erro{extra}")
    print("Por agente: " + ", ".join(f"{k or '-'} {v}" for k, v in Counter(e.get("agente") for e in todas).most_common()))
    print("Por ferramenta: " + ", ".join(f"{k} {v}" for k, v in Counter(e.get("ferramenta") for e in todas).most_common()))
    alertas = Counter(e.get("nivel") for e in eventos if e["tipo"] == "alerta")
    print("Alertas: " + (", ".join(f"{k} {v}" for k, v in alertas.items()) or "nenhum"))


if __name__ == "__main__":
    main()
