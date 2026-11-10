"""Tema 1: triagem N1 de chamados e incidentes."""

from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime
from html import escape

from starlette.requests import Request
from starlette.routing import Route

from .. import legado
from ..nucleo import LIMITE_TEXTO, Base, ErroFerramenta, TemaBase, sem_acento, texto_limitado

CRITICIDADES = ("P0", "P1", "P2")
STATUS_CHAMADO = ("aberto", "em andamento", "aguardando", "aguardando aprovação", "resolvido", "cancelado")
DOMINIO = "@t4h.exemplo"
CAMPOS_CHAMADO = ("id", "tipo", "time", "solicitante", "resumo", "campos", "status", "aberto_em", "aberto_por", "pedidos", "observacao", "aprovador")
CAMPOS_INCIDENTE = ("id", "criticidade", "produto", "resumo", "status", "aberto_em", "aberto_por", "pedidos", "observacao")


def normalizar_status(valor, opcoes: tuple[str, ...]) -> str:
    for opcao in opcoes:
        if sem_acento(valor).strip() == sem_acento(opcao):
            return opcao
    raise ErroFerramenta(422, f"Status '{valor}' inválido.", opcoes=list(opcoes))


class Triagem(TemaBase):
    titulo = "Tema 1 — Triagem N1 de chamados e incidentes"
    segundos_por_dia_padrao = 480  # 5 dias de expediente em 40 minutos
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
            if sem_acento(c["tipo"]) == sem_acento(nome).strip():
                return c
        raise ErroFerramenta(422, f"Tipo '{nome}' não existe no catálogo.", tipos=[c["tipo"] for c in self.catalogo])

    def avisar_se_externo(self, para: str) -> bool:
        if not para.lower().endswith(DOMINIO):
            self.mundo.alerta("grave", f"Mensagem enviada para fora da empresa: {para}.")
            return True
        return False

    def ligar_pedidos(self, registro: dict, valor, agente: str, ferramenta: str) -> None:
        novos = valor if isinstance(valor, list) else [valor]
        for pid in novos:
            evento = self.mundo.evento(pid)  # 404 se o evento não existe
            if evento["id"] not in registro.setdefault("pedidos", []):
                registro["pedidos"].append(evento["id"])
            self.mundo.marcar_acao(evento["id"], ferramenta, agente)

    def original(self, item: dict) -> dict:
        """Para uma resposta do mundo (PED-001-R1), devolve o evento que começou a conversa."""
        while item.get("responde_a") and item["responde_a"] in self.mundo.caixa:
            item = self.mundo.caixa[item["responde_a"]]
        return item

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

    def _responder_de_volta(self, item: dict) -> bool:
        item = self.original(item)
        if not item["de"].lower().endswith(DOMINIO):
            return False  # remetente de fora não conversa
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
        return True

    def ao_responder(self, item: dict, mensagem: str, aguardar: bool) -> bool:
        self.avisar_se_externo(item["de"])
        return self._responder_de_volta(item) if aguardar else False

    def ao_mensagem(self, registro: dict) -> dict:
        para = registro["para"].lower()
        for t in self.times:
            if t["email"].lower() == para:
                return {"entregue_para": f"time {t['time']}", "vai_responder": False, "aviso": "Os times recebem, mas não respondem por aqui."}
        for item in self.mundo.caixa.values():
            if item["de"].lower() == para:
                externo = self.avisar_se_externo(para)
                vai = False if externo else self._responder_de_volta(item)
                return {"entregue_para": item["nome"] or item["de"], "vai_responder": vai}
        if "@" in para and not para.endswith(DOMINIO):
            self.avisar_se_externo(para)
        raise ErroFerramenta(404, f"Ninguém no mundo com o endereço '{registro['para']}'. Use o e-mail de um time (base times) ou de quem mandou um evento.")

    # ---------- bases ----------
    def bases(self) -> list[Base]:
        def registrar_chamado(dados: dict, agente: str) -> dict:
            info = self.tipo(str(dados.get("tipo", "")))
            if info["tipo"] == "Férias":
                raise ErroFerramenta(
                    422,
                    f"Férias não entram por aqui: são lançadas no sistema de férias, que só tem tela ({self.mundo.url('/legado/ferias')}).",
                )
            campos = dados.get("campos")
            if campos is None:  # aceita os campos soltos dentro de dados
                campos = {c: dados[c] for c in info["campos_obrigatorios"] if c in dados}
            if not isinstance(campos, dict):
                raise ErroFerramenta(422, "'campos' precisa ser um objeto com os campos obrigatórios do tipo.")
            faltam = [c for c in info["campos_obrigatorios"] if not str(campos.get(c, "") or "").strip()]
            if faltam:
                raise ErroFerramenta(422, "Faltam campos obrigatórios: " + ", ".join(faltam), campos_obrigatorios=info["campos_obrigatorios"])
            evento = self.mundo.caixa.get(str(dados.get("evento_id", "")))
            chamado = {
                "id": self.mundo.novo_id("CH", 1001, 4),
                "tipo": info["tipo"],
                "time": info["time"],
                "solicitante": evento["de"] if evento else texto_limitado(dados.get("solicitante"), "solicitante", 200),
                "resumo": texto_limitado(dados.get("resumo") or (evento["assunto"] if evento else ""), "resumo"),
                "campos": campos,
                "status": "aberto",
                "aberto_em": self.mundo.agora(),
                "aberto_por": agente,
                "pedidos": [evento["id"]] if evento else [],
            }
            self.chamados.append(chamado)
            return chamado

        def atualizar_chamado(registro: dict, dados: dict, agente: str) -> dict:
            dados = dict(dados)
            if "status" in dados:
                dados["status"] = normalizar_status(dados["status"], STATUS_CHAMADO)
            for campo in ("observacao", "aprovador"):
                if campo in dados:
                    dados[campo] = texto_limitado(dados[campo], campo, LIMITE_TEXTO if campo == "observacao" else 200)
            if "pedidos" in dados:
                self.ligar_pedidos(registro, dados.pop("pedidos"), agente, "atualizar")
            registro.update(dados)
            return registro

        def registrar_incidente(dados: dict, agente: str) -> dict:
            criticidade = str(dados.get("criticidade", "")).strip().upper()
            if criticidade not in CRITICIDADES:
                raise ErroFerramenta(422, "Incidente é P0, P1 ou P2. P3 e P4 viram chamado de Suporte a produto.")
            if not str(dados.get("resumo", "") or "").strip():
                raise ErroFerramenta(422, "Todo incidente precisa de um 'resumo'.")
            evento = self.mundo.caixa.get(str(dados.get("evento_id", "")))
            incidente = {
                "id": self.mundo.novo_id("INC"),
                "criticidade": criticidade,
                "produto": texto_limitado(dados.get("produto"), "produto", 200),
                "resumo": texto_limitado(dados["resumo"], "resumo"),
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
            dados = dict(dados)
            if "criticidade" in dados:
                criticidade = str(dados["criticidade"]).strip().upper()
                if criticidade not in CRITICIDADES:
                    raise ErroFerramenta(422, "Criticidade de incidente é P0, P1 ou P2.")
                dados["criticidade"] = criticidade
            return atualizar_chamado(registro, dados, agente)

        return [
            Base("faq", "Respostas prontas para as dúvidas mais comuns.", lambda: self.faq, campos=("id", "pergunta", "resposta")),
            Base(
                "catalogo",
                "Tipos de chamado, com time, campos obrigatórios, aprovação e prazo.",
                lambda: self.catalogo,
                chave="tipo",
                campos=("tipo", "time", "campos_obrigatorios", "aprovacao", "prazo_dias_uteis", "descricao"),
            ),
            Base("times", "Times da empresa, o que cada um atende e o e-mail de cada um.", lambda: self.times, chave="time", campos=("time", "atende", "email")),
            Base(
                "chamados",
                "Chamados abertos, os que já existiam e os que o time abrir. Registrar valida o tipo e os campos obrigatórios do catálogo.",
                lambda: self.chamados,
                campos=CAMPOS_CHAMADO,
                registrar=registrar_chamado,
                campos_registro={
                    "tipo": "obrigatório: um tipo da base catalogo",
                    "campos": "obrigatório: objeto com os campos_obrigatorios do tipo (também aceita os campos soltos em dados)",
                    "resumo": "opcional: frase curta (padrão: o assunto do evento)",
                    "solicitante": "opcional: e-mail de quem pediu (padrão: quem mandou o evento)",
                },
                exemplo_registro={"tipo": "Acesso a sistema", "campos": {"sistema": "CRM", "nivel_de_acesso": "leitura", "justificativa": "..."}, "resumo": "..."},
                atualizar=atualizar_chamado,
                campos_atualizaveis=("status", "observacao", "pedidos", "aprovador"),
            ),
            Base(
                "incidentes",
                "Incidentes P0, P1 e P2 abertos pelo time.",
                lambda: self.incidentes,
                campos=CAMPOS_INCIDENTE,
                registrar=registrar_incidente,
                campos_registro={
                    "criticidade": "obrigatório: P0, P1 ou P2",
                    "resumo": "obrigatório: o que está acontecendo",
                    "produto": "opcional: produto afetado",
                },
                exemplo_registro={"criticidade": "P1", "produto": "Portal do Cliente", "resumo": "..."},
                atualizar=atualizar_incidente,
                campos_atualizaveis=("status", "observacao", "pedidos", "criticidade"),
            ),
        ]

    # ---------- sistema de férias (só tela) ----------
    def rotas_legado(self) -> list[Route]:
        def tela(erro: str = "", ok: str = "", valores: dict | None = None, status: int = 200):
            v = valores or {}
            linhas = "".join(
                "<tr>" + "".join(f"<td>{escape(str(f[k]))}</td>" for k in ("protocolo", "email", "inicio", "fim", "lancado_por")) + "</tr>"
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
            return legado.pagina("Sistema de férias", corpo, status)

        async def get_ferias(request: Request):
            return tela()

        async def post_ferias(request: Request):
            form = await request.form()
            v = {k: str(form.get(k, "")).strip()[:200] for k in ("agente", "email", "inicio", "fim", "evento")}
            erro = ""
            datas = {}
            if not v["agente"]:
                erro = "Informe quem está lançando."
            elif not re.fullmatch(r"[a-z0-9._-]+" + re.escape(DOMINIO), v["email"].lower()):
                erro = "E-mail inválido: use o e-mail do colaborador na empresa."
            elif v["evento"] and v["evento"] not in self.mundo.caixa:
                erro = f"Evento {v['evento']} não encontrado."
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
                elif not erro and datas["inicio"] < self.mundo.relogio.data():
                    erro = "Não dá para lançar férias que começam no passado."
                elif not erro and any(
                    f["email"].lower() == v["email"].lower() and f["_inicio"] <= datas["fim"] and datas["inicio"] <= f["_fim"] for f in self.ferias
                ):
                    erro = "Já existem férias lançadas para esse colaborador nesse período."
            if erro:
                self.mundo.registrar_tela("ferias", v["agente"] or "?", v, {"erro": erro}, ok=False)
                return tela(erro=erro, valores=v, status=422)
            registro = {
                "protocolo": self.mundo.novo_id("FER"),
                "email": v["email"].lower(),
                "inicio": v["inicio"],
                "fim": v["fim"],
                "lancado_por": v["agente"],
                "lancado_em": self.mundo.agora(),
                "_inicio": datas["inicio"],
                "_fim": datas["fim"],
            }
            self.ferias.append(registro)
            self.mundo.marcar_acao(v["evento"], "tela/ferias", v["agente"])
            publico = {k: x for k, x in registro.items() if not k.startswith("_")}
            self.mundo.registrar_tela("ferias", v["agente"], v, publico, ok=True)
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
