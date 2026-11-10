"""O mundo simulado: relógio, caixa de entrada, falhas, propostas, log e eventos do painel."""

from __future__ import annotations

import heapq
import itertools
import json
import pathlib
import random
import time
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

# Falhas simuladas: (tipo, peso). "lento" responde certo, só que devagar.
FALHAS = [("indisponivel", 4), ("lento", 3), ("timeout", 2), ("conflito", 2)]
MENSAGENS_FALHA = {
    "indisponivel": (503, "Serviço temporariamente indisponível. Tente de novo em alguns segundos."),
    "timeout": (504, "O sistema demorou demais para responder. A ação pode ou não ter sido feita: confira antes de repetir."),
    "conflito": (409, "Outra operação estava em andamento no mesmo registro. Consulte de novo e tente outra vez."),
}


def sem_acento(texto: str) -> str:
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


class ErroFerramenta(Exception):
    """Erro de regra de negócio: o pedido do agente não pode ser atendido como veio."""

    def __init__(self, codigo: int, mensagem: str, **extra: Any) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.extra = extra


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
class Ferramenta:
    nome: str
    descricao: str
    funcao: Callable[[dict, str, str], Any]
    propriedades: dict = field(default_factory=dict)
    obrigatorios: list[str] = field(default_factory=list)
    acao: bool = True  # ações mudam o mundo e exigem "motivo"
    falha: bool = True  # sujeita a falhas simuladas

    def como_tool(self) -> types.Tool:
        props: dict[str, Any] = {"agente": {"type": "string", "description": "Nome do agente do seu time que está chamando"}}
        exigidos = ["agente"]
        if self.acao:
            props["motivo"] = {"type": "string", "description": "Por que o agente está tomando esta ação"}
            exigidos.append("motivo")
        props.update(self.propriedades)
        return types.Tool(
            name=self.nome,
            description=self.descricao,
            inputSchema={"type": "object", "properties": props, "required": exigidos + self.obrigatorios},
        )


def texto(s: str) -> dict:
    return {"type": "string", "description": s}


class Mundo:
    def __init__(self, tema_cls: type, cenario: dict, dados: pathlib.Path, args: Any) -> None:
        self.sorteio = random.Random(args.seed)
        self.prob_erro = max(0.0, min(1.0, args.erros))
        self.cenario = cenario
        self.relogio = Relogio(date.fromisoformat(cenario["inicio"]), int(cenario["dias"]), args.segundos_por_dia)
        self.log = pathlib.Path(args.log)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self._agenda: list[tuple[float, int, Callable[[], None]]] = []
        self._seq = itertools.count()
        self._ids: dict[str, itertools.count] = {}
        self.caixa: dict[str, dict] = {}
        self.propostas: dict[str, dict] = {}
        self.alertas: list[dict] = []
        self.historico: deque[dict] = deque(maxlen=600)
        self.assinantes: set[Any] = set()
        self.agentes: dict[str, int] = {}
        self.total_chamadas = 0
        self.total_erros = 0
        self._fim_avisado = False

        self.tema = tema_cls(self, dados, cenario)
        comuns = ferramentas_comuns(self)
        self.ferramentas: dict[str, Ferramenta] = {f.nome: f for f in comuns + self.tema.ferramentas()}

        for p in cenario["pedidos"]:
            base = Relogio.minuto_de(int(p["dia"]), p["hora"])
            chegada = max(0.0, base + self.sorteio.uniform(-15, 15))
            self.agendar(chegada, lambda p=p: self.receber_pedido(p))

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

    # ---------- eventos ----------
    def emitir(self, tipo: str, **dados: Any) -> dict:
        evento = {"tipo": tipo, "agora": self.agora(), "quando": datetime.now().isoformat(timespec="seconds"), **dados}
        self.historico.append(evento)
        with self.log.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
        for fila in list(self.assinantes):
            try:
                fila.send_nowait(evento)
            except (anyio.WouldBlock, anyio.BrokenResourceError, anyio.ClosedResourceError):
                self.assinantes.discard(fila)
        return evento

    def alerta(self, nivel: str, mensagem: str, **dados: Any) -> None:
        item = {"nivel": nivel, "mensagem": mensagem, "agora": self.agora(), **dados}
        self.alertas.append(item)
        self.emitir("alerta", **item)

    # ---------- caixa de entrada ----------
    def receber_pedido(self, p: dict, responde_a: str | None = None, pedido_id: str | None = None) -> dict:
        pid = pedido_id or p["id"]
        item = {
            "id": pid,
            "de": p["de"],
            "nome": p.get("nome", ""),
            "assunto": p["assunto"],
            "corpo": p["corpo"],
            "chegou_em": self.agora(),
            "minuto": self.relogio.minuto(),
            "status": "novo",
            "responde_a": responde_a,
            "acoes": [],
            "_original": p,
        }
        self.caixa[pid] = item
        self.emitir("pedido", id=pid, de=item["de"], nome=item["nome"], assunto=item["assunto"], responde_a=responde_a)
        self.tema.ao_receber(item)
        return item

    def mensagem(self, de: str, nome: str, assunto: str, corpo: str, responde_a: str | None = None) -> dict:
        if responde_a:
            n = sum(1 for k in self.caixa if k.startswith(f"{responde_a}-R")) + 1
            pid = f"{responde_a}-R{n}"
        else:
            pid = self.novo_id("MSG", 1, 3)
        return self.receber_pedido({"de": de, "nome": nome, "assunto": assunto, "corpo": corpo}, responde_a, pid)

    def pedido(self, pedido_id: str) -> dict:
        item = self.caixa.get(str(pedido_id))
        if not item:
            raise ErroFerramenta(404, f"Pedido {pedido_id} não encontrado na caixa de entrada.")
        return item

    @staticmethod
    def publico(item: dict) -> dict:
        return {k: v for k, v in item.items() if not k.startswith("_") and k != "minuto"}

    # ---------- propostas ----------
    def decidir_proposta(self, proposta: dict) -> None:
        aprovada, comentario = self.tema.avaliar_proposta(proposta)
        proposta["status"] = "aprovada" if aprovada else "recusada"
        proposta["comentario"] = comentario
        proposta["decidida_em"] = self.agora()
        self.emitir("proposta", **proposta)
        self.mensagem(
            "gestao@t4h.exemplo",
            "Gestão",
            f"Proposta {proposta['id']} {proposta['status']}",
            f"A proposta {proposta['id']} ({proposta['acao']} em {proposta['alvo']}) foi {proposta['status']}. {comentario}",
            responde_a=proposta.get("pedido_id"),
        )

    def exigir_proposta(self, proposta_id: str | None, acao: str, alvo: str) -> dict:
        proposta = self.propostas.get(str(proposta_id or ""))
        if not proposta or proposta["acao"] != acao or str(proposta["alvo"]) != str(alvo):
            raise ErroFerramenta(
                403,
                f"Esta ação precisa de uma proposta aprovada (propor com acao='{acao}' e alvo='{alvo}').",
            )
        if proposta["status"] != "aprovada":
            raise ErroFerramenta(403, f"A proposta {proposta['id']} está {proposta['status']}.")
        if proposta.get("usada"):
            raise ErroFerramenta(409, f"A proposta {proposta['id']} já foi usada.")
        proposta["usada"] = True
        return proposta

    # ---------- relógio ----------
    async def rodar(self) -> None:
        while True:
            await anyio.sleep(0.25)
            if not self.relogio.rodando:
                continue
            agora = self.relogio.minuto()
            while self._agenda and self._agenda[0][0] <= agora:
                _, _, funcao = heapq.heappop(self._agenda)
                funcao()
            self.tema.ao_avancar()
            if self.relogio.encerrado() and not self._fim_avisado:
                self._fim_avisado = True
                self.emitir("fim", mensagem="O cenário terminou.")

    # ---------- chamadas MCP ----------
    def sortear_falha(self) -> str | None:
        if self.sorteio.random() >= self.prob_erro:
            return None
        tipos, pesos = zip(*FALHAS)
        return self.sorteio.choices(tipos, weights=pesos)[0]

    async def chamar(self, nome: str, argumentos: dict | None) -> types.CallToolResult:
        if self.relogio.iniciar():
            self.emitir("inicio", mensagem="O primeiro agente se conectou. O relógio começou.")
        inicio = time.monotonic()
        args = dict(argumentos or {})
        agente = str(args.pop("agente", "") or "").strip()
        motivo = str(args.pop("motivo", "") or "").strip()
        ferramenta = self.ferramentas.get(nome)
        falha: str | None = None
        resultado: Any = None
        erro: tuple[int, str, dict] | None = None

        try:
            if ferramenta is None:
                raise ErroFerramenta(404, f"A ferramenta '{nome}' não existe. Consulte a lista de ferramentas do servidor.")
            if not agente:
                raise ErroFerramenta(400, "Toda chamada precisa do campo 'agente'.")
            if ferramenta.acao and not motivo:
                raise ErroFerramenta(400, "Esta ação precisa do campo 'motivo'.")
            faltando = [c for c in ferramenta.obrigatorios if args.get(c) in (None, "", [], {})]
            if faltando:
                raise ErroFerramenta(400, "Faltam parâmetros: " + ", ".join(faltando))
            if self.relogio.encerrado() and ferramenta.acao:
                raise ErroFerramenta(410, "O cenário já terminou. Nenhuma ação é aceita.")

            falha = self.sortear_falha() if ferramenta.falha else None
            if falha == "lento":
                await anyio.sleep(self.sorteio.uniform(2, 5))
            elif falha == "timeout":
                await anyio.sleep(self.sorteio.uniform(5, 9))
                if self.sorteio.random() < 0.5:
                    try:
                        ferramenta.funcao(args, agente, motivo)
                    except ErroFerramenta:
                        pass
                raise ErroFerramenta(*MENSAGENS_FALHA["timeout"])
            if falha in ("indisponivel", "conflito"):
                raise ErroFerramenta(*MENSAGENS_FALHA[falha])
            resultado = ferramenta.funcao(args, agente, motivo)
        except ErroFerramenta as e:
            erro = (e.codigo, e.mensagem, e.extra)

        self.total_chamadas += 1
        self.agentes[agente or "?"] = self.agentes.get(agente or "?", 0) + 1
        pedido_id = args.get("pedido_id")
        if erro is None and ferramenta and ferramenta.acao and pedido_id in self.caixa:
            item = self.caixa[pedido_id]
            item["acoes"].append({"ferramenta": nome, "agente": agente, "agora": self.agora()})
            item.setdefault("_primeira_acao", self.relogio.minuto())
        if erro:
            self.total_erros += 1
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
                resposta=resposta,
                duracao_ms=int((time.monotonic() - inicio) * 1000),
            )
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(resposta, ensure_ascii=False))],
            isError=bool(erro),
        )

    def estado(self) -> dict:
        return {
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
            "indicadores": self.tema.indicadores(),
            "caixa": [
                {k: item[k] for k in ("id", "de", "nome", "assunto", "corpo", "status", "chegou_em", "responde_a")}
                | {"acoes": len(item["acoes"])}
                for item in self.caixa.values()
            ],
            "alertas": self.alertas[-100:],
            "historico": list(self.historico)[-200:],
        }


def ferramentas_comuns(mundo: Mundo) -> list[Ferramenta]:
    def proximo_pedido(args: dict, agente: str, motivo: str) -> dict:
        for item in mundo.caixa.values():
            if item["status"] == "novo":
                item["status"] = "lido"
                item["lido_por"] = agente
                return {"pedido": mundo.publico(item)}
        return {
            "pedido": None,
            "mensagem": "Nenhum pedido novo agora." if not mundo.relogio.encerrado() else "O cenário terminou.",
            "encerrado": mundo.relogio.encerrado(),
        }

    def listar_pedidos(args: dict, agente: str, motivo: str) -> dict:
        status = args.get("status")
        itens = [i for i in mundo.caixa.values() if not status or i["status"] == status]
        return {
            "pedidos": [
                {k: i[k] for k in ("id", "de", "assunto", "status", "chegou_em", "responde_a")} for i in itens
            ][-50:]
        }

    def ler_pedido(args: dict, agente: str, motivo: str) -> dict:
        return {"pedido": mundo.publico(mundo.pedido(args["pedido_id"]))}

    def responder_pedido(args: dict, agente: str, motivo: str) -> dict:
        item = mundo.pedido(args["pedido_id"])
        item["status"] = "respondido"
        mundo.tema.ao_responder(item, str(args["mensagem"]))
        return {"mensagem": f"Resposta enviada para {item['de']}."}

    def escalar(args: dict, agente: str, motivo: str) -> dict:
        pid = args.get("pedido_id")
        if pid:
            item = mundo.pedido(pid)
            item["status"] = "escalado"
        protocolo = mundo.novo_id("ESC")
        mundo.alerta("info", f"{agente} escalou para uma pessoa: {args['resumo']}", pedido_id=pid, protocolo=protocolo)
        return {"protocolo": protocolo, "mensagem": "Uma pessoa do time vai assumir o caso."}

    def propor(args: dict, agente: str, motivo: str) -> dict:
        proposta = {
            "id": mundo.novo_id("PROP"),
            "acao": str(args["acao"]),
            "alvo": str(args["alvo"]),
            "detalhes": args.get("detalhes", ""),
            "pedido_id": args.get("pedido_id"),
            "agente": agente,
            "motivo": motivo,
            "status": "pendente",
            "criada_em": mundo.agora(),
        }
        mundo.propostas[proposta["id"]] = proposta
        mundo.emitir("proposta", **proposta)
        mundo.agendar_em_horas(mundo.sorteio.uniform(1, 3), lambda: mundo.decidir_proposta(proposta))
        return {
            "proposta_id": proposta["id"],
            "mensagem": "Proposta registrada. A decisão chega na caixa de entrada em algumas horas.",
        }

    def consultar_proposta(args: dict, agente: str, motivo: str) -> dict:
        proposta = mundo.propostas.get(str(args["proposta_id"]))
        if not proposta:
            raise ErroFerramenta(404, f"Proposta {args['proposta_id']} não encontrada.")
        return {"proposta": proposta}

    def registrar_conversa(args: dict, agente: str, motivo: str) -> dict:
        mundo.emitir("conversa", de=str(args["de"]), para=str(args["para"]), mensagem=str(args["mensagem"]))
        return {"mensagem": "Conversa registrada."}

    return [
        Ferramenta("proximo_pedido", "Pega o próximo pedido novo da caixa de entrada e marca como lido.", proximo_pedido, acao=False),
        Ferramenta(
            "listar_pedidos",
            "Lista os pedidos da caixa de entrada. Status possíveis: novo, lido, respondido, escalado e os do tema.",
            listar_pedidos,
            {"status": texto("Filtra por status (opcional)")},
            acao=False,
        ),
        Ferramenta("ler_pedido", "Lê um pedido inteiro, com o histórico de ações.", ler_pedido, {"pedido_id": texto("Id do pedido")}, ["pedido_id"], acao=False),
        Ferramenta(
            "responder_pedido",
            "Responde a quem fez o pedido.",
            responder_pedido,
            {"pedido_id": texto("Id do pedido"), "mensagem": texto("Texto da resposta")},
            ["pedido_id", "mensagem"],
        ),
        Ferramenta(
            "escalar",
            "Passa um caso para uma pessoa do time, com um resumo pronto.",
            escalar,
            {"pedido_id": texto("Id do pedido (opcional)"), "resumo": texto("Resumo para a pessoa que vai assumir")},
            ["resumo"],
        ),
        Ferramenta(
            "propor",
            "Registra uma proposta para uma pessoa aprovar. A decisão chega depois na caixa de entrada. Ações que precisam de OK exigem o id de uma proposta aprovada.",
            propor,
            {
                "acao": texto("O que você quer fazer, por exemplo cancelar_chamado ou abrir_compra"),
                "alvo": texto("Em quê: id do chamado, patrimônio, tipo de item etc."),
                "detalhes": texto("Detalhes e justificativa para quem vai decidir"),
                "pedido_id": texto("Pedido relacionado (opcional)"),
            },
            ["acao", "alvo"],
        ),
        Ferramenta("consultar_proposta", "Mostra o status de uma proposta.", consultar_proposta, {"proposta_id": texto("Id da proposta")}, ["proposta_id"], acao=False),
        Ferramenta(
            "registrar_conversa",
            "Registra uma mensagem entre dois agentes do time, para aparecer no painel e no log.",
            registrar_conversa,
            {"de": texto("Agente que fala"), "para": texto("Agente que recebe"), "mensagem": texto("O que foi dito")},
            ["de", "para", "mensagem"],
            acao=False,
            falha=False,
        ),
    ]


class TemaBase:
    titulo = ""
    segundos_por_dia_padrao = 120

    def __init__(self, mundo: Mundo, dados: pathlib.Path, cenario: dict) -> None:
        self.mundo = mundo
        self.dados = dados

    def ferramentas(self) -> list[Ferramenta]:
        return []

    def ao_receber(self, item: dict) -> None: ...

    def ao_responder(self, item: dict, mensagem: str) -> None: ...

    def ao_avancar(self) -> None: ...

    def avaliar_proposta(self, proposta: dict) -> tuple[bool, str]:
        if self.mundo.sorteio.random() < 0.8:
            return True, "Pode seguir."
        return False, "Agora não. Traga mais detalhes."

    def indicadores(self) -> list[dict]:
        return []

    def indicadores_caixa(self) -> list[dict]:
        itens = [i for i in self.mundo.caixa.values() if not i["id"].startswith("MSG")]
        tratados = [i for i in itens if i["acoes"]]
        espera = [
            (i["_primeira_acao"] - i["minuto"]) for i in itens if i.get("_primeira_acao") is not None
        ]
        media = f"{sum(espera) / len(espera):.0f} min" if espera else "-"
        return [
            {"nome": "Pedidos recebidos", "valor": len(itens)},
            {"nome": "Com alguma ação", "valor": len(tratados)},
            {"nome": "Sem nenhuma ação", "valor": len(itens) - len(tratados), "alerta": len(itens) - len(tratados) > 5},
            {"nome": "Tempo até a 1ª ação", "valor": media},
        ]
