"""Painel ao vivo: uma página que mostra pedidos, chamadas, conversas e o que o mundo fez."""

from __future__ import annotations

import json
import pathlib

import anyio
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

HTML = (pathlib.Path(__file__).parent / "painel.html").read_text(encoding="utf-8")


def rotas(mundo) -> list[Route]:
    async def pagina(request: Request) -> HTMLResponse:
        return HTMLResponse(HTML)

    async def estado(request: Request) -> JSONResponse:
        return JSONResponse(mundo.estado())

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

    return [
        Route("/", pagina),
        Route("/api/estado", estado),
        Route("/api/eventos", eventos),
    ]
