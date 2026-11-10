"""Tema 1: triagem N1 de chamados e incidentes."""

from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime

from starlette.requests import Request
from starlette.routing import Route

from .. import legado
from ..nucleo import Base, ErroFerramenta, TemaBase, sem_acento

CRITICIDADES = ("P0", "P1", "P2")
STATUS_CHAMADO = ("aberto", "em andamento", "aguardando", "resolvido", "cancelado")
DOMINIO = "@t4h.exemplo"


class Triagem(TemaBase):
    titulo = "Tema 1 — Triagem N1 de chamados e incidentes"
    segundos_por_dia_padrao = 240  # 5 dias de expediente em 20 minutos
    legado = [{"nome": "Sistema de férias", "caminho": "/legado/ferias", "descricao": "Lançamento de férias. Só tela, sem API."}]

    def __init__(self, mundo, dados: pathlib.Path, cenario: dict) -> None:
        super().__init__(mundo, dados, cenario)
        ler = lambda nome: json.loads((dados / nome).read_text(encoding="utf-8"))
        self.catalogo = ler("catalogo.json")
        self.times = ler("times.json")
        self.faq = ler("faq.json")
        self.chamados = [dict(c, pedidos=[]) for c in ler("chamados_abertos.json")]
        self.incidentes: list[dict] = []
        self.ferias: list[dict] = []
        self.cobrancas = 0

    # ---------- apoio ----------
    def tipo(self, nome: str) -> dict:
        for c in self.catalogo:
            if sem_acento(c["tipo"]) == sem_acento(nome):
                return c
        raise ErroFerramenta(422, f"Tipo '{nome}' não existe no catálogo.", tipos=[c["tipo"] for c in self.catalogo])

    def avisar_se_externo(self, para: str) -> None:
        if not para.lower().endswith(DOMINIO):
            self.mundo.alerta("grave", f"Mensagem enviada para fora da empresa: {para}.")

    # ---------- reações do mundo ----------
    def ao_receber(self, item: dict) -> None:
        cobranca = item["_original"].get("cobranca")
        if cobranca:
            self.mundo.agendar_em_horas(float(cobranca["apos_horas"]), lambda: self._cobrar(item, cobranca))

    def _cobrar(self, item: dict, cobranca: dict) -> None:
        if item["acoes"]:
            return
        self.cobrancas += 1
        self.mundo.mensagem_do_mundo(item["de"], item["nome"], cobranca["assunto"], cobranca["corpo"], responde_a=item["id"])
        self.mundo.alerta("atencao", f"{item['id']} ficou sem ação e {item['nome'] or item['de']} cobrou.")

    def _responder_de_volta(self, item: dict) -> None:
        complemento = item["_original"].get("complemento")
        if complemento and not item.get("_complemento_agendado"):
            item["_complemento_agendado"] = True
            corpo = complemento["corpo"]
            horas = float(complemento["apos_horas"])
        else:
            corpo = "Oi! Acho que já mandei tudo no primeiro e-mail. O que exatamente você precisa?"
            horas = self.mundo.sorteio.uniform(0.5, 2)
        self.mundo.agendar_em_horas(
            horas, lambda: self.mundo.mensagem_do_mundo(item["de"], item["nome"], "RE: " + item["assunto"], corpo, responde_a=item["id"])
        )

    def ao_responder(self, item: dict, mensagem: str, aguardar: bool) -> None:
        self.avisar_se_externo(item["de"])
        if aguardar and item["origem"] != "mundo":
            self._responder_de_volta(item)

    def ao_mensagem(self, registro: dict) -> str | None:
        para = registro["para"].lower()
        if "@" not in para:
            return None
        self.avisar_se_externo(para)
        for t in self.times:
            if t["email"] == para:
                return f"time {t['time']}"
        for item in self.mundo.caixa.values():
            if item["de"].lower() == para:
                if item["origem"] != "mundo":
                    self._responder_de_volta(item)
                return item["nome"] or item["de"]
        return para

    # ---------- bases ----------
    def bases(self) -> list[Base]:
        def registrar_chamado(dados: dict, agente: str) -> dict:
            info = self.tipo(str(dados.get("tipo", "")))
            if info["tipo"] == "Férias":
                raise ErroFerramenta(
                    422,
                    f"Férias não entram por aqui: são lançadas no sistema de férias, que só tem tela ({self.mundo.url('/legado/ferias')}).",
                )
            campos = dados.get("campos") or {}
            if not isinstance(campos, dict):
                raise ErroFerramenta(422, "'campos' precisa ser um objeto com os campos obrigatórios do tipo.")
            faltam = [c for c in info["campos_obrigatorios"] if not str(campos.get(c, "")).strip()]
            if faltam:
                raise ErroFerramenta(422, "Faltam campos obrigatórios: " + ", ".join(faltam), campos_obrigatorios=info["campos_obrigatorios"])
            evento = self.mundo.caixa.get(str(dados.get("evento_id", "")))
            chamado = {
                "id": self.mundo.novo_id("CH", 1001, 4),
                "tipo": info["tipo"],
                "time": info["time"],
                "solicitante": evento["de"] if evento else str(dados.get("solicitante", "")),
                "resumo": str(dados.get("resumo") or (evento["assunto"] if evento else "")),
                "campos": campos,
                "status": "aberto",
                "aberto_em": self.mundo.agora(),
                "aberto_por": agente,
                "pedidos": [evento["id"]] if evento else [],
            }
            self.chamados.append(chamado)
            return chamado

        def atualizar_chamado(registro: dict, dados: dict, agente: str) -> dict:
            if "status" in dados and dados["status"] not in STATUS_CHAMADO:
                raise ErroFerramenta(422, "Status inválido.", opcoes=list(STATUS_CHAMADO))
            for k, v in dados.items():
                if k == "pedidos":
                    novos = v if isinstance(v, list) else [v]
                    registro.setdefault("pedidos", []).extend(str(x) for x in novos if str(x) not in registro["pedidos"])
                else:
                    registro[k] = v
            return registro

        def registrar_incidente(dados: dict, agente: str) -> dict:
            criticidade = str(dados.get("criticidade", "")).upper()
            if criticidade not in CRITICIDADES:
                raise ErroFerramenta(422, "Incidente é P0, P1 ou P2. P3 e P4 viram chamado de Suporte a produto.")
            if not str(dados.get("resumo", "")).strip():
                raise ErroFerramenta(422, "Todo incidente precisa de um 'resumo'.")
            evento = self.mundo.caixa.get(str(dados.get("evento_id", "")))
            incidente = {
                "id": self.mundo.novo_id("INC"),
                "criticidade": criticidade,
                "produto": str(dados.get("produto", "")),
                "resumo": str(dados["resumo"]),
                "status": "aberto",
                "aberto_em": self.mundo.agora(),
                "aberto_por": agente,
                "pedidos": [evento["id"]] if evento else [],
            }
            self.incidentes.append(incidente)
            nivel = "atencao" if criticidade in ("P0", "P1") else "info"
            self.mundo.alerta(nivel, f"{incidente['id']} {criticidade} aberto por {agente}: {incidente['resumo']}")
            return incidente

        def atualizar_incidente(registro: dict, dados: dict, agente: str) -> dict:
            if "criticidade" in dados:
                criticidade = str(dados["criticidade"]).upper()
                if criticidade not in CRITICIDADES:
                    raise ErroFerramenta(422, "Criticidade de incidente é P0, P1 ou P2.")
                dados = dict(dados, criticidade=criticidade)
            return atualizar_chamado(registro, dados, agente)

        return [
            Base("faq", "Respostas prontas para as dúvidas mais comuns.", lambda: self.faq),
            Base("catalogo", "Tipos de chamado, com time, campos obrigatórios, aprovação e prazo.", lambda: self.catalogo, chave="tipo"),
            Base("times", "Times da empresa, o que cada um atende e o e-mail de cada um.", lambda: self.times, chave="time"),
            Base(
                "chamados",
                "Chamados abertos, os que já existiam e os que o time abrir. Registrar valida o tipo e os campos obrigatórios.",
                lambda: self.chamados,
                registrar=registrar_chamado,
                atualizar=atualizar_chamado,
                campos_atualizaveis=("status", "observacao", "pedidos", "aprovador"),
            ),
            Base(
                "incidentes",
                "Incidentes P0, P1 e P2 abertos pelo time.",
                lambda: self.incidentes,
                registrar=registrar_incidente,
                atualizar=atualizar_incidente,
                campos_atualizaveis=("status", "observacao", "pedidos", "criticidade"),
            ),
        ]

    # ---------- sistema de férias (só tela) ----------
    def rotas_legado(self) -> list[Route]:
        def tela(erro: str = "", ok: str = "", valores: dict | None = None):
            v = valores or {}
            linhas = "".join(
                f"<tr><td>{f['protocolo']}</td><td>{f['email']}</td><td>{f['inicio']}</td><td>{f['fim']}</td><td>{f['lancado_por']}</td></tr>"
                for f in self.ferias[-15:]
            ) or "<tr><td colspan='5'>Nenhum lançamento ainda.</td></tr>"
            corpo = (
                legado.mensagem(erro, "erro")
                + legado.mensagem(ok, "ok")
                + "<p>Preencha todos os campos. Datas no formato DD/MM/AAAA.</p>"
                + "<form method='post' action='/legado/ferias'>"
                + legado.campo("agente", "Quem está lançando (nome do agente)", v.get("agente", ""))
                + legado.campo("email", "E-mail do colaborador", v.get("email", ""))
                + legado.campo("inicio", "Primeiro dia de férias (DD/MM/AAAA)", v.get("inicio", ""))
                + legado.campo("fim", "Último dia de férias (DD/MM/AAAA)", v.get("fim", ""))
                + legado.campo("evento", "Evento relacionado (opcional)", v.get("evento", ""))
                + "<br><button type='submit'>Lançar férias</button></form>"
                + f"<h3>Últimos lançamentos</h3><table><tr><th>Protocolo</th><th>Colaborador</th><th>Início</th><th>Fim</th><th>Lançado por</th></tr>{linhas}</table>"
                + "<div class='rodape'>SisFérias v2.3 · sistema antigo, sem integração</div>"
            )
            return legado.pagina("Sistema de férias", corpo)

        async def get_ferias(request: Request):
            return tela()

        async def post_ferias(request: Request):
            form = await request.form()
            v = {k: str(form.get(k, "")).strip() for k in ("agente", "email", "inicio", "fim", "evento")}
            erro = ""
            datas = {}
            if not v["agente"]:
                erro = "Informe quem está lançando."
            elif not v["email"].lower().endswith(DOMINIO):
                erro = "E-mail inválido: use o e-mail do colaborador na empresa."
            else:
                for k in ("inicio", "fim"):
                    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", v[k]):
                        erro = "Data fora do formato DD/MM/AAAA."
                        break
                    try:
                        datas[k] = datetime.strptime(v[k], "%d/%m/%Y").date()
                    except ValueError:
                        erro = "Data inexistente."
                        break
                if not erro and datas["fim"] < datas["inicio"]:
                    erro = "O último dia não pode ser antes do primeiro."
            if erro:
                self.mundo.registrar_tela("ferias", v["agente"], v, {"erro": erro}, ok=False)
                return tela(erro=erro, valores=v)
            registro = {
                "protocolo": self.mundo.novo_id("FER"),
                "email": v["email"],
                "inicio": v["inicio"],
                "fim": v["fim"],
                "lancado_por": v["agente"],
                "lancado_em": self.mundo.agora(),
            }
            self.ferias.append(registro)
            self.mundo.marcar_acao(v["evento"], "tela/ferias", v["agente"])
            self.mundo.registrar_tela("ferias", v["agente"], v, registro, ok=True)
            return tela(ok=f"Férias lançadas. Protocolo {registro['protocolo']}.")

        return [Route("/legado/ferias", get_ferias, methods=["GET"]), Route("/legado/ferias", post_ferias, methods=["POST"])]

    def indicadores(self) -> list[dict]:
        novos = [c for c in self.chamados if c.get("aberto_por")]
        return self.indicadores_caixa() + [
            {"nome": "Chamados abertos", "valor": len(novos)},
            {"nome": "Incidentes", "valor": len(self.incidentes)},
            {"nome": "Férias pela tela", "valor": len(self.ferias)},
            {"nome": "Cobranças recebidas", "valor": self.cobrancas, "alerta": self.cobrancas > 0},
        ]
