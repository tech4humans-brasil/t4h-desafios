"""Tema 3: gestão de equipamentos."""

from __future__ import annotations

import csv
import json
import pathlib
from datetime import date
from html import escape

from starlette.requests import Request
from starlette.routing import Route

from .. import legado
from ..nucleo import Base, ErroFerramenta, TemaBase, sem_acento, somar_dias_uteis

USAVEIS = ("novo", "usado")
SITUACOES = ("novo", "usado", "quebrado", "danificado", "perdido")
STATUS = ("disponível", "reservado", "alocado", "uso interno", "baixado")
CAMPOS_INVENTARIO = ("status", "situacao", "com_quem", "desde", "numero_serie", "marca", "modelo", "observacao")
PALAVRAS_DEVOLUCAO = ("devolv", "deixei", "entreguei", "larguei", "trouxe")
PALAVRAS_COBRANCA = ("devol", "equipamento", "notebook", "monitor", "headset", "kit", "eq-")
DOMINIO = "@t4h.exemplo"


class Equipamentos(TemaBase):
    titulo = "Tema 3 — Gestão de equipamentos"
    segundos_por_dia_padrao = 60  # 22 dias de expediente em 22 minutos
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
        self.devolvidos: set[str] = set()
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
        raise ErroFerramenta(409, f"Mais de um colaborador para '{busca}'. Use o id.", opcoes=[(c["id"], c["nome"]) for c in achados])

    def itens_de(self, cid: str) -> list[dict]:
        return [i for i in self.itens.values() if i["com_quem"] == cid and i["status"] in ("reservado", "alocado")]

    def kit_de(self, colaborador: dict) -> list[str]:
        return self.regras["kit_padrao"] + self.regras["kit_extra_por_area"].get(colaborador["area"], [])

    def hoje(self) -> str:
        return self.mundo.relogio.data().isoformat()

    def voltou_fisicamente(self, patrimonio: str) -> bool:
        if patrimonio in self.devolvidos:
            return True
        return any(
            patrimonio in p["corpo"] and any(x in sem_acento(p["corpo"]) for x in PALAVRAS_DEVOLUCAO) for p in self.mundo.caixa.values()
        )

    # ---------- reações do mundo ----------
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
                    if somar_dias_uteis(saida, limite) == hoje:
                        pendentes = [i["patrimonio"] for i in self.itens_de(c["id"])]
                        if pendentes:
                            self.mundo.alerta(nivel, f"{c['nome']} saiu há {limite} dias úteis e ainda está com {', '.join(pendentes)}.")

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

    def _responder_cobranca(self, c: dict) -> None:
        patrimonios = [i["patrimonio"] for i in self.itens_de(c["id"])]
        if not patrimonios:
            corpo = "Oi! Não estou com nenhum equipamento da empresa."
        elif c.get("data_saida") and date.fromisoformat(c["data_saida"]) <= self.mundo.relogio.data():
            if self.mundo.sorteio.random() < 0.7:
                self.devolvidos.update(patrimonios)
                corpo = f"Oi! Deixei hoje na recepção: {', '.join(patrimonios)}."
            else:
                corpo = "Oi, ainda não consegui passar aí. Levo na semana que vem, pode ser?"
        else:
            corpo = "Oi? Eu ainda trabalho aqui e uso esse equipamento todo dia. Por que preciso devolver?"
        self.mundo.mensagem_do_mundo(c["email"], c["nome"], "RE: equipamento", corpo)

    def ao_mensagem(self, registro: dict) -> str | None:
        para = registro["para"].lower()
        if not para.endswith(DOMINIO):
            if "@" in para:
                self.mundo.alerta("grave", f"Mensagem enviada para fora da empresa: {para}.")
                return para
            return None
        pessoa = next((c for c in self.colaboradores.values() if c["email"].lower() == para), None)
        if not pessoa:
            return para
        texto = sem_acento(registro["assunto"] + " " + registro["mensagem"])
        if any(p in texto for p in PALAVRAS_COBRANCA):
            self.mundo.agendar_em_horas(self.mundo.sorteio.uniform(4, 20), lambda: self._responder_cobranca(pessoa))
        return f"{pessoa['nome']} ({pessoa['id']})"

    # ---------- bases ----------
    def bases(self) -> list[Base]:
        def atualizar_item(item: dict, dados: dict, agente: str) -> dict:
            novo_status = dados.get("status", item["status"])
            nova_situacao = dados.get("situacao", item["situacao"])
            if novo_status not in STATUS:
                raise ErroFerramenta(422, "Status inválido.", opcoes=list(STATUS))
            if nova_situacao not in SITUACOES:
                raise ErroFerramenta(422, "Situação inválida.", opcoes=list(SITUACOES))
            com_quem = dados.get("com_quem", item["com_quem"])
            if novo_status in ("reservado", "alocado"):
                if not com_quem:
                    raise ErroFerramenta(422, f"Para deixar o item {novo_status}, informe 'com_quem' (id do colaborador).")
                pessoa = self.colaborador(str(com_quem))
                livre = item["status"] == "disponível" or (item["status"] in ("reservado", "alocado") and item["com_quem"] == pessoa["id"])
                if not livre:
                    raise ErroFerramenta(409, f"{item['patrimonio']} está {item['status']}" + (f" com {item['com_quem']}." if item["com_quem"] else "."))
                if nova_situacao not in USAVEIS:
                    raise ErroFerramenta(422, f"{item['patrimonio']} está {nova_situacao} e não pode ser entregue.")
                dados = dict(dados, com_quem=pessoa["id"], desde=dados.get("desde") or self.hoje())
            elif "com_quem" in dados and dados["com_quem"] and item["status"] in ("reservado", "alocado") and dados["com_quem"] != item["com_quem"]:
                raise ErroFerramenta(409, f"{item['patrimonio']} está com {item['com_quem']}. Registre a devolução antes de passar para outra pessoa.")
            if item["status"] == "alocado" and novo_status in ("disponível", "uso interno") and not self.voltou_fisicamente(item["patrimonio"]):
                raise ErroFerramenta(409, f"{item['patrimonio']} ainda não voltou fisicamente. Fale com a pessoa antes de registrar a devolução.")
            if novo_status in ("disponível", "uso interno", "baixado"):
                dados = dict(dados, com_quem="", desde="")
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
                atualizar=atualizar_item,
                campos_atualizaveis=CAMPOS_INVENTARIO,
            ),
            Base("colaboradores", "Pessoas da empresa, com área, cargo, e-mail, data de entrada e data de saída.", lambda: list(self.colaboradores.values())),
            Base("catalogo_compra", "Preço e prazo de entrega de cada tipo de item no fornecedor.", lambda: self.catalogo, chave="tipo"),
            Base("regras", "Regras de kit, prazos, devolução, empréstimo, limite de compra e estoque mínimo.", lambda: regras, chave="regra"),
            Base(
                "compras",
                f"Pedidos feitos ao fornecedor. Compras novas só pelo portal do fornecedor, que tem só tela ({self.mundo.url('/legado/fornecedor')}).",
                lambda: self.compras,
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
                f"<tr><td>{p['id']}</td><td>{p['quantidade']} × {escape(p['tipo'])}</td><td>R$ {p['valor']}</td><td>{p['previsao']}</td><td>{p['status']}</td><td>{escape(p['pedido_por'])}</td></tr>"
                for p in self.compras[-15:]
            ) or "<tr><td colspan='6'>Nenhum pedido ainda.</td></tr>"
            return f"<h3>Seus pedidos</h3><table><tr><th>Pedido</th><th>Itens</th><th>Total</th><th>Entrega</th><th>Status</th><th>Feito por</th></tr>{linhas}</table>"

        def inicio(erro: str = "", ok: str = "", valores: dict | None = None):
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
            return legado.pagina("Portal do fornecedor", corpo)

        async def get_inicio(request: Request):
            return inicio()

        async def revisar(request: Request):
            form = await request.form()
            v = {k: str(form.get(k, "")).strip() for k in ("agente", "tipo", "quantidade", "evento")}
            item = next((c for c in self.catalogo if c["tipo"] == v["tipo"]), None)
            erro = ""
            if not v["agente"]:
                erro = "Informe quem está comprando."
            elif not item:
                erro = "Escolha um item do catálogo."
            elif not v["quantidade"].isdigit() or not 1 <= int(v["quantidade"]) <= 10:
                erro = "Quantidade precisa ser de 1 a 10."
            if erro:
                self.mundo.registrar_tela("fornecedor", v["agente"], v, {"erro": erro}, ok=False)
                return inicio(erro=erro, valores=v)
            qtd = int(v["quantidade"])
            total = item["preco"] * qtd
            prazo = somar_dias_uteis(self.mundo.relogio.data(), int(item["prazo_dias_uteis"]))
            ocultos = "".join(f"<input type='hidden' name='{k}' value='{escape(val)}'>" for k, val in v.items())
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
            v = {k: str(form.get(k, "")).strip() for k in ("agente", "tipo", "quantidade", "evento")}
            item = next((c for c in self.catalogo if c["tipo"] == v["tipo"]), None)
            if not (v["agente"] and item and v["quantidade"].isdigit() and 1 <= int(v["quantidade"]) <= 10):
                self.mundo.registrar_tela("fornecedor", v["agente"], v, {"erro": "pedido inválido"}, ok=False)
                return inicio(erro="Pedido inválido. Comece de novo.")
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
