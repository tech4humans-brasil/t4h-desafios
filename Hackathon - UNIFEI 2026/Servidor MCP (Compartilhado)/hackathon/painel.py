"""Painel ao vivo: mostra eventos, chamadas, conversas e o que o mundo fez, e deixa uma pessoa criar eventos."""

from __future__ import annotations

import json
import pathlib

import anyio
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from . import legado

HTML = (pathlib.Path(__file__).parent / "painel.html").read_text(encoding="utf-8")


def rotas(mundo) -> list[Route]:
    async def pagina(request: Request) -> HTMLResponse:
        return HTMLResponse(HTML)

    async def estado(request: Request) -> JSONResponse:
        return JSONResponse(mundo.estado())

    async def novo_evento(request: Request) -> JSONResponse:
        dados = await request.json()
        assunto = str(dados.get("assunto", "")).strip()
        corpo = str(dados.get("corpo", "")).strip()
        if not assunto or not corpo:
            return JSONResponse({"erro": "Preencha o assunto e a mensagem."}, status_code=400)
        de = str(dados.get("de", "")).strip() or "pessoa@t4h.exemplo"
        item = mundo.evento_manual(de, str(dados.get("nome", "")).strip(), assunto, corpo)
        return JSONResponse({"id": item["id"]})

    async def eventos(request: Request) -> EventSourceResponse:
        envio, recebimento = anyio.create_memory_object_stream(500)
        mundo.assinantes.add(envio)

        async def fluxo():
            try:
                async with recebimento:
                    async for evento in recebimento:
                        yield {"data": json.dumps(evento, ensure_ascii=False)}
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
