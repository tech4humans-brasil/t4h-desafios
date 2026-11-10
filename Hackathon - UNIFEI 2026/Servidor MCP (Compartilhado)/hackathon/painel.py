"""Painel ao vivo: mostra eventos, chamadas, conversas e o que o mundo fez, e deixa uma pessoa criar eventos."""

from __future__ import annotations

import json
import pathlib

import anyio
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from . import legado
from .nucleo import LIMITE_TEXTO, para_json

LIMITE_CORPO = 10_000

HTML = (pathlib.Path(__file__).parent / "painel.html").read_text(encoding="utf-8")


def rotas(mundo) -> list[Route]:
    async def pagina(request: Request) -> HTMLResponse:
        return HTMLResponse(HTML)

    async def estado(request: Request) -> JSONResponse:
        return Response(para_json(mundo.estado()), media_type="application/json")

    async def novo_evento(request: Request) -> JSONResponse:
        if mundo.relogio.encerrado():
            return JSONResponse({"erro": "O cenário terminou: não dá para criar eventos novos."}, status_code=410)
        corpo_bruto = await request.body()
        if len(corpo_bruto) > LIMITE_CORPO:
            return JSONResponse({"erro": f"O corpo do pedido passa de {LIMITE_CORPO // 1000} KB."}, status_code=413)
        try:
            if "application/json" in request.headers.get("content-type", ""):
                dados = json.loads(corpo_bruto or b"{}")
            else:
                dados = dict(await request.form())
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"erro": "O corpo do pedido não é JSON válido."}, status_code=400)
        if not isinstance(dados, dict):
            return JSONResponse({"erro": "O corpo do pedido precisa ser um objeto com de, nome, assunto e corpo."}, status_code=400)
        campo = lambda k, limite: str(dados.get(k) or "").strip()[:limite]
        assunto, corpo = campo("assunto", 300), campo("corpo", LIMITE_TEXTO)
        if not assunto or not corpo:
            return JSONResponse({"erro": "Preencha o assunto e a mensagem (campos assunto e corpo)."}, status_code=400)
        de = campo("de", 200) or "pessoa@t4h.exemplo"
        item = mundo.evento_manual(de, campo("nome", 200), assunto, corpo)
        return JSONResponse({"id": item["id"]})

    async def eventos(request: Request) -> EventSourceResponse:
        envio, recebimento = anyio.create_memory_object_stream(500)
        mundo.assinantes.add(envio)

        async def fluxo():
            try:
                async with recebimento:
                    async for evento in recebimento:
                        yield {"data": para_json(evento)}
            finally:
                mundo.assinantes.discard(envio)

        return EventSourceResponse(fluxo(), ping=15)

    async def indice_legado(request: Request) -> HTMLResponse:
        return legado.indice(mundo.tema.legado)

    return [
        Route("/", pagina),
        Route("/api/estado", estado),
        Route("/api/eventos", eventos),
        Route("/api/evento", novo_evento, methods=["POST"]),
        Route("/legado", indice_legado),
        *mundo.tema.rotas_legado(),
    ]
