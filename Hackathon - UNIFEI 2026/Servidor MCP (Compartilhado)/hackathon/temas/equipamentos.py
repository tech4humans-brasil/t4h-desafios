"""Tema 3: gestão de equipamentos."""

from __future__ import annotations

import csv
import json
import pathlib
from datetime import date

from ..nucleo import ErroFerramenta, Ferramenta, TemaBase, sem_acento, somar_dias_uteis, texto

USAVEIS = ("novo", "usado")
SITUACOES = ("novo", "usado", "quebrado", "danificado", "perdido")
CAMPOS_CORRIGIVEIS = ("marca", "modelo", "numero_serie", "status", "situacao", "com_quem", "desde")
PALAVRAS_DEVOLUCAO = ("devolv", "deixei", "entreguei", "larguei", "trouxe")


class Equipamentos(TemaBase):
    titulo = "Tema 3 — Gestão de equipamentos"
    segundos_por_dia_padrao = 60  # 22 dias de expediente em 22 minutos

    def __init__(self, mundo, dados: pathlib.Path, cenario: dict) -> None:
        super().__init__(mundo, dados, cenario)
        with (dados / "inventario.csv").open(encoding="utf-8") as f:
            self.itens = {linha["patrimonio"]: linha for linha in csv.DictReader(f)}
        with (dados / "colaboradores.csv").open(encoding="utf-8") as f:
            self.colaboradores = {linha["id"]: linha for linha in csv.DictReader(f)}
        self.catalogo = {c["tipo"]: c for c in json.loads((dados / "catalogo_compra.json").read_text(encoding="utf-8"))}
        self.regras = json.loads((dados / "regras.json").read_text(encoding="utf-8"))
        self.compras: dict[str, dict] = {}
        self.devolvidos: set[str] = set()
        self.cobrados: set[str] = set()
        self.dia_visto = 0
        self.entradas = {"completas": 0, "incompletas": 0}
        maior = max(int(p.split("-")[1]) for p in self.itens) if self.itens else 0
        self.proximo_patrimonio = maior + 1

    # ---------- apoio ----------
    def item(self, patrimonio: str) -> dict:
        item = self.itens.get(str(patrimonio))
        if not item:
            raise ErroFerramenta(404, f"Patrimônio {patrimonio} não encontrado.")
        return item

    def colaborador(self, busca: str) -> dict:
        if busca in self.colaboradores:
            return self.colaboradores[busca]
        alvo = sem_acento(busca)
        achados = [c for c in self.colaboradores.values() if alvo in sem_acento(c["nome"]) or alvo == sem_acento(c["email"])]
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
            nivel = "grave" if "notebook" in faltam else "atencao"
            self.mundo.alerta(nivel, f"{c['nome']} começou hoje sem: {', '.join(faltam)}.")
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
        self.mundo.mensagem(
            "compras@fornecedor.exemplo",
            "Fornecedor",
            f"Entrega da compra {compra['id']}",
            f"Entregamos {compra['quantidade']} × {compra['tipo']} ({compra['modelo']}). Patrimônios: {', '.join(novos)}.",
            responde_a=compra.get("pedido_id"),
        )

    def _responder_cobranca(self, c: dict, patrimonios: list[str]) -> None:
        if c.get("data_saida") and date.fromisoformat(c["data_saida"]) <= self.mundo.relogio.data():
            if self.mundo.sorteio.random() < 0.7:
                self.devolvidos.update(patrimonios)
                corpo = f"Oi! Deixei hoje na recepção: {', '.join(patrimonios)}."
            else:
                corpo = "Oi, ainda não consegui passar aí. Levo na semana que vem, pode ser?"
        else:
            corpo = "Oi? Eu ainda trabalho aqui e uso esse equipamento todo dia. Por que preciso devolver?"
        self.mundo.mensagem(c["email"], c["nome"], "RE: devolução de equipamento", corpo)

    def avaliar_proposta(self, proposta: dict) -> tuple[bool, str]:
        chance = {"abrir_compra": 0.9, "corrigir_inventario": 0.9, "baixar": 0.85}.get(proposta["acao"], 0.7)
        if self.mundo.sorteio.random() < chance:
            return True, "Pode seguir."
        return False, "Não aprovado. Veja se há outra saída com o que temos no estoque."

    # ---------- ferramentas ----------
    def ferramentas(self) -> list[Ferramenta]:
        m = self.mundo

        def consultar_estoque(args, agente, motivo):
            tipo = args.get("tipo")
            livres = [i for i in self.itens.values() if i["status"] == "disponível" and i["situacao"] in USAVEIS and (not tipo or i["tipo"] == tipo)]
            contagem: dict[str, int] = {}
            for i in livres:
                contagem[i["tipo"]] = contagem.get(i["tipo"], 0) + 1
            return {"disponiveis_por_tipo": contagem, "itens": [i["patrimonio"] for i in livres][:30]}

        def buscar_itens(args, agente, motivo):
            filtros = {k: str(v) for k, v in args.items() if k in ("patrimonio", "tipo", "status", "situacao", "com_quem", "numero_serie", "marca") and v}
            achados = [i for i in self.itens.values() if all(sem_acento(v) in sem_acento(i.get(k, "")) for k, v in filtros.items())]
            return {"total": len(achados), "itens": achados[:40]}

        def consultar_colaborador(args, agente, motivo):
            c = self.colaborador(str(args["busca"]))
            return {"colaborador": c, "kit_esperado": self.kit_de(c), "itens_com_a_pessoa": self.itens_de(c["id"])}

        def consultar_catalogo_compra(args, agente, motivo):
            return {"itens": list(self.catalogo.values())}

        def consultar_regras(args, agente, motivo):
            return {"regras": self.regras}

        def reservar(args, agente, motivo):
            item = self.item(args["patrimonio"])
            c = self.colaborador(str(args["para"]))
            if item["status"] != "disponível":
                raise ErroFerramenta(409, f"{item['patrimonio']} está {item['status']}" + (f" com {item['com_quem']}." if item["com_quem"] else "."))
            if item["situacao"] not in USAVEIS:
                raise ErroFerramenta(422, f"{item['patrimonio']} está {item['situacao']} e não pode ser entregue.")
            item.update(status="reservado", com_quem=c["id"], desde=self.hoje())
            return {"item": item}

        def alocar(args, agente, motivo):
            item = self.item(args["patrimonio"])
            c = self.colaborador(str(args["para"]))
            if not (item["status"] == "disponível" or (item["status"] == "reservado" and item["com_quem"] == c["id"])):
                raise ErroFerramenta(409, f"{item['patrimonio']} está {item['status']}" + (f" com {item['com_quem']}." if item["com_quem"] else "."))
            if item["situacao"] not in USAVEIS:
                raise ErroFerramenta(422, f"{item['patrimonio']} está {item['situacao']} e não pode ser entregue.")
            item.update(status="alocado", com_quem=c["id"], desde=self.hoje())
            return {"item": item}

        def registrar_devolucao(args, agente, motivo):
            item = self.item(args["patrimonio"])
            situacao = str(args["situacao"])
            if situacao not in SITUACOES:
                raise ErroFerramenta(422, "Situação inválida.", opcoes=list(SITUACOES))
            if item["status"] not in ("alocado", "reservado"):
                raise ErroFerramenta(409, f"{item['patrimonio']} não está com ninguém (status {item['status']}).")
            citado = any(
                item["patrimonio"] in p["corpo"] and any(x in sem_acento(p["corpo"]) for x in PALAVRAS_DEVOLUCAO) for p in m.caixa.values()
            )
            if item["status"] == "alocado" and item["patrimonio"] not in self.devolvidos and not citado:
                raise ErroFerramenta(409, f"{item['patrimonio']} ainda não voltou fisicamente. Cobre a pessoa antes de registrar.")
            item.update(status="disponível" if situacao in USAVEIS else "disponível", situacao=situacao, com_quem="", desde="")
            return {"item": item}

        def cobrar_devolucao(args, agente, motivo):
            c = self.colaborador(str(args["colaborador"]))
            patrimonios = [args["patrimonio"]] if args.get("patrimonio") else [i["patrimonio"] for i in self.itens_de(c["id"])]
            if not patrimonios:
                raise ErroFerramenta(422, f"{c['nome']} não está com nenhum item.")
            self.cobrados.update(patrimonios)
            m.agendar_em_horas(m.sorteio.uniform(4, 20), lambda: self._responder_cobranca(c, patrimonios))
            return {"mensagem": f"Cobrança enviada para {c['email']}.", "patrimonios": patrimonios}

        def abrir_compra(args, agente, motivo):
            tipo = args["tipo"]
            if tipo not in self.catalogo:
                raise ErroFerramenta(422, f"'{tipo}' não está no catálogo de compra.", tipos=list(self.catalogo))
            quantidade = int(args.get("quantidade") or 1)
            if quantidade < 1:
                raise ErroFerramenta(422, "Quantidade precisa ser 1 ou mais.")
            info = self.catalogo[tipo]
            valor = info["preco"] * quantidade
            limite = self.regras["limite_compra_sem_aprovacao"]
            if valor > limite:
                m.exigir_proposta(args.get("proposta_id"), "abrir_compra", tipo)
            prazo = int(info["prazo_dias_uteis"])
            chega = somar_dias_uteis(m.relogio.data(), prazo)
            compra = {
                "id": m.novo_id("CMP"),
                "tipo": tipo,
                "modelo": info["modelo"],
                "quantidade": quantidade,
                "valor": valor,
                "pedido_id": args.get("pedido_id"),
                "previsao": chega.isoformat(),
                "status": "a caminho",
            }
            self.compras[compra["id"]] = compra
            m.agendar(m.relogio.minuto_da_data(chega, "09:00"), lambda: self._chegar_compra(compra))
            return {"compra": compra}

        def corrigir_inventario(args, agente, motivo):
            item = self.item(args["patrimonio"])
            campo = args["campo"]
            if campo not in CAMPOS_CORRIGIVEIS:
                raise ErroFerramenta(422, "Campo não pode ser corrigido.", campos=list(CAMPOS_CORRIGIVEIS))
            m.exigir_proposta(args.get("proposta_id"), "corrigir_inventario", item["patrimonio"])
            antes = item.get(campo, "")
            item[campo] = str(args.get("valor", ""))
            return {"item": item, "antes": antes}

        def baixar(args, agente, motivo):
            item = self.item(args["patrimonio"])
            m.exigir_proposta(args.get("proposta_id"), "baixar", item["patrimonio"])
            item.update(status="baixado", com_quem="", desde="")
            return {"item": item}

        pat = {"patrimonio": texto("Patrimônio, por exemplo EQ-0142")}
        return [
            Ferramenta("consultar_estoque", "Mostra os itens disponíveis para entrega, por tipo.", consultar_estoque, {"tipo": texto("Tipo (opcional)")}, acao=False),
            Ferramenta(
                "buscar_itens",
                "Procura itens no inventário por qualquer campo (todos opcionais).",
                buscar_itens,
                {**pat, "tipo": texto(""), "status": texto(""), "situacao": texto(""), "com_quem": texto("Id do colaborador"), "numero_serie": texto(""), "marca": texto("")},
                acao=False,
            ),
            Ferramenta("consultar_colaborador", "Mostra uma pessoa (por id, nome ou e-mail), o kit que ela deve ter e os itens com ela.", consultar_colaborador, {"busca": texto("Id, nome ou e-mail")}, ["busca"], acao=False),
            Ferramenta("consultar_catalogo_compra", "Mostra preço e prazo de entrega de cada tipo de item.", consultar_catalogo_compra, acao=False),
            Ferramenta("consultar_regras", "Mostra as regras de kit, prazos, devolução e limite de compra.", consultar_regras, acao=False),
            Ferramenta("reservar", "Separa um item disponível para uma pessoa.", reservar, {**pat, "para": texto("Id, nome ou e-mail da pessoa"), "pedido_id": texto("Pedido relacionado (opcional)")}, ["patrimonio", "para"]),
            Ferramenta("alocar", "Registra a entrega de um item a uma pessoa.", alocar, {**pat, "para": texto("Id, nome ou e-mail da pessoa"), "pedido_id": texto("Pedido relacionado (opcional)")}, ["patrimonio", "para"]),
            Ferramenta(
                "registrar_devolucao",
                "Registra que um item voltou, com a situação dele. Só funciona depois que o item voltou de fato.",
                registrar_devolucao,
                {**pat, "situacao": texto("novo, usado, quebrado, danificado ou perdido"), "pedido_id": texto("Pedido relacionado (opcional)")},
                ["patrimonio", "situacao"],
            ),
            Ferramenta(
                "cobrar_devolucao",
                "Pede para uma pessoa devolver itens. A resposta chega depois na caixa de entrada.",
                cobrar_devolucao,
                {"colaborador": texto("Id, nome ou e-mail"), **pat, "mensagem": texto("Texto da cobrança"), "pedido_id": texto("Pedido relacionado (opcional)")},
                ["colaborador"],
            ),
            Ferramenta(
                "abrir_compra",
                "Compra itens do catálogo. Acima do limite sem aprovação, precisa de uma proposta aprovada (acao='abrir_compra', alvo=<tipo>).",
                abrir_compra,
                {"tipo": texto("Tipo do item"), "quantidade": {"type": "integer"}, "proposta_id": texto("Id da proposta aprovada (quando precisa)"), "pedido_id": texto("Pedido relacionado (opcional)")},
                ["tipo"],
            ),
            Ferramenta(
                "corrigir_inventario",
                "Corrige um campo de um item. Precisa de uma proposta aprovada (acao='corrigir_inventario', alvo=<patrimônio>).",
                corrigir_inventario,
                {**pat, "campo": texto("Campo a corrigir"), "valor": texto("Novo valor"), "proposta_id": texto("Id da proposta aprovada")},
                ["patrimonio", "campo", "proposta_id"],
            ),
            Ferramenta(
                "baixar",
                "Tira um item do parque (perdido ou sem conserto). Precisa de uma proposta aprovada (acao='baixar', alvo=<patrimônio>).",
                baixar,
                {**pat, "proposta_id": texto("Id da proposta aprovada")},
                ["patrimonio", "proposta_id"],
            ),
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
        gasto = sum(c["valor"] for c in self.compras.values())
        return self.indicadores_caixa() + estoque + [
            {"nome": "Entradas com kit completo", "valor": f"{self.entradas['completas']} de {self.entradas['completas'] + self.entradas['incompletas']}", "alerta": self.entradas["incompletas"] > 0},
            {"nome": "Compras", "valor": f"{len(self.compras)} (R$ {gasto:,.0f})".replace(",", ".")},
            {"nome": "Propostas", "valor": len(self.mundo.propostas)},
        ]
