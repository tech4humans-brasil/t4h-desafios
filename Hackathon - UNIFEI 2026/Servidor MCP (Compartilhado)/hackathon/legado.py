"""Telas dos sistemas legados: não têm API, só HTML. Para usar, o agente precisa operar a tela (computer use)."""

from __future__ import annotations

from html import escape

from starlette.responses import HTMLResponse

ESTILO = """
body { font-family: Verdana, Geneva, sans-serif; font-size: 13px; background: #d4d0c8; color: #000; margin: 0; }
.janela { max-width: 760px; margin: 24px auto; background: #ece9d8; border: 2px outset #fff; }
.titulo { background: #0a246a; color: #fff; font-weight: bold; padding: 6px 10px; }
.conteudo { padding: 14px 18px; }
table { border-collapse: collapse; width: 100%; background: #fff; margin: 8px 0 14px; }
th, td { border: 1px solid #808080; padding: 4px 6px; text-align: left; }
th { background: #c0c0c0; }
label { display: block; margin-top: 8px; }
input, select, textarea { font: inherit; padding: 2px 4px; border: 2px inset #fff; }
button { font: inherit; padding: 3px 14px; margin-top: 12px; }
.erro { background: #fff0f0; border: 1px solid #c00; color: #900; padding: 6px 8px; margin-bottom: 10px; }
.ok { background: #f0fff0; border: 1px solid #080; color: #060; padding: 6px 8px; margin-bottom: 10px; }
.rodape { font-size: 11px; color: #444; margin-top: 12px; }
"""


def pagina(titulo: str, corpo: str, status: int = 200) -> HTMLResponse:
    html = (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        f"<title>{escape(titulo)}</title><style>{ESTILO}</style></head><body>"
        f"<div class='janela'><div class='titulo'>{escape(titulo)}</div><div class='conteudo'>{corpo}</div></div>"
        "</body></html>"
    )
    return HTMLResponse(html, status_code=status)


def campo(nome: str, rotulo: str, valor: str = "", tipo: str = "text", extra: str = "") -> str:
    return (
        f"<label for='{escape(nome)}'>{escape(rotulo)}</label>"
        f"<input id='{escape(nome)}' name='{escape(nome)}' type='{escape(tipo)}' value='{escape(valor)}' {extra}>"
    )


def mensagem(texto: str, classe: str) -> str:
    return f"<div class='{classe}'>{escape(texto)}</div>" if texto else ""


def indice(sistemas: list[dict]) -> HTMLResponse:
    linhas = "".join(
        f"<tr><td><a href='{escape(s['caminho'])}'>{escape(s['nome'])}</a></td><td>{escape(s['descricao'])}</td></tr>"
        for s in sistemas
    )
    corpo = (
        "<p>Sistemas antigos da empresa. Eles não têm API: tudo é feito pela tela.</p>"
        f"<table><tr><th>Sistema</th><th>Para quê</th></tr>{linhas}</table>"
    )
    return pagina("Sistemas legados", corpo)
