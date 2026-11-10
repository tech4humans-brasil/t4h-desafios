"""O mundo simulado: relógio, eventos, bases de dados, falhas, log e eventos do painel.

As ferramentas são genéricas de propósito: eventos (o que chega para o time), mensagens
(falar com pessoas e times do mundo) e bases (consultar, registrar e atualizar).
Memória, escalação e aprovação ficam com os times.
"""

from __future__ import annotations

import bisect
import heapq
import itertools
import json
import math
import pathlib
import random
import time
import traceback
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable

import anyio
import mcp_types as types

INICIO_DIA = 8 * 60  # o expediente simulado vai das 08:00 às 18:00
MINUTOS_DIA = 10 * 60
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
LIMITE_TEXTO = 2000
LIMITE_AGENTE = 60

# Falhas simuladas: (tipo, peso). "lento" responde certo, só que devagar.
FALHAS = [("indisponivel", 4), ("lento", 3), ("timeout", 2), ("conflito", 2)]
MENSAGENS_FALHA = {
    "indisponivel": (503, "Serviço temporariamente indisponível. Tente de novo em alguns segundos."),
    "timeout": (504, "O sistema demorou demais para responder. A ação pode ou não ter sido feita: confira antes de repetir."),
    "conflito": (409, "Outra operação estava em andamento no mesmo registro. Consulte de novo e tente outra vez."),
}
VERDADEIROS = (True, 1, "1", "true", "True", "sim", "yes")


def sem_acento(texto: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def somar_dias_uteis(inicio: date, n: int) -> date:
    d = inicio
    while d.weekday() >= 5:
        d += timedelta(days=1)
    passos = 0
    while passos < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            passos += 1
    return d


def limpar(valor: Any) -> Any:
    """Troca NaN e Infinity por None, em qualquer profundidade, para o JSON nunca quebrar."""
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    if isinstance(valor, dict):
        return {str(k): limpar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [limpar(v) for v in valor]
    return valor


def para_json(valor: Any) -> str:
    return json.dumps(limpar(valor), ensure_ascii=False, default=str, allow_nan=False)


class ErroFerramenta(Exception):
    """Erro de regra: o pedido do agente não pode ser atendido como veio."""

    def __init__(self, codigo: int, mensagem: str, **extra: Any) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.extra = extra


def inteiro(valor: Any, nome: str, padrao: int, minimo: int, maximo: int) -> int:
    if valor in (None, ""):
        return padrao
    if isinstance(valor, bool):
        raise ErroFerramenta(422, f"'{nome}' precisa ser um número inteiro.")
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ErroFerramenta(422, f"'{nome}' precisa ser um número inteiro.") from None
    if numero != valor and not isinstance(valor, str):
        raise ErroFerramenta(422, f"'{nome}' precisa ser um número inteiro.")
    return max(minimo, min(numero, maximo))


def texto_limitado(valor: Any, nome: str, limite: int = LIMITE_TEXTO) -> str:
    if valor is None:
        return ""
    if not isinstance(valor, (str, int, float)):
        raise ErroFerramenta(422, f"'{nome}' precisa ser texto.")
    texto = str(valor)
    if len(texto) > limite:
        raise ErroFerramenta(422, f"'{nome}' passa de {limite} caracteres.")
    return texto


class Relogio:
    """Relógio simulado em minutos de expediente. Começa parado e anda quando o primeiro agente chama algo."""

    def __init__(self, inicio: date, dias: int, segundos_por_dia: float) -> None:
        self.inicio = inicio
        self.dias = dias
        self.segundos_por_dia = segundos_por_dia
        self.t0: float | None = None

    @property
    def rodando(self) -> bool:
        return self.t0 is not None

    def iniciar(self) -> bool:
        if self.t0 is None:
            self.t0 = time.monotonic()
            return True
        return False

    def minuto(self) -> float:
        if self.t0 is None:
            return 0.0
        return min((time.monotonic() - self.t0) / self.segundos_por_dia * MINUTOS_DIA, self.dias * MINUTOS_DIA)

    def encerrado(self) -> bool:
        return self.minuto() >= self.dias * MINUTOS_DIA

    def dia(self, minuto: float | None = None) -> int:
        m = self.minuto() if minuto is None else minuto
        return min(int(m // MINUTOS_DIA) + 1, self.dias)

    def data(self, dia: int | None = None) -> date:
        return somar_dias_uteis(self.inicio, (dia or self.dia()) - 1)

    def texto(self, minuto: float | None = None) -> str:
        m = self.minuto() if minuto is None else minuto
        dia = self.dia(m)
        resto = m - (dia - 1) * MINUTOS_DIA
        total = INICIO_DIA + int(resto)
        d = self.data(dia)
        return f"{DIAS_SEMANA[d.weekday()]} {d.strftime('%d/%m/%Y')} {total // 60:02d}:{total % 60:02d}"

    def segundos_reais(self, minutos_simulados: float) -> float:
        return minutos_simulados / MINUTOS_DIA * self.segundos_por_dia

    @staticmethod
    def minuto_de(dia: int, hora: str) -> float:
        h, m = (int(x) for x in hora.split(":"))
        return (dia - 1) * MINUTOS_DIA + (h * 60 + m - INICIO_DIA)

    def minuto_da_data(self, d: date, hora: str = "08:00") -> float:
        dia = 1
        while self.data(dia) < d and dia < 400:
            dia += 1
        return self.minuto_de(dia, hora)


@dataclass
class Base:
    """Uma base de dados do mundo. Toda base pode ser consultada; registrar e atualizar são opcionais."""

    nome: str
    descricao: str
    registros: Callable[[], list[dict]]
    chave: str = "id"
    campos: tuple[str, ...] = ()
    registrar: Callable[[dict, str], dict] | None = None
    campos_registro: dict[str, str] = field(default_factory=dict)
    exemplo_registro: dict | None = None
    atualizar: Callable[[dict, dict, str], dict] | None = None
    campos_atualizaveis: tuple[str, ...] = ()

    def resumo(self) -> dict:
        regs = self.registros()
        campos = list(self.campos) or (list(regs[0].keys()) if regs else [])
        resumo = {
            "base": self.nome,
            "descricao": self.descricao,
            "total": len(regs),
            "chave": self.chave,
            "campos": campos,
            "pode_registrar": self.registrar is not None,
            "pode_atualizar": list(self.campos_atualizaveis) if self.atualizar else [],
        }
        if self.registrar:
            resumo["campos_para_registrar"] = self.campos_registro
            if self.exemplo_registro:
                resumo["exemplo_registrar"] = self.exemplo_registro
        return resumo


@dataclass
class Ferramenta:
    nome: str
    descricao: str
    funcao: Callable[[dict, str], Any]
    propriedades: dict = field(default_factory=dict)
    obrigatorios: list[str] = field(default_factory=list)
    leitura: bool = False  # só consulta: não sofre conflito simulado e não muda nada num 504
    falha: bool = True  # sujeita a falhas simuladas

    def como_tool(self) -> types.Tool:
        props: dict[str, Any] = {
            "agente": {"type": "string", "description": "Nome do agente do seu time que está chamando (aparece no painel)"},
            "motivo": {"type": "string", "description": "Por que o agente está fazendo esta chamada (opcional, aparece no painel)"},
        }
        props.update(self.propriedades)
        return types.Tool(
            name=self.nome,
            description=self.descricao,
            inputSchema={"type": "object", "properties": props, "required": ["agente", *self.obrigatorios]},
            annotations=types.ToolAnnotations(readOnlyHint=self.leitura),
        )


def texto(s: str) -> dict:
    return {"type": "string", "description": s}


def objeto(s: str) -> dict:
    return {"type": "object", "description": s}


def numero(s: str) -> dict:
    return {"type": "integer", "description": s}


class Mundo:
    def __init__(self, tema_cls: type, cenario: dict, dados: pathlib.Path, args: Any) -> None:
        self.sorteio = random.Random(args.seed)
        self.prob_erro = max(0.0, min(1.0, args.erros))
        self.porta = getattr(args, "porta_publica", args.porta)
        self.cenario = cenario
        self.relogio = Relogio(date.fromisoformat(cenario["inicio"]), int(cenario["dias"]), args.segundos_por_dia)
        self.log = pathlib.Path(args.log)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self._agenda: list[tuple[float, int, Callable[[], None]]] = []
        self._seq = itertools.count()
        self._ids: dict[str, itertools.count] = {}
        self._chegadas: list[float] = []  # minutos em que chegam os próximos eventos do cenário
        self.caixa: dict[str, dict] = {}
        self.mensagens: list[dict] = []
        self.alertas: list[dict] = []
        self.historico: deque[dict] = deque(maxlen=800)
        self.assinantes: set[Any] = set()
        self.agentes: dict[str, dict] = {}
        self.total_chamadas = 0
        self.total_erros = 0
        self._fim_avisado = False

        self.tema = tema_cls(self, dados, cenario)
        self.bases: dict[str, Base] = {b.nome: b for b in [self._base_eventos(), self._base_mensagens(), *self.tema.bases()]}
        self.ferramentas: dict[str, Ferramenta] = {f.nome: f for f in self._ferramentas()}

        if not getattr(args, "sem_cenario", False):
            for p in cenario["pedidos"]:
                base = Relogio.minuto_de(int(p["dia"]), p["hora"])
                chegada = max(0.0, base + self.sorteio.uniform(-15, 15))
                self.agendar(chegada, lambda p=p, m=chegada: self._chegar_do_cenario(p, m))
                bisect.insort(self._chegadas, chegada)

    # ---------- utilidades ----------
    def novo_id(self, prefixo: str, inicio: int = 1, largura: int = 2) -> str:
        contador = self._ids.setdefault(prefixo, itertools.count(inicio))
        return f"{prefixo}-{next(contador):0{largura}d}"

    def agendar(self, minuto: float, funcao: Callable[[], None]) -> None:
        heapq.heappush(self._agenda, (minuto, next(self._seq), funcao))

    def agendar_em_horas(self, horas: float, funcao: Callable[[], None]) -> None:
        self.agendar(self.relogio.minuto() + horas * 60, funcao)

    def agora(self) -> str:
        return self.relogio.texto()

    def url(self, caminho: str) -> str:
        return f"http://localhost:{self.porta}{caminho}"

    # ---------- emissão para o painel e o log ----------
    def emitir(self, tipo: str, **dados: Any) -> dict:
        evento = limpar({"tipo": tipo, "agora": self.agora(), "quando": datetime.now().isoformat(timespec="seconds"), **dados})
        self.historico.append(evento)
        with self.log.open("a", encoding="utf-8") as arquivo:
            arquivo.write(para_json(evento) + "\n")
        for fila in list(self.assinantes):
            try:
                fila.send_nowait(evento)
            except anyio.WouldBlock:
                # Cliente lento: fecha a conexão; o navegador reconecta sozinho e recarrega o estado.
                self.assinantes.discard(fila)
                fila.close()
            except (anyio.BrokenResourceError, anyio.ClosedResourceError):
                self.assinantes.discard(fila)
        return evento

    def alerta(self, nivel: str, mensagem: str, **dados: Any) -> None:
        item = {"nivel": nivel, "mensagem": mensagem, "agora": self.agora(), **dados}
        self.alertas.append(item)
        self.emitir("alerta", **item)

    def contar_agente(self, agente: str, ferramenta: str, erro: bool) -> None:
        info = self.agentes.setdefault(agente or "?", {"chamadas": 0, "erros": 0, "ultima": "", "ferramentas": {}})
        info["chamadas"] += 1
        info["erros"] += int(erro)
        info["ultima"] = ferramenta
        info["ferramentas"][ferramenta] = info["ferramentas"].get(ferramenta, 0) + 1

    # ---------- eventos (a caixa de entrada do time) ----------
    def _chegar_do_cenario(self, p: dict, minuto: float) -> None:
        indice = bisect.bisect_left(self._chegadas, minuto)
        if indice < len(self._chegadas) and self._chegadas[indice] == minuto:
            self._chegadas.pop(indice)
        if self.tema.deve_chegar(p):
            self.receber_evento(p)

    def receber_evento(self, p: dict, responde_a: str | None = None, evento_id: str | None = None, origem: str = "cenario") -> dict:
        eid = evento_id or p["id"]
        item = {
            "id": eid,
            "de": p["de"],
            "nome": p.get("nome", ""),
            "assunto": p["assunto"],
            "corpo": p["corpo"],
            "chegou_em": self.agora(),
            "minuto": self.relogio.minuto(),
            "status": "novo",
            "responde_a": responde_a,
            "origem": origem,
            "acoes": [],
            "_original": p,
        }
        self.caixa[eid] = item
        self.emitir("pedido", id=eid, de=item["de"], nome=item["nome"], assunto=item["assunto"], responde_a=responde_a, origem=origem)
        self.tema.ao_receber(item)
        return item

    def mensagem_do_mundo(self, de: str, nome: str, assunto: str, corpo: str, responde_a: str | None = None) -> dict:
        if responde_a and responde_a in self.caixa:
            n = sum(1 for k in self.caixa if k.startswith(f"{responde_a}-R")) + 1
            eid = f"{responde_a}-R{n}"
        else:
            responde_a = None
            eid = self.novo_id("MSG", 1, 3)
        return self.receber_evento({"de": de, "nome": nome, "assunto": assunto, "corpo": corpo}, responde_a, eid, origem="mundo")

    def evento_manual(self, de: str, nome: str, assunto: str, corpo: str) -> dict:
        return self.receber_evento({"de": de, "nome": nome, "assunto": assunto, "corpo": corpo}, None, self.novo_id("MAN", 1, 3), origem="painel")

    def evento(self, evento_id: Any) -> dict:
        item = self.caixa.get(str(evento_id))
        if not item:
            raise ErroFerramenta(404, f"Evento {evento_id} não encontrado. Veja os ids com listar_eventos.")
        return item

    def evento_opcional(self, evento_id: Any) -> dict | None:
        if evento_id in (None, ""):
            return None
        return self.evento(evento_id)

    @staticmethod
    def publico(item: dict) -> dict:
        return {k: v for k, v in item.items() if not k.startswith("_") and k != "minuto"}

    def proximo_em(self) -> dict | None:
        if not self._chegadas:
            return None
        minuto = self._chegadas[0]
        falta = max(0.0, minuto - self.relogio.minuto())
        return {"hora_simulada": self.relogio.texto(minuto), "em_segundos_reais": round(self.relogio.segundos_reais(falta), 1)}

    def _base_eventos(self) -> Base:
        def atualizar(registro: dict, dados: dict, agente: str) -> dict:
            item = self.caixa[registro["id"]]
            for campo in ("status", "observacao"):
                if campo in dados:
                    item[campo] = texto_limitado(dados[campo], campo, 200 if campo == "status" else LIMITE_TEXTO)
            return self.publico(item)

        return Base(
            "eventos",
            "Tudo o que chegou para o time. O status começa em novo, vira lido quando um agente pega o evento e respondido quando alguém responde; "
            "o time pode gravar o status e a observação que quiser.",
            lambda: [self.publico(i) for i in self.caixa.values()],
            campos=("id", "de", "nome", "assunto", "corpo", "chegou_em", "status", "responde_a", "origem", "acoes", "observacao"),
            atualizar=atualizar,
            campos_atualizaveis=("status", "observacao"),
        )

    def _base_mensagens(self) -> Base:
        return Base(
            "mensagens",
            "Mensagens que o time enviou com enviar_mensagem. Serve para conferir se um envio que deu erro 504 chegou antes de repetir.",
            lambda: self.mensagens,
            campos=("id", "para", "assunto", "mensagem", "agente", "evento_id", "enviada_em"),
        )

    # ---------- relógio ----------
    async def rodar(self) -> None:
        while True:
            await anyio.sleep(0.25)
            if not self.relogio.rodando:
                continue
            agora = self.relogio.minuto()
            while self._agenda and self._agenda[0][0] <= agora:
                _, _, funcao = heapq.heappop(self._agenda)
                try:
                    funcao()
                except Exception:
                    traceback.print_exc()
            try:
                self.tema.ao_avancar()
            except Exception:
                traceback.print_exc()
            if self.relogio.encerrado() and not self._fim_avisado:
                self._fim_avisado = True
                self.emitir("fim", mensagem="O cenário terminou.")

    # ---------- chamadas MCP ----------
    def sortear_falha(self, leitura: bool) -> str | None:
        if self.sorteio.random() >= self.prob_erro:
            return None
        falhas = [(t, p) for t, p in FALHAS if not (leitura and t == "conflito")]
        tipos, pesos = zip(*falhas)
        return self.sorteio.choices(tipos, weights=pesos)[0]

    def marcar_acao(self, evento_id: Any, ferramenta: str, agente: str) -> None:
        item = self.caixa.get(str(evento_id)) if evento_id else None
        if item:
            item["acoes"].append({"ferramenta": ferramenta, "agente": agente, "agora": self.agora()})
            item.setdefault("_primeira_acao", self.relogio.minuto())

    async def _esperar_evento(self, segundos: float) -> None:
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            if any(i["status"] == "novo" for i in self.caixa.values()) or self.relogio.encerrado():
                return
            await anyio.sleep(0.25)

    async def chamar(self, nome: str, argumentos: dict | None) -> types.CallToolResult:
        if self.relogio.iniciar():
            self.emitir("inicio", mensagem="O primeiro agente se conectou. O relógio começou.")
        inicio = time.monotonic()
        args = limpar(dict(argumentos or {})) if isinstance(argumentos, dict) else {}
        agente = str(args.pop("agente", "") or "").strip()[:LIMITE_AGENTE]
        motivo = str(args.pop("motivo", "") or "").strip()[:LIMITE_TEXTO]
        ferramenta = self.ferramentas.get(nome)
        falha: str | None = None
        resultado: Any = None
        erro: tuple[int, str, dict] | None = None

        try:
            if ferramenta is None:
                raise ErroFerramenta(404, f"A ferramenta '{nome}' não existe. Consulte a lista de ferramentas do servidor.")
            if not agente:
                raise ErroFerramenta(400, "Toda chamada precisa do campo 'agente', com o nome de quem está chamando.")
            faltando = [c for c in ferramenta.obrigatorios if args.get(c) in (None, "", [], {})]
            if faltando:
                raise ErroFerramenta(400, "Faltam parâmetros: " + ", ".join(faltando))
            if not ferramenta.leitura and self.relogio.encerrado():
                raise ErroFerramenta(410, "O cenário terminou: o mundo não aceita mais ações. Reinicie o servidor para começar de novo.")

            if nome == "proximo_evento":
                espera = inteiro(args.get("esperar_segundos"), "esperar_segundos", 0, 0, 30)
                if espera:
                    await self._esperar_evento(espera)

            falha = self.sortear_falha(ferramenta.leitura) if ferramenta.falha else None
            if falha == "lento":
                await anyio.sleep(self.sorteio.uniform(2, 5))
            elif falha == "timeout":
                await anyio.sleep(self.sorteio.uniform(5, 9))
                if not ferramenta.leitura and self.sorteio.random() < 0.5:
                    try:
                        ferramenta.funcao(args, agente)
                    except ErroFerramenta:
                        pass
                raise ErroFerramenta(*MENSAGENS_FALHA["timeout"])
            if falha in ("indisponivel", "conflito"):
                raise ErroFerramenta(*MENSAGENS_FALHA[falha])
            resultado = ferramenta.funcao(args, agente)
        except ErroFerramenta as e:
            erro = (e.codigo, e.mensagem, e.extra)
        except Exception as e:  # nunca devolver erro fora do contrato
            traceback.print_exc()
            erro = (500, f"Erro interno do servidor ({type(e).__name__}). Tente de novo e, se repetir, avise a organização.", {})

        self.total_chamadas += 1
        self.total_erros += int(bool(erro))
        self.contar_agente(agente, nome, bool(erro))
        if erro:
            resposta = {"status": "erro", "codigo": erro[0], "mensagem": erro[1], **erro[2], "agora": self.agora()}
        else:
            resposta = {"status": "ok", **(resultado if isinstance(resultado, dict) else {"resultado": resultado}), "agora": self.agora()}

        if nome != "registrar_conversa" or erro:
            self.emitir(
                "chamada",
                agente=agente,
                ferramenta=nome,
                argumentos=args,
                motivo=motivo,
                resultado="erro" if erro else "ok",
                codigo=erro[0] if erro else 200,
                falha=falha,
                via="mcp",
                resposta=resposta,
                duracao_ms=int((time.monotonic() - inicio) * 1000),
            )
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=para_json(resposta))],
            isError=bool(erro),
        )

    def registrar_tela(self, sistema: str, agente: str, dados: dict, resposta: dict, ok: bool) -> None:
        """Registra no log e no painel uma ação feita pela tela do sistema legado (computer use)."""
        if self.relogio.iniciar():
            self.emitir("inicio", mensagem="O primeiro agente se conectou. O relógio começou.")
        agente = agente[:LIMITE_AGENTE]
        self.total_chamadas += 1
        self.total_erros += int(not ok)
        self.contar_agente(agente, f"tela/{sistema}", not ok)
        self.emitir(
            "chamada",
            agente=agente,
            ferramenta=f"tela/{sistema}",
            argumentos=dados,
            resultado="ok" if ok else "erro",
            codigo=200 if ok else 422,
            falha=None,
            via="tela",
            resposta=resposta,
            duracao_ms=0,
        )

    # ---------- ferramentas genéricas ----------
    def base(self, nome: Any) -> Base:
        base = self.bases.get(str(nome))
        if not base:
            raise ErroFerramenta(404, f"A base '{nome}' não existe.", bases=list(self.bases))
        return base

    def registro(self, base: Base, chave: Any) -> dict:
        for r in base.registros():
            if str(r.get(base.chave)) == str(chave):
                return r
        raise ErroFerramenta(404, f"Nenhum registro com {base.chave} = {chave} na base '{base.nome}'.")

    def _ferramentas(self) -> list[Ferramenta]:
        def proximo_evento(args, agente):
            for item in self.caixa.values():
                if item["status"] == "novo":
                    item["status"] = "lido"
                    item["lido_por"] = agente
                    return {"evento": self.publico(item), "encerrado": self.relogio.encerrado()}
            encerrado = self.relogio.encerrado()
            return {
                "evento": None,
                "mensagem": "O cenário terminou." if encerrado else "Nenhum evento novo agora. Espere e pergunte de novo.",
                "encerrado": encerrado,
                "proximo_evento_do_cenario": None if encerrado else self.proximo_em(),
            }

        def listar_eventos(args, agente):
            status = args.get("status")
            itens = [i for i in self.caixa.values() if not status or i["status"] == status]
            limite = inteiro(args.get("limite"), "limite", 50, 1, 200)
            offset = inteiro(args.get("offset"), "offset", 0, 0, 10**6)
            campos = ("id", "de", "assunto", "status", "chegou_em", "responde_a", "origem")
            pagina = [{k: i.get(k) for k in campos} for i in itens[offset : offset + limite]]
            return {"total": len(itens), "offset": offset, "eventos": pagina, "tem_mais": offset + limite < len(itens)}

        def ler_evento(args, agente):
            return {"evento": self.publico(self.evento(args["evento_id"]))}

        def responder_evento(args, agente):
            item = self.evento(args["evento_id"])
            mensagem = texto_limitado(args["mensagem"], "mensagem")
            aguardar = args.get("aguardar_resposta") in VERDADEIROS
            item["status"] = "respondido"
            self.marcar_acao(item["id"], "responder_evento", agente)
            vai_responder = self.tema.ao_responder(item, mensagem, aguardar)
            if aguardar and vai_responder:
                aviso = "Se a pessoa responder, a resposta chega depois como evento novo."
            elif aguardar:
                aviso = "Quem mandou este evento não costuma responder de volta."
            else:
                aviso = ""
            return {"mensagem": f"Resposta enviada para {item['de']}. {aviso}".strip()}

        def enviar_mensagem(args, agente):
            evento = self.evento_opcional(args.get("evento_id"))
            registro = {
                "id": self.novo_id("ENV", 1, 3),
                "para": texto_limitado(args["para"], "para", 200).strip(),
                "assunto": texto_limitado(args.get("assunto"), "assunto", 300),
                "mensagem": texto_limitado(args["mensagem"], "mensagem"),
                "agente": agente,
                "evento_id": evento["id"] if evento else None,
                "enviada_em": self.agora(),
            }
            destino = self.tema.ao_mensagem(registro)
            self.mensagens.append(registro)
            self.marcar_acao(registro["evento_id"], "enviar_mensagem", agente)
            return {"mensagem_id": registro["id"], **destino}

        def listar_bases(args, agente):
            return {"bases": [b.resumo() for b in self.bases.values()]}

        def consultar(args, agente):
            base = self.base(args["base"])
            filtro = args.get("filtro") or {}
            if not isinstance(filtro, dict):
                raise ErroFerramenta(422, "'filtro' precisa ser um objeto {campo: valor}.")
            busca = sem_acento(args.get("busca") or "")
            limite = inteiro(args.get("limite"), "limite", 20, 1, 100)
            offset = inteiro(args.get("offset"), "offset", 0, 0, 10**6)
            achados = []
            for r in base.registros():
                if any(sem_acento(v) not in sem_acento(r.get(k, "")) for k, v in filtro.items()):
                    continue
                if busca and not all(t in sem_acento(json.dumps(r, ensure_ascii=False, default=str)) for t in busca.split()):
                    continue
                achados.append(r)
            pagina = achados[offset : offset + limite]
            resposta = {"base": base.nome, "total": len(achados), "offset": offset, "registros": pagina, "tem_mais": offset + limite < len(achados)}
            if resposta["tem_mais"]:
                resposta["aviso"] = f"Mostrando {len(pagina)} de {len(achados)}. Use offset={offset + len(pagina)} para ver o resto."
            desconhecidos = [k for k in filtro if base.campos and k not in base.campos]
            if desconhecidos:
                resposta["aviso_filtro"] = "Campos que não existem nesta base: " + ", ".join(desconhecidos)
            return resposta

        def registrar(args, agente):
            base = self.base(args["base"])
            if not base.registrar:
                raise ErroFerramenta(405, f"A base '{base.nome}' não aceita registros novos por aqui.")
            dados = args.get("dados") or {}
            if not isinstance(dados, dict):
                raise ErroFerramenta(422, "'dados' precisa ser um objeto.")
            evento = self.evento_opcional(args.get("evento_id") or dados.get("evento_id"))
            if evento:
                dados = dict(dados, evento_id=evento["id"])
            novo = base.registrar(dados, agente)
            usados = set(base.campos_registro) | {"evento_id"} | set(novo) | set(novo.get("campos") or {})
            ignorados = [k for k in dados if base.campos_registro and k not in usados]
            self.marcar_acao(evento["id"] if evento else None, "registrar", agente)
            resposta = {"base": base.nome, "registro": novo}
            if ignorados:
                resposta["campos_ignorados"] = ignorados
            return resposta

        def atualizar(args, agente):
            base = self.base(args["base"])
            if not base.atualizar:
                raise ErroFerramenta(405, f"A base '{base.nome}' não pode ser alterada por aqui.")
            dados = args.get("dados") or {}
            if not isinstance(dados, dict) or not dados:
                raise ErroFerramenta(422, "'dados' precisa ser um objeto com os campos a mudar.")
            proibidos = [c for c in dados if c not in base.campos_atualizaveis]
            if proibidos:
                raise ErroFerramenta(422, "Estes campos não podem ser alterados: " + ", ".join(proibidos), campos=list(base.campos_atualizaveis))
            evento = self.evento_opcional(args.get("evento_id"))
            registro = self.registro(base, args["id"])
            novo = base.atualizar(registro, dados, agente)
            if base.nome != "eventos":  # mexer só no status do evento não conta como ação de atendimento
                self.marcar_acao(evento["id"] if evento else None, "atualizar", agente)
            return {"base": base.nome, "registro": novo}

        def registrar_conversa(args, agente):
            de = str(args.get("de") or agente)[:LIMITE_AGENTE]
            self.emitir("conversa", de=de, para=str(args["para"])[:LIMITE_AGENTE], mensagem=texto_limitado(args["mensagem"], "mensagem"))
            return {"mensagem": "Conversa registrada no painel e no log."}

        ev = {"evento_id": texto("Id do evento relacionado (opcional). Ligar a ação ao evento conta como atendimento dele")}
        paginacao = {
            "limite": numero("Quantos registros devolver"),
            "offset": numero("Quantos pular, para paginar (padrão 0)"),
        }
        return [
            Ferramenta(
                "proximo_evento",
                "Pega o próximo evento novo da caixa de entrada do time e marca como lido. Sem evento novo, devolve evento=null, "
                "encerrado (true quando o cenário acabou) e quando chega o próximo evento do cenário. Use esperar_segundos (até 30) "
                "para o servidor esperar um evento chegar antes de responder. O agente deve chamar em laço até encerrado=true.",
                proximo_evento,
                {"esperar_segundos": numero("Esperar até N segundos (0 a 30) por um evento novo")},
                leitura=True,
            ),
            Ferramenta(
                "listar_eventos",
                "Lista os eventos da caixa de entrada, do mais antigo para o mais novo. Status do sistema: novo, lido, respondido; "
                "o time pode gravar outros com atualizar na base eventos. Devolve total e tem_mais para paginar.",
                listar_eventos,
                {"status": texto("Filtra por status (opcional)"), **{k: dict(v, description=v["description"] + (" (padrão 50, máx. 200)" if k == "limite" else "")) for k, v in paginacao.items()}},
                leitura=True,
            ),
            Ferramenta("ler_evento", "Lê um evento inteiro, com o que já foi feito nele.", ler_evento, {"evento_id": texto("Id do evento")}, ["evento_id"], leitura=True),
            Ferramenta(
                "responder_evento",
                "Responde ao REMETENTE do evento (o campo 'de') e marca o evento como respondido. Para falar com outra pessoa, use enviar_mensagem.",
                responder_evento,
                {
                    "evento_id": texto("Id do evento"),
                    "mensagem": texto("Texto da resposta"),
                    "aguardar_resposta": {"type": "boolean", "description": "true se a resposta pede algo de volta (ex.: uma informação que falta); se a pessoa responder, chega um evento novo"},
                },
                ["evento_id", "mensagem"],
            ),
            Ferramenta(
                "enviar_mensagem",
                "Envia uma mensagem, pelo e-mail, para alguém do mundo: um time, uma pessoa que mandou evento ou alguém das bases do tema. "
                "Só responde quem o tema prevê (veja a resposta); as respostas chegam como eventos novos.",
                enviar_mensagem,
                {"para": texto("E-mail da pessoa ou do time"), "assunto": texto("Assunto da mensagem"), "mensagem": texto("Texto"), **ev},
                ["para", "mensagem"],
            ),
            Ferramenta(
                "listar_bases",
                "Lista as bases de dados do mundo: o que cada uma guarda, a chave, os campos, quais campos registrar e quais podem ser alterados.",
                listar_bases,
                leitura=True,
            ),
            Ferramenta(
                "consultar",
                "Consulta uma base. 'filtro' compara campo a campo (o valor só precisa estar contido, sem diferença de acento); "
                "'busca' exige que todas as palavras apareçam em algum campo. Devolve total e tem_mais para paginar.",
                consultar,
                {
                    "base": texto("Nome da base (veja listar_bases)"),
                    "filtro": objeto("{campo: valor}"),
                    "busca": texto("Palavras (opcional)"),
                    "limite": numero("Quantos registros devolver (padrão 20, máx. 100)"),
                    "offset": paginacao["offset"],
                },
                ["base"],
                leitura=True,
            ),
            Ferramenta(
                "registrar",
                "Cria um registro novo numa base que aceite. Os campos esperados de cada base estão em listar_bases (campos_para_registrar). "
                "O mundo valida as regras do tema e recusa o que estiver errado.",
                registrar,
                {"base": texto("Nome da base"), "dados": objeto("Campos do registro"), **ev},
                ["base", "dados"],
            ),
            Ferramenta(
                "atualizar",
                "Altera campos de um registro existente, achado pela chave da base (veja chave em listar_bases: id, patrimonio etc.). "
                "O mundo valida as regras do tema e recusa o que estiver errado.",
                atualizar,
                {"base": texto("Nome da base"), "id": texto("Valor da chave do registro"), "dados": objeto("Campos a mudar"), **ev},
                ["base", "id", "dados"],
            ),
            Ferramenta(
                "registrar_conversa",
                "Deixa no painel e no log uma conversa entre dois agentes do time. Não entrega nada a ninguém: o time decide como os agentes se falam de verdade.",
                registrar_conversa,
                {"de": texto("Agente que fala (padrão: o próprio agente)"), "para": texto("Agente que recebe"), "mensagem": texto("O que foi dito")},
                ["para", "mensagem"],
                falha=False,
            ),
        ]

    def estado(self) -> dict:
        return limpar({
            "tema": self.tema.titulo,
            "cenario": self.cenario.get("nome", ""),
            "agora": self.agora(),
            "dia": self.relogio.dia(),
            "dias": self.relogio.dias,
            "rodando": self.relogio.rodando,
            "encerrado": self.relogio.encerrado(),
            "progresso": round(self.relogio.minuto() / (self.relogio.dias * MINUTOS_DIA), 4),
            "agentes": self.agentes,
            "chamadas": self.total_chamadas,
            "erros": self.total_erros,
            "legado": self.tema.legado,
            "indicadores": self.tema.indicadores(),
            "caixa": [
                {k: item.get(k) for k in ("id", "de", "nome", "assunto", "corpo", "status", "chegou_em", "responde_a", "origem")}
                | {"acoes": len(item["acoes"])}
                for item in self.caixa.values()
            ],
            "alertas": self.alertas[-100:],
            "historico": list(self.historico)[-200:],
        })


class TemaBase:
    titulo = ""
    segundos_por_dia_padrao = 120
    legado: list[dict] = []  # sistemas só com tela: [{"nome", "caminho", "descricao"}]

    def __init__(self, mundo: Mundo, dados: pathlib.Path, cenario: dict) -> None:
        self.mundo = mundo
        self.dados = dados

    def bases(self) -> list[Base]:
        return []

    def rotas_legado(self) -> list:
        return []

    def deve_chegar(self, p: dict) -> bool:
        """Um tema pode segurar um evento do cenário que já não faz sentido no estado atual."""
        return True

    def ao_receber(self, item: dict) -> None: ...

    def ao_responder(self, item: dict, mensagem: str, aguardar: bool) -> bool:
        """Devolve True se quem mandou o evento vai responder de volta."""
        return False

    def ao_mensagem(self, registro: dict) -> dict:
        """Entrega a mensagem e devolve {"entregue_para": ..., "vai_responder": bool}; ErroFerramenta se o endereço não existe."""
        raise ErroFerramenta(404, f"Ninguém no mundo com o endereço '{registro['para']}'.")

    def ao_avancar(self) -> None: ...

    def indicadores(self) -> list[dict]:
        return []

    def indicadores_caixa(self) -> list[dict]:
        itens = [i for i in self.mundo.caixa.values() if i["origem"] != "mundo"]
        tratados = [i for i in itens if i["acoes"]]
        espera = [(i["_primeira_acao"] - i["minuto"]) for i in itens if i.get("_primeira_acao") is not None]
        media = f"{sum(espera) / len(espera):.0f} min" if espera else "-"
        return [
            {"nome": "Eventos recebidos", "valor": len(itens)},
            {"nome": "Com alguma ação", "valor": len(tratados)},
            {"nome": "Sem nenhuma ação", "valor": len(itens) - len(tratados), "alerta": len(itens) - len(tratados) > 5},
            {"nome": "Tempo até a 1ª ação", "valor": media},
        ]
