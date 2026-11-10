"""Tema 1: triagem N1 de chamados e incidentes."""

from __future__ import annotations

import json
import pathlib
import re

from ..nucleo import ErroFerramenta, Ferramenta, TemaBase, sem_acento, texto

CRITICIDADES_INCIDENTE = ("P0", "P1", "P2")


class Triagem(TemaBase):
    titulo = "Tema 1 — Triagem N1 de chamados e incidentes"
    segundos_por_dia_padrao = 240  # 5 dias de expediente em 20 minutos

    def __init__(self, mundo, dados: pathlib.Path, cenario: dict) -> None:
        super().__init__(mundo, dados, cenario)
        ler = lambda nome: json.loads((dados / nome).read_text(encoding="utf-8"))
        self.catalogo = {c["tipo"]: c for c in ler("catalogo.json")}
        self.times = {t["time"]: t for t in ler("times.json")}
        self.faq = ler("faq.json")
        self.chamados = {c["id"]: dict(c, pedidos=[]) for c in ler("chamados_abertos.json")}
        self.incidentes: dict[str, dict] = {}
        self.cobrancas = 0

    # ---------- reações do mundo ----------
    def ao_receber(self, item: dict) -> None:
        cobranca = item["_original"].get("cobranca")
        if cobranca:
            self.mundo.agendar_em_horas(float(cobranca["apos_horas"]), lambda: self._cobrar(item, cobranca))

    def _cobrar(self, item: dict, cobranca: dict) -> None:
        if item["acoes"]:
            return
        self.cobrancas += 1
        self.mundo.mensagem(item["de"], item["nome"], cobranca["assunto"], cobranca["corpo"], responde_a=item["id"])
        self.mundo.alerta("atencao", f"{item['id']} ficou sem ação e {item['nome'] or item['de']} cobrou.", pedido_id=item["id"])

    def _aprovar_chamado(self, chamado: dict) -> None:
        if chamado["status"] == "aguardando aprovação":
            chamado["status"] = "aprovado"
            self.mundo.emitir("mundo", mensagem=f"{chamado['id']} aprovado pelo gestor e enviado ao time {chamado['time']}.")

    # ---------- ferramentas ----------
    def ferramentas(self) -> list[Ferramenta]:
        m = self.mundo

        def consultar_faq(args, agente, motivo):
            termos = set(re.findall(r"\w+", sem_acento(args["busca"]))) - {"de", "do", "da", "o", "a", "e", "como", "que", "um", "uma", "para", "no", "na"}
            pontuados = []
            for item in self.faq:
                base = set(re.findall(r"\w+", sem_acento(item["pergunta"] + " " + " ".join(item.get("palavras_chave", [])))))
                pontos = len(termos & base)
                if pontos:
                    pontuados.append((pontos, item))
            pontuados.sort(key=lambda x: -x[0])
            achados = [{"id": i["id"], "pergunta": i["pergunta"], "resposta": i["resposta"]} for _, i in pontuados[:3]]
            return {"resultados": achados, "mensagem": None if achados else "Nada no FAQ para essa busca."}

        def consultar_catalogo(args, agente, motivo):
            return {"tipos": list(self.catalogo.values())}

        def listar_times(args, agente, motivo):
            return {"times": list(self.times.values())}

        def buscar_chamados(args, agente, motivo):
            busca = sem_acento(args.get("texto", ""))
            solicitante = sem_acento(args.get("solicitante", ""))
            achados = []
            for c in list(self.chamados.values()) + list(self.incidentes.values()):
                alvo = sem_acento(json.dumps(c, ensure_ascii=False))
                if (not busca or all(t in alvo for t in busca.split())) and (not solicitante or solicitante in sem_acento(c.get("solicitante", ""))):
                    achados.append(c)
            return {"chamados": achados[:20]}

        def abrir_chamado(args, agente, motivo):
            item = m.pedido(args["pedido_id"])
            tipo = args["tipo"]
            if tipo not in self.catalogo:
                raise ErroFerramenta(422, f"Tipo '{tipo}' não existe no catálogo.", tipos=list(self.catalogo))
            campos = args.get("campos") or {}
            if not isinstance(campos, dict):
                raise ErroFerramenta(422, "'campos' precisa ser um objeto com os campos obrigatórios do tipo.")
            faltam = [c for c in self.catalogo[tipo]["campos_obrigatorios"] if not str(campos.get(c, "")).strip()]
            if faltam:
                raise ErroFerramenta(422, "Faltam campos obrigatórios: " + ", ".join(faltam), campos_obrigatorios=self.catalogo[tipo]["campos_obrigatorios"])
            cid = m.novo_id("CH", 1001, 4)
            info = self.catalogo[tipo]
            chamado = {
                "id": cid,
                "tipo": tipo,
                "time": info["time"],
                "solicitante": item["de"],
                "resumo": item["assunto"],
                "campos": campos,
                "status": "aguardando aprovação" if info["aprovacao"] else "aberto",
                "aberto_em": m.agora(),
                "pedidos": [item["id"]],
            }
            self.chamados[cid] = chamado
            item["status"] = "chamado aberto"
            if info["aprovacao"]:
                m.agendar_em_horas(m.sorteio.uniform(1, 4), lambda: self._aprovar_chamado(chamado))
            return {"chamado": chamado}

        def pedir_informacao(args, agente, motivo):
            item = m.pedido(args["pedido_id"])
            item["status"] = "aguardando informação"
            original = item["_original"]
            complemento = original.get("complemento")
            if complemento and not item.get("_complemento_agendado"):
                item["_complemento_agendado"] = True
                m.agendar_em_horas(
                    float(complemento["apos_horas"]),
                    lambda: m.mensagem(item["de"], item["nome"], "RE: " + item["assunto"], complemento["corpo"], responde_a=item["id"]),
                )
            elif not complemento:
                m.agendar_em_horas(
                    m.sorteio.uniform(0.5, 2),
                    lambda: m.mensagem(
                        item["de"],
                        item["nome"],
                        "RE: " + item["assunto"],
                        "Oi! Acho que já mandei tudo no primeiro e-mail. O que exatamente está faltando?",
                        responde_a=item["id"],
                    ),
                )
            return {"mensagem": f"Pedido de informação enviado para {item['de']}."}

        def juntar_duplicado(args, agente, motivo):
            item = m.pedido(args["pedido_id"])
            alvo = self.chamados.get(args["chamado_id"]) or self.incidentes.get(args["chamado_id"])
            if not alvo:
                raise ErroFerramenta(404, f"Chamado ou incidente {args['chamado_id']} não encontrado.")
            alvo.setdefault("pedidos", []).append(item["id"])
            item["status"] = "duplicado"
            return {"mensagem": f"{item['id']} ligado a {alvo['id']}.", "chamado": alvo}

        def encaminhar(args, agente, motivo):
            item = m.pedido(args["pedido_id"])
            if args["time"] not in self.times:
                raise ErroFerramenta(422, f"Time '{args['time']}' não existe.", times=list(self.times))
            item["status"] = "encaminhado"
            item["encaminhado_para"] = args["time"]
            return {"mensagem": f"{item['id']} encaminhado ao time {args['time']}."}

        def abrir_incidente(args, agente, motivo):
            item = m.pedido(args["pedido_id"])
            criticidade = str(args["criticidade"]).upper()
            if criticidade not in CRITICIDADES_INCIDENTE:
                raise ErroFerramenta(422, "Incidente é P0, P1 ou P2. P3 e P4 viram chamado de Suporte a produto.")
            iid = m.novo_id("INC")
            incidente = {
                "id": iid,
                "criticidade": criticidade,
                "produto": args.get("produto", ""),
                "resumo": args["resumo"],
                "solicitante": item["de"],
                "aberto_em": m.agora(),
                "pedidos": [item["id"]],
                "status": "aberto",
            }
            self.incidentes[iid] = incidente
            item["status"] = "incidente aberto"
            nivel = "atencao" if criticidade in ("P0", "P1") else "info"
            m.alerta(nivel, f"{iid} {criticidade} aberto por {agente}: {args['resumo']}", pedido_id=item["id"])
            return {"incidente": incidente}

        def cancelar_chamado(args, agente, motivo):
            chamado = self.chamados.get(args["chamado_id"])
            if not chamado:
                raise ErroFerramenta(404, f"Chamado {args['chamado_id']} não encontrado.")
            m.exigir_proposta(args.get("proposta_id"), "cancelar_chamado", chamado["id"])
            chamado["status"] = "cancelado"
            return {"chamado": chamado}

        def trocar_aprovador(args, agente, motivo):
            chamado = self.chamados.get(args["chamado_id"])
            if not chamado:
                raise ErroFerramenta(404, f"Chamado {args['chamado_id']} não encontrado.")
            m.exigir_proposta(args.get("proposta_id"), "trocar_aprovador", chamado["id"])
            chamado["aprovador"] = args["aprovador"]
            return {"chamado": chamado}

        pid = {"pedido_id": texto("Id do pedido")}
        return [
            Ferramenta("consultar_faq", "Busca respostas prontas no FAQ da empresa.", consultar_faq, {"busca": texto("Palavras da dúvida")}, ["busca"], acao=False),
            Ferramenta("consultar_catalogo", "Lista os tipos de chamado, com time, campos obrigatórios, aprovação e prazo.", consultar_catalogo, acao=False),
            Ferramenta("listar_times", "Lista os times da empresa e o que cada um atende.", listar_times, acao=False),
            Ferramenta(
                "buscar_chamados",
                "Procura chamados e incidentes já abertos, para achar duplicados.",
                buscar_chamados,
                {"texto": texto("Palavras para buscar (opcional)"), "solicitante": texto("E-mail ou parte do e-mail (opcional)")},
                acao=False,
            ),
            Ferramenta(
                "abrir_chamado",
                "Abre um chamado do catálogo. Recusa se o tipo não existir ou faltar campo obrigatório.",
                abrir_chamado,
                {**pid, "tipo": texto("Tipo do catálogo"), "campos": {"type": "object", "description": "Campos obrigatórios do tipo"}},
                ["pedido_id", "tipo", "campos"],
            ),
            Ferramenta(
                "pedir_informacao",
                "Pede a quem fez o pedido as informações que faltam. A resposta chega depois na caixa de entrada.",
                pedir_informacao,
                {**pid, "campos": {"type": "array", "items": {"type": "string"}, "description": "O que falta"}, "mensagem": texto("Texto para a pessoa")},
                ["pedido_id", "mensagem"],
            ),
            Ferramenta(
                "juntar_duplicado",
                "Liga um pedido a um chamado ou incidente que já existe.",
                juntar_duplicado,
                {**pid, "chamado_id": texto("Id do chamado (CH-...) ou incidente (INC-...)")},
                ["pedido_id", "chamado_id"],
            ),
            Ferramenta(
                "encaminhar",
                "Encaminha ao time certo um pedido que não é chamado do catálogo.",
                encaminhar,
                {**pid, "time": texto("Nome do time"), "resumo": texto("Resumo para o time")},
                ["pedido_id", "time"],
            ),
            Ferramenta(
                "abrir_incidente",
                "Abre um incidente P0, P1 ou P2.",
                abrir_incidente,
                {**pid, "criticidade": texto("P0, P1 ou P2"), "produto": texto("Produto afetado"), "resumo": texto("O que está acontecendo")},
                ["pedido_id", "criticidade", "resumo"],
            ),
            Ferramenta(
                "cancelar_chamado",
                "Cancela um chamado. Precisa de uma proposta aprovada (acao='cancelar_chamado', alvo=<id do chamado>).",
                cancelar_chamado,
                {"chamado_id": texto("Id do chamado"), "proposta_id": texto("Id da proposta aprovada")},
                ["chamado_id", "proposta_id"],
            ),
            Ferramenta(
                "trocar_aprovador",
                "Troca o aprovador de um chamado. Precisa de uma proposta aprovada (acao='trocar_aprovador', alvo=<id do chamado>).",
                trocar_aprovador,
                {"chamado_id": texto("Id do chamado"), "aprovador": texto("E-mail do novo aprovador"), "proposta_id": texto("Id da proposta aprovada")},
                ["chamado_id", "aprovador", "proposta_id"],
            ),
        ]

    def indicadores(self) -> list[dict]:
        novos = [c for c in self.chamados.values() if c["id"] >= "CH-1001"]
        return self.indicadores_caixa() + [
            {"nome": "Chamados abertos", "valor": len(novos)},
            {"nome": "Incidentes", "valor": len(self.incidentes)},
            {"nome": "Propostas", "valor": len(self.mundo.propostas)},
            {"nome": "Cobranças recebidas", "valor": self.cobrancas, "alerta": self.cobrancas > 0},
        ]
