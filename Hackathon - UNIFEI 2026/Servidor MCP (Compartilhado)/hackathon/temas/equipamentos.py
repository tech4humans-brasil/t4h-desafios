"""Tema 3: gestão de equipamentos."""

from __future__ import annotations

import csv
import json
import pathlib
import re
import secrets
from datetime import date
from html import escape

from starlette.requests import Request
from starlette.routing import Route

from .. import legado
from ..nucleo import LIMITE_TEXTO, Base, ErroFerramenta, TemaBase, sem_acento, somar_dias_uteis, texto_limitado

USAVEIS = ("novo", "usado")
SITUACOES = ("novo", "usado", "quebrado", "danificado", "perdido")
STATUS = ("disponível", "reservado", "alocado", "uso interno", "baixado")
CAMPOS_INVENTARIO = ("status", "situacao", "com_quem", "desde", "numero_serie", "marca", "modelo", "observacao")
SAIDA_SEM_VOLTA = ("perdido", "quebrado", "danificado")  # alocado só vira baixado nessas situações
DOMINIO = "@t4h.exemplo"
CAMPOS_ITEM = ("patrimonio", "tipo", "marca", "modelo", "numero_serie", "status", "situacao", "com_quem", "desde", "observacao")


def normalizar(valor, opcoes: tuple[str, ...], nome: str) -> str:
    for opcao in opcoes:
        if sem_acento(valor).strip() == sem_acento(opcao):
            return opcao
    raise ErroFerramenta(422, f"{nome} '{valor}' inválido.", opcoes=list(opcoes))


class Equipamentos(TemaBase):
    titulo = "Tema 3 — Gestão de equipamentos"
    segundos_por_dia_padrao = 55  # 22 dias de expediente em uns 20 minutos
    legado = [{"nome": "Portal do fornecedor", "caminho": "/legado/fornecedor", "descricao": "Compra de equipamentos. Só tela, sem API."}]

    def __init__(self, mundo, dados: pathlib.Path, cenario: dict) -> None:
        super().__init__(mundo, dados, cenario)
        with (dados / "inventario.csv").open(encoding="utf-8") as f:
            self.itens = {linha["patrimonio"]: linha for linha in csv.DictReader(f)}
        with (dados / "colaboradores.csv").open(encoding="utf-8") as f:
            self.colaboradores = {linha["id"]: linha for linha in csv.DictReader(f)}
        self.catalogo = json.loads((dados / "catalogo_compra.json").read_text(encoding="utf-8"))
        self.regras = json.loads((dados / "regras.json").read_text(encoding="utf-8"))
        self.compras: list[dict] = []
        self.devolvidos: set[str] = set()  # patrimônios que já voltaram fisicamente
        self.a_devolver: dict[tuple[str, str], int] = {}  # (colaborador, tipo) -> quantos voltaram sem patrimônio dito
        self.tokens: dict[str, dict] = {}  # revisões do portal ainda não confirmadas
        self.dia_visto = 0
        self.entradas = {"completas": 0, "incompletas": 0}
        maior = max(int(p.split("-")[1]) for p in self.itens) if self.itens else 0
        self.proximo_patrimonio = maior + 1

    # ---------- apoio ----------
    def colaborador(self, busca: str) -> dict:
        if busca in self.colaboradores:
            return self.colaboradores[busca]
        alvo = sem_acento(busca)
        achados = [c for c in self.colaboradores.values() if alvo == sem_acento(c["email"]) or alvo in sem_acento(c["nome"])]
        if len(achados) == 1:
            return achados[0]
        if not achados:
            raise ErroFerramenta(404, f"Colaborador '{busca}' não encontrado.")
        raise ErroFerramenta(422, f"Mais de um colaborador para '{busca}'. Use o id.", opcoes=[(c["id"], c["nome"]) for c in achados])

    def itens_de(self, cid: str) -> list[dict]:
        return [i for i in self.itens.values() if i["com_quem"] == cid and i["status"] in ("reservado", "alocado")]

    def kit_de(self, colaborador: dict) -> list[str]:
        return self.regras["kit_padrao"] + self.regras["kit_extra_por_area"].get(colaborador["area"], [])

    def hoje(self) -> str:
        return self.mundo.relogio.data().isoformat()

    def saiu(self, c: dict) -> bool:
        return bool(c.get("data_saida")) and date.fromisoformat(c["data_saida"]) <= self.mundo.relogio.data()

    def voltou_fisicamente(self, item: dict) -> bool:
        if item["patrimonio"] in self.devolvidos:
            return True
        chave = (item["com_quem"], item["tipo"])
        if self.a_devolver.get(chave, 0) > 0:
            self.a_devolver[chave] -= 1
            self.devolvidos.add(item["patrimonio"])
            return True
        return False

    # ---------- reações do mundo ----------
    def ao_receber(self, item: dict) -> None:
        # Só os eventos do cenário dizem o que voltou de verdade; evento do painel não devolve nada.
        devolve = item["_original"].get("devolve") if item["origem"] == "cenario" else None
        if not devolve:
            return
        self.devolvidos.update(devolve.get("patrimonios", []))
        if devolve.get("colaborador"):
            chave = (devolve["colaborador"], devolve["tipo"])
            self.a_devolver[chave] = self.a_devolver.get(chave, 0) + int(devolve.get("quantidade", 1))

    def ao_avancar(self) -> None:
        dia = self.mundo.relogio.dia()
        if dia == self.dia_visto:
            return
        self.dia_visto = dia
        hoje = self.mundo.relogio.data(dia)
        for c in self.colaboradores.values():
            if c["data_entrada"] == hoje.isoformat():
                self._primeiro_dia(c)
            if c.get("data_saida"):
                saida = date.fromisoformat(c["data_saida"])
                if saida < self.mundo.relogio.inicio:
                    continue  # quem saiu antes do cenário não gera aviso: achar isso é trabalho do agente
                for limite, nivel in ((self.regras["devolucao_dias_uteis"], "atencao"), (self.regras["escalar_devolucao_dias_uteis"], "grave")):
                    if somar_dias_uteis(saida, limite + 1) == hoje:  # o prazo vence no fim do dia 'limite'
                        pendentes = [i["patrimonio"] for i in self.itens_de(c["id"])]
                        if pendentes:
                            self.mundo.alerta(nivel, f"{c['nome']} passou do prazo de {limite} dias úteis para devolver e ainda está com {', '.join(pendentes)}.")

    def _primeiro_dia(self, c: dict) -> None:
        tem = {i["tipo"] for i in self.itens_de(c["id"])}
        faltam = [t for t in self.kit_de(c) if t not in tem]
        for i in self.itens_de(c["id"]):
            if i["status"] == "reservado":
                i["status"], i["desde"] = "alocado", self.hoje()
        if faltam:
            self.entradas["incompletas"] += 1
            self.mundo.alerta("grave" if "notebook" in faltam else "atencao", f"{c['nome']} começou hoje sem: {', '.join(faltam)}.")
        else:
            self.entradas["completas"] += 1
            self.mundo.emitir("mundo", mensagem=f"{c['nome']} começou hoje com o kit completo.")

    def _chegar_compra(self, compra: dict) -> None:
        novos = []
        for _ in range(compra["quantidade"]):
            patrimonio = f"EQ-{self.proximo_patrimonio:04d}"
            self.proximo_patrimonio += 1
            self.itens[patrimonio] = {
                "patrimonio": patrimonio,
                "tipo": compra["tipo"],
                "marca": compra["modelo"].split()[0],
                "modelo": compra["modelo"],
                "numero_serie": f"SN{self.mundo.sorteio.randrange(10**7, 10**8)}",
                "status": "disponível",
                "situacao": "novo",
                "com_quem": "",
                "desde": "",
            }
            novos.append(patrimonio)
        compra["status"] = "entregue"
        compra["patrimonios"] = novos
        self.mundo.mensagem_do_mundo(
            "entregas@fornecedor.exemplo",
            "Fornecedor",
            f"Entrega do pedido {compra['id']}",
            f"Entregamos {compra['quantidade']} × {compra['tipo']} ({compra['modelo']}). Patrimônios: {', '.join(novos)}.",
            responde_a=compra.get("evento_id") or None,
        )

    def _responder_cobranca(self, c: dict, registro: dict) -> None:
        patrimonios = [i["patrimonio"] for i in self.itens_de(c["id"])]
        if not patrimonios:
            corpo = "Oi! Não estou com nenhum equipamento da empresa."
        elif self.saiu(c):
            if self.mundo.sorteio.random() < 0.7:
                self.devolvidos.update(patrimonios)
                corpo = f"Oi! Deixei hoje na recepção: {', '.join(patrimonios)}."
            else:
                corpo = "Oi, ainda não consegui passar aí. Levo na semana que vem, pode ser?"
        else:
            corpo = "Oi? Eu ainda trabalho aqui e uso esse equipamento todo dia. Por que preciso devolver?"
        assunto = "RE: " + (registro["assunto"] or "equipamento")
        self.mundo.mensagem_do_mundo(c["email"], c["nome"], assunto, corpo, responde_a=registro.get("evento_id"))

    def ao_mensagem(self, registro: dict) -> dict:
        para = registro["para"].lower()
        if "@" in para and not para.endswith(DOMINIO):
            self.mundo.alerta("grave", f"Mensagem enviada para fora da empresa: {para}.")
        pessoa = next((c for c in self.colaboradores.values() if c["email"].lower() == para), None)
        if pessoa:
            # Só quem recebe um pedido de devolução responde; ninguém responde a pedido de aprovação.
            texto = sem_acento(registro["assunto"] + " " + registro["mensagem"])
            vai = "devol" in texto
            if vai:
                self.mundo.agendar_em_horas(self.mundo.sorteio.uniform(4, 20), lambda: self._responder_cobranca(pessoa, registro))
            return {"entregue_para": f"{pessoa['nome']} ({pessoa['id']})", "vai_responder": vai}
        remetente = next((i for i in self.mundo.caixa.values() if i["de"].lower() == para), None)
        if remetente:
            return {"entregue_para": remetente["nome"] or remetente["de"], "vai_responder": False}
        raise ErroFerramenta(404, f"Ninguém no mundo com o endereço '{registro['para']}'. Use o e-mail de alguém da base colaboradores ou de quem mandou um evento.")

    # ---------- bases ----------
    def bases(self) -> list[Base]:
        def atualizar_item(item: dict, dados: dict, agente: str) -> dict:
            dados = dict(dados)
            if "status" in dados:
                dados["status"] = normalizar(dados["status"], STATUS, "Status")
            if "situacao" in dados:
                dados["situacao"] = normalizar(dados["situacao"], SITUACOES, "Situação")
            if "observacao" in dados:
                dados["observacao"] = texto_limitado(dados["observacao"], "observacao", LIMITE_TEXTO)
            atual = item["status"]
            novo_status = dados.get("status", atual)
            nova_situacao = dados.get("situacao", item["situacao"])
            if atual == "baixado" and (novo_status != "baixado" or "com_quem" in dados):
                raise ErroFerramenta(409, f"{item['patrimonio']} já foi baixado. Baixa é definitiva.")
            com_quem = dados.get("com_quem", item["com_quem"])
            if novo_status in ("reservado", "alocado"):
                if not com_quem:
                    raise ErroFerramenta(422, f"Para deixar o item {novo_status}, informe 'com_quem' (id do colaborador).")
                pessoa = self.colaborador(str(com_quem))
                mesmo_dono = atual in ("reservado", "alocado") and item["com_quem"] == pessoa["id"]
                if not (mesmo_dono or atual in ("disponível", "uso interno")):
                    raise ErroFerramenta(409, f"{item['patrimonio']} está {atual}" + (f" com {item['com_quem']}." if item["com_quem"] else "."))
                if not mesmo_dono:
                    if self.saiu(pessoa):
                        raise ErroFerramenta(422, f"{pessoa['nome']} já saiu da empresa ({pessoa['data_saida']}).")
                    if nova_situacao not in USAVEIS:
                        raise ErroFerramenta(422, f"{item['patrimonio']} está {nova_situacao} e não pode ser entregue.")
                dados.update(com_quem=pessoa["id"], desde=dados.get("desde") or (item["desde"] if mesmo_dono else "") or self.hoje())
                if not mesmo_dono:
                    self.devolvidos.discard(item["patrimonio"])  # a devolução anterior já foi usada
            elif dados.get("com_quem") and atual in ("reservado", "alocado") and dados["com_quem"] != item["com_quem"]:
                raise ErroFerramenta(409, f"{item['patrimonio']} está com {item['com_quem']}. Registre a devolução antes de passar para outra pessoa.")
            if atual == "alocado" and novo_status == "baixado" and nova_situacao not in SAIDA_SEM_VOLTA:
                raise ErroFerramenta(422, f"Item alocado só é baixado direto se estiver {', '.join(SAIDA_SEM_VOLTA)}. Senão, registre a devolução antes.")
            if atual == "alocado" and novo_status in ("disponível", "uso interno") and not self.voltou_fisicamente(item):
                raise ErroFerramenta(409, f"{item['patrimonio']} ainda não voltou fisicamente. Fale com a pessoa antes de registrar a devolução.")
            if novo_status in ("disponível", "uso interno") or (novo_status == "baixado" and atual != "alocado"):
                dados.update(com_quem="", desde="")
            # item alocado baixado direto (perdido, quebrado, danificado) guarda com quem estava, para o registro
            for campo, valor in dados.items():
                item[campo] = str(valor)
            return item

        regras = [{"regra": k, "valor": v} for k, v in self.regras.items()]
        return [
            Base(
                "inventario",
                "Todos os equipamentos: tipo, marca, modelo, série, status, situação e com quem está. Atualizar valida reserva, entrega e devolução.",
                lambda: list(self.itens.values()),
                chave="patrimonio",
                campos=CAMPOS_ITEM,
                atualizar=atualizar_item,
                campos_atualizaveis=CAMPOS_INVENTARIO,
            ),
            Base(
                "colaboradores",
                "Pessoas da empresa, com área, cargo, e-mail, data de entrada e data de saída.",
                lambda: list(self.colaboradores.values()),
                campos=tuple(next(iter(self.colaboradores.values())).keys()) if self.colaboradores else (),
            ),
            Base(
                "catalogo_compra",
                "Preço e prazo de entrega de cada tipo de item no fornecedor.",
                lambda: self.catalogo,
                chave="tipo",
                campos=tuple(self.catalogo[0].keys()) if self.catalogo else (),
            ),
            Base("regras", "Regras de kit, prazos, devolução, empréstimo, limite de compra e estoque mínimo.", lambda: regras, chave="regra", campos=("regra", "valor")),
            Base(
                "compras",
                f"Pedidos feitos ao fornecedor. Compras novas só pelo portal do fornecedor, que tem só tela ({self.mundo.url('/legado/fornecedor')}).",
                lambda: self.compras,
                campos=("id", "tipo", "modelo", "quantidade", "valor", "previsao", "status", "pedido_por", "evento_id", "pedido_em", "patrimonios"),
            ),
        ]

    # ---------- portal do fornecedor (só tela) ----------
    def rotas_legado(self) -> list[Route]:
        def catalogo_html() -> str:
            real = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            linhas = "".join(
                f"<tr><td>{escape(c['tipo'])}</td><td>{escape(c['modelo'])}</td><td>{real(c['preco'])}</td><td>{c['prazo_dias_uteis']} dias úteis</td></tr>"
                for c in self.catalogo
            )
            return f"<table><tr><th>Item</th><th>Modelo</th><th>Preço</th><th>Entrega</th></tr>{linhas}</table>"

        def pedidos_html() -> str:
            linhas = "".join(
                f"<tr><td>{escape(p['id'])}</td><td>{p['quantidade']} × {escape(p['tipo'])}</td><td>R$ {p['valor']}</td><td>{escape(p['previsao'])}</td><td>{escape(p['status'])}</td><td>{escape(p['pedido_por'])}</td></tr>"
                for p in self.compras[-15:]
            ) or "<tr><td colspan='6'>Nenhum pedido ainda.</td></tr>"
            return f"<h3>Seus pedidos</h3><table><tr><th>Pedido</th><th>Itens</th><th>Total</th><th>Entrega</th><th>Status</th><th>Feito por</th></tr>{linhas}</table>"

        def inicio(erro: str = "", ok: str = "", valores: dict | None = None, status: int = 200):
            v = valores or {}
            opcoes = "".join(f"<option value='{escape(c['tipo'])}'>{escape(c['tipo'])}</option>" for c in self.catalogo)
            corpo = (
                legado.mensagem(erro, "erro")
                + legado.mensagem(ok, "ok")
                + catalogo_html()
                + "<form method='post' action='/legado/fornecedor/revisar'>"
                + legado.campo("agente", "Quem está comprando (nome do agente)", v.get("agente", ""))
                + f"<label for='tipo'>Item</label><select id='tipo' name='tipo'>{opcoes}</select>"
                + legado.campo("quantidade", "Quantidade (1 a 10)", v.get("quantidade", "1"), "number", "min='1' max='10'")
                + legado.campo("evento", "Evento relacionado (opcional)", v.get("evento", ""))
                + "<br><button type='submit'>Revisar pedido</button></form>"
                + pedidos_html()
                + f"<div class='rodape'>Regra da empresa: compras acima de R$ {self.regras['limite_compra_sem_aprovacao']} precisam de aprovação. Portal Fornecedor 1.4</div>"
            )
            return legado.pagina("Portal do fornecedor", corpo, status)

        def validar(v: dict) -> tuple[dict | None, str]:
            item = next((c for c in self.catalogo if c["tipo"] == v["tipo"]), None)
            if not v["agente"]:
                return item, "Informe quem está comprando."
            if not item:
                return item, "Escolha um item do catálogo."
            if not re.fullmatch(r"[0-9]{1,2}", v["quantidade"]) or not 1 <= int(v["quantidade"]) <= 10:
                return item, "Quantidade precisa ser de 1 a 10."
            if v["evento"] and v["evento"] not in self.mundo.caixa:
                return item, f"Evento {v['evento']} não encontrado."
            return item, ""

        def ler(form) -> dict:
            return {k: str(form.get(k, "")).strip()[:200] for k in ("agente", "tipo", "quantidade", "evento")}

        async def get_inicio(request: Request):
            return inicio()

        async def revisar(request: Request):
            v = ler(await request.form())
            item, erro = validar(v)
            if erro:
                self.mundo.registrar_tela("fornecedor", v["agente"] or "?", v, {"erro": erro}, ok=False)
                return inicio(erro=erro, valores=v, status=422)
            qtd = int(v["quantidade"])
            total = item["preco"] * qtd
            prazo = somar_dias_uteis(self.mundo.relogio.data(), int(item["prazo_dias_uteis"]))
            token = secrets.token_hex(8)
            self.tokens[token] = v
            ocultos = f"<input type='hidden' name='token' value='{token}'>"
            corpo = (
                "<p>Confira o pedido antes de confirmar.</p>"
                f"<table><tr><th>Item</th><td>{qtd} × {escape(item['tipo'])} ({escape(item['modelo'])})</td></tr>"
                f"<tr><th>Total</th><td>R$ {total}</td></tr><tr><th>Entrega prevista</th><td>{prazo.strftime('%d/%m/%Y')}</td></tr></table>"
                f"<form method='post' action='/legado/fornecedor/confirmar'>{ocultos}<button type='submit'>Confirmar pedido</button></form>"
                "<p><a href='/legado/fornecedor'>Voltar</a></p>"
            )
            return legado.pagina("Portal do fornecedor — revisão", corpo)

        async def confirmar(request: Request):
            form = await request.form()
            v = self.tokens.pop(str(form.get("token", "")), None)
            if v is None:
                self.mundo.registrar_tela("fornecedor", "?", {"token": str(form.get("token", ""))[:40]}, {"erro": "revisão inválida ou já confirmada"}, ok=False)
                return inicio(erro="Esse pedido já foi confirmado ou a revisão não é válida. Comece de novo.", status=409)
            item, erro = validar(v)
            if erro:
                self.mundo.registrar_tela("fornecedor", v["agente"] or "?", v, {"erro": erro}, ok=False)
                return inicio(erro=erro, valores=v, status=422)
            qtd = int(v["quantidade"])
            chega = somar_dias_uteis(self.mundo.relogio.data(), int(item["prazo_dias_uteis"]))
            compra = {
                "id": self.mundo.novo_id("FORN", 1, 4),
                "tipo": item["tipo"],
                "modelo": item["modelo"],
                "quantidade": qtd,
                "valor": item["preco"] * qtd,
                "previsao": chega.isoformat(),
                "status": "a caminho",
                "pedido_por": v["agente"],
                "evento_id": v["evento"],
                "pedido_em": self.mundo.agora(),
            }
            self.compras.append(compra)
            self.mundo.agendar(self.mundo.relogio.minuto_da_data(chega, "09:00"), lambda: self._chegar_compra(compra))
            self.mundo.marcar_acao(v["evento"], "tela/fornecedor", v["agente"])
            self.mundo.registrar_tela("fornecedor", v["agente"], v, compra, ok=True)
            limite = self.regras["limite_compra_sem_aprovacao"]
            if compra["valor"] > limite:
                self.mundo.alerta("info", f"Compra {compra['id']} de R$ {compra['valor']} passa do limite de R$ {limite}: confira se houve aprovação.")
            return inicio(ok=f"Pedido {compra['id']} confirmado. Entrega prevista em {chega.strftime('%d/%m/%Y')}.")

        return [
            Route("/legado/fornecedor", get_inicio, methods=["GET"]),
            Route("/legado/fornecedor/revisar", revisar, methods=["POST"]),
            Route("/legado/fornecedor/confirmar", confirmar, methods=["POST"]),
        ]

    def indicadores(self) -> list[dict]:
        livres: dict[str, int] = {}
        for i in self.itens.values():
            if i["status"] == "disponível" and i["situacao"] in USAVEIS:
                livres[i["tipo"]] = livres.get(i["tipo"], 0) + 1
        minimo = self.regras["estoque_minimo"]
        estoque = [
            {"nome": f"Livres: {t}", "valor": livres.get(t, 0), "alerta": livres.get(t, 0) < minimo}
            for t in ("notebook", "monitor", "headset", "kit teclado e mouse")
        ]
        gasto = sum(c["valor"] for c in self.compras)
        total_entradas = self.entradas["completas"] + self.entradas["incompletas"]
        return self.indicadores_caixa() + estoque + [
            {"nome": "Entradas com kit completo", "valor": f"{self.entradas['completas']} de {total_entradas}", "alerta": self.entradas["incompletas"] > 0},
            {"nome": "Compras pela tela", "valor": f"{len(self.compras)} (R$ {gasto:,.0f})".replace(",", ".")},
        ]
