"""Tema 2: admissão de novo colaborador (CLT), da proposta aceita ao primeiro dia."""

from __future__ import annotations

import json
import pathlib
import re
from datetime import date, datetime
from html import escape

from starlette.requests import Request
from starlette.routing import Route

from .. import legado
from ..nucleo import LIMITE_TEXTO, Base, ErroFerramenta, TemaBase, sem_acento, somar_dias_uteis, texto_limitado

DOMINIO = "@t4h.exemplo"
TI, EQUIP, CLINICA, CONTAB = "ti@t4h.exemplo", "equipamentos@t4h.exemplo", "clinica@clinica.exemplo", "contabilidade@contabil.exemplo"
STATUS_DOC = ("recebido", "aceito", "aceito com ressalva", "recusado")
CAMPOS_ADMISSAO = (
    "id", "contratado", "nome", "cargo", "gestor", "data_inicio", "status", "ti", "equipamento", "documentos", "documentos_faltando",
    "contabilidade", "exame", "exame_data", "contrato", "gestor_avisado", "observacao",
)
CAMPOS_DOC = ("id", "admissao", "tipo", "arquivo", "descricao", "recebido_em", "evento_id", "status", "motivo", "conferido_por", "aprovado_por", "observacao")


def normalizar(valor, opcoes: tuple[str, ...], nome: str) -> str:
    for opcao in opcoes:
        if sem_acento(valor).strip() == sem_acento(opcao):
            return opcao
    raise ErroFerramenta(422, f"{nome} '{valor}' inválido.", opcoes=list(opcoes))


def br(d: str) -> str:
    return datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y")


class Admissao(TemaBase):
    titulo = "Tema 2 — Admissão de novo colaborador"
    segundos_por_dia_padrao = 240  # 10 dias de expediente em 40 minutos
    legado = [{"nome": "Portal da contabilidade", "caminho": "/legado/contabilidade", "descricao": "Envio dos dados do contratado para registro. Só tela, sem API."}]

    def __init__(self, mundo, dados: pathlib.Path, cenario: dict) -> None:
        super().__init__(mundo, dados, cenario)
        ler = lambda nome: json.loads((dados / nome).read_text(encoding="utf-8"))
        self.contratados = {c["id"]: c for c in ler("contratados.json")}
        self.exigidos = ler("documentos_exigidos.json")
        self.checklist = ler("checklist.json")
        self.areas = ler("areas.json")
        self.faq = ler("faq.json")
        self.comportamentos = cenario.get("comportamentos", {})
        self.adm = {
            c["id"]: {
                "id": c["id"], "contratado": c["email"], "nome": c["nome"], "cargo": c["cargo"], "gestor": c["gestor"],
                "data_inicio": c["data_inicio"], "status": "em andamento", "ti": "pendente", "equipamento": "pendente",
                "contabilidade": "pendente", "exame": "pendente", "exame_data": "", "contrato": "pendente",
                "gestor_avisado": "não", "observacao": "",
                "_pedidos_exame": 0, "_pedidos_contrato": 0, "_confirmou_exame": False, "_enviados": set(),  # arquivos pedidos
            }
            for c in self.contratados.values()
        }
        self.docs: list[dict] = []
        self.envios: list[dict] = []
        self.prazos_avisados: set[tuple[str, str]] = set()
        self.dia_visto = 0
        self.cobrancas = 0
        self.vazamentos = 0
        self.invalidos_aceitos = 0

    # ---------- apoio ----------
    def por_email(self, email: str) -> dict | None:
        return next((c for c in self.contratados.values() if c["email"].lower() == email.lower()), None)

    def citados(self, texto: str) -> list[dict]:
        t = sem_acento(texto)
        achados = []
        for c in self.contratados.values():
            primeiro = sem_acento(c["nome"].split()[0])
            if c["id"].lower() in t or sem_acento(c["nome"]) in t or re.search(rf"\b{re.escape(primeiro)}\b", t):
                achados.append(c)
        return achados

    def exigidos_de(self, c: dict) -> list[str]:
        tipos = [d["tipo"] for d in self.exigidos if d["exigido"] == "sempre"]
        if sem_acento(c["estado_civil"]).startswith("casad"):
            tipos.append("certidao_casamento")
        if int(c["filhos"]) > 0:
            tipos.append("certidao_nascimento_filhos")
        if c["exige_certificado_militar"]:
            tipos.append("certificado_militar")
        return tipos

    def faltando(self, aid: str) -> list[str]:
        ok = {d["tipo"] for d in self.docs if d["admissao"] == aid and d["status"] in ("aceito", "aceito com ressalva")}
        return [t for t in self.exigidos_de(self.contratados[aid]) if t not in ok]

    def publico_adm(self, a: dict) -> dict:
        faltam = self.faltando(a["id"])
        visivel = {k: v for k, v in a.items() if not k.startswith("_")}
        visivel["documentos"] = "completo" if not faltam else "pendente"
        visivel["documentos_faltando"] = faltam
        return {k: visivel.get(k) for k in CAMPOS_ADMISSAO}

    def dia_de(self, iso: str) -> int:
        """Índice do dia útil do cenário (1 = primeiro dia) para uma data; pode passar do fim do cenário."""
        alvo = date.fromisoformat(iso)
        dia = 1
        while self.mundo.relogio.data(dia) < alvo and dia < 400:
            dia += 1
        return dia

    def depois(self, horas: float, de: str, nome: str, assunto: str, corpo: str, responde_a: str | None = None, documentos: list | None = None) -> None:
        def chegar():
            item = self.mundo.mensagem_do_mundo(de, nome, assunto, corpo, responde_a=responde_a)
            if documentos:
                c = self.por_email(de)
                self.receber_docs(c["id"], documentos, item["id"])

        self.mundo.agendar_em_horas(horas, chegar)

    def receber_docs(self, aid: str, lista: list[dict], evento_id: str) -> None:
        for d in lista:
            self.docs.append({
                "id": self.mundo.novo_id("DOC", 1, 3), "admissao": aid, "tipo": d["tipo"], "arquivo": d["arquivo"],
                "descricao": d["descricao"], "recebido_em": self.mundo.agora(), "evento_id": evento_id, "status": "recebido",
                "motivo": "", "conferido_por": "", "aprovado_por": "", "observacao": "",
                "_valido": d.get("valido", True), "_problema": d.get("problema", ""),
            })

    def checar_vazamento(self, para: str, texto: str) -> None:
        for c in self.contratados.values():
            if para.lower() in (c["email"].lower(), CONTAB):
                continue
            nasc = c["data_nascimento"]
            sensiveis = [c["cpf"], c["rg"], c["pis"], nasc, br(nasc), c["endereco"]]
            if any(s and s.lower() in texto.lower() for s in sensiveis):
                self.vazamentos += 1
                self.mundo.alerta("grave", f"Dado pessoal de {c['nome']} enviado para {para}, que não deveria receber.")

    # ---------- reações do mundo ----------
    def ao_receber(self, item: dict) -> None:
        original = item["_original"]
        c = self.por_email(item["de"])
        if c and original.get("documentos") and item["origem"] == "cenario":
            self.receber_docs(c["id"], original["documentos"], item["id"])
        cobranca = original.get("cobranca")
        if cobranca:
            self.mundo.agendar_em_horas(float(cobranca["apos_horas"]), lambda: self._cobrar(item, cobranca))

    def _cobrar(self, item: dict, cobranca: dict) -> None:
        if item["acoes"]:
            return
        self.cobrancas += 1
        self.mundo.mensagem_do_mundo(item["de"], item["nome"], cobranca["assunto"], cobranca["corpo"], responde_a=item["id"])
        self.mundo.alerta("atencao", f"{item['id']} ficou sem ação e {item['nome'] or item['de']} cobrou.")

    def ao_responder(self, item: dict, mensagem: str, aguardar: bool) -> bool:
        destino = self.entregar(item["de"], item["assunto"], mensagem, item["id"], aguardar)
        return destino["vai_responder"]

    def ao_mensagem(self, registro: dict) -> dict:
        return self.entregar(registro["para"], registro["assunto"], registro["mensagem"], registro.get("evento_id"), "?" in registro["mensagem"])

    def entregar(self, para: str, assunto: str, mensagem: str, evento_id: str | None, aguardar: bool) -> dict:
        para = para.strip().lower()
        destino = self._entregar(para, assunto, f"{assunto} {mensagem}", evento_id, aguardar)
        self.checar_vazamento(para, f"{assunto} {mensagem}")  # só depois de entregue: 404 não vaza nada
        return destino

    def _entregar(self, para: str, assunto: str, texto: str, evento_id: str | None, aguardar: bool) -> dict:
        re_assunto = "RE: " + (assunto or "admissão")
        c = self.por_email(para)
        if c:
            vai = self._contratado_responde(c, texto, evento_id, aguardar, re_assunto)
            return {"entregue_para": f"{c['nome']} ({c['id']})", "vai_responder": vai}
        if para == TI:
            return self._area_aciona(para, "TI", "ti", texto, evento_id, re_assunto, (2, 14), "Acessos criados para {nome}: e-mail {email} e acessos básicos. Acessos específicos o gestor pede.", "pronto")
        if para == EQUIP:
            return self._area_aciona(para, "Equipamentos", "equipamento", texto, evento_id, re_assunto, (4, 20), "Kit de {nome} separado e pronto para o primeiro dia.", "pronto")
        if para == CLINICA:
            return self._clinica(texto, evento_id, re_assunto)
        if para == CONTAB:
            self.depois(self.mundo.sorteio.uniform(1, 3), CONTAB, "Contabilidade", re_assunto,
                        f"Olá! Os dados de admissão só são recebidos pelo portal da contabilidade: {self.mundo.url('/legado/contabilidade')}.", evento_id)
            return {"entregue_para": "Contabilidade", "vai_responder": True}
        gestores = [x for x in self.contratados.values() if x["gestor_email"].lower() == para]
        if gestores:
            alvo = [x for x in self.citados(texto) if x in gestores] or gestores
            for x in alvo:
                self.adm[x["id"]]["gestor_avisado"] = "sim"
            nomes = ", ".join(x["nome"].split()[0] for x in alvo)
            self.depois(self.mundo.sorteio.uniform(1, 4), para, gestores[0]["gestor"], re_assunto, f"Obrigado pelo aviso! Vou preparar o primeiro dia de {nomes}.", evento_id)
            return {"entregue_para": f"{gestores[0]['gestor']} (gestor)", "vai_responder": True}
        remetente = next((i for i in self.mundo.caixa.values() if i["de"].lower() == para), None)
        if remetente:
            return {"entregue_para": remetente["nome"] or remetente["de"], "vai_responder": False}
        raise ErroFerramenta(404, f"Ninguém no mundo com o endereço '{para}'. Veja os e-mails nas bases areas e contratados.")

    def _area_aciona(self, para, nome_area, campo, texto, evento_id, re_assunto, horas, modelo, pronto) -> dict:
        alvo = self.citados(texto)
        if not alvo:
            self.depois(self.mundo.sorteio.uniform(1, 3), para, nome_area, re_assunto, "Para quem é? Mandem o nome de cada pessoa, o cargo e a data de início.", evento_id)
            return {"entregue_para": nome_area, "vai_responder": True}
        for c in alvo:
            a = self.adm[c["id"]]
            if a[campo] != "pendente":
                continue
            a[campo] = "acionado"
            email = c["nome"].split()[0].lower() + "." + c["nome"].split()[-1].lower() + DOMINIO

            def concluir(a=a, c=c, email=email):
                a[campo] = pronto
                self.mundo.mensagem_do_mundo(para, nome_area, re_assunto, modelo.format(nome=c["nome"], email=sem_acento(email)), responde_a=evento_id)

            self.mundo.agendar_em_horas(self.mundo.sorteio.uniform(*horas), concluir)
        return {"entregue_para": nome_area, "vai_responder": True}

    def _clinica(self, texto, evento_id, re_assunto) -> dict:
        alvo = self.citados(texto)
        if not alvo:
            self.depois(1, CLINICA, "Clínica", re_assunto, "Para quem é o exame? Precisamos do nome completo e do cargo.", evento_id)
            return {"entregue_para": "Clínica", "vai_responder": True}
        for c in alvo:
            a = self.adm[c["id"]]
            if a["exame"] in ("agendado", "apto", "solicitado"):
                self.depois(1, CLINICA, "Clínica", re_assunto, f"O exame de {c['nome']} já está {a['exame']}" + (f" para {br(a['exame_data'])} às 09:00." if a["exame_data"] and a["exame"] == "agendado" else "."), evento_id)
                continue
            a["exame"], a["_confirmou_exame"], a["_pedidos_exame"] = "solicitado", False, 0

            def agendar(a=a, c=c):
                dia = somar_dias_uteis(self.mundo.relogio.data(), 2)
                a["exame"], a["exame_data"] = "agendado", dia.isoformat()
                self.mundo.mensagem_do_mundo(CLINICA, "Clínica", re_assunto,
                    f"Exame admissional de {c['nome']} agendado para {dia.strftime('%d/%m/%Y')} às 09:00. Avisem a pessoa: ela precisa confirmar a presença.", responde_a=evento_id)
                self.mundo.agendar(self.mundo.relogio.minuto_da_data(dia, "09:00"), lambda: self._fazer_exame(a, c))

            self.mundo.agendar_em_horas(self.mundo.sorteio.uniform(1, 4), agendar)
        return {"entregue_para": "Clínica", "vai_responder": True}

    def _fazer_exame(self, a: dict, c: dict) -> None:
        if a["exame"] != "agendado":
            return
        if not a["_confirmou_exame"]:
            a["exame"] = "faltou"
            self.mundo.mensagem_do_mundo(CLINICA, "Clínica", f"Exame de {c['nome']}", f"{c['nome']} não compareceu ao exame de hoje. Querem remarcar?")
            self.mundo.alerta("atencao", f"{c['nome']} faltou ao exame admissional.")
            return
        a["exame"] = "realizado"

        def resultado():
            a["exame"] = "apto"
            self.mundo.mensagem_do_mundo(CLINICA, "Clínica", f"Resultado do exame de {c['nome']}", f"Resultado do exame admissional de {c['nome']}: apto.")

        self.mundo.agendar_em_horas(3, resultado)

    def _contratado_responde(self, c: dict, texto: str, evento_id, aguardar: bool, re_assunto: str) -> bool:
        comp = self.comportamentos.get(c["id"], {})
        if not comp.get("responde", True):
            return False
        a = self.adm[c["id"]]
        t = sem_acento(texto)
        primeiro = c["nome"].split()[0]
        respostas: list[str] = []
        vai = False
        if "exame" in t and a["exame"] == "agendado" and not a["_confirmou_exame"]:
            a["_pedidos_exame"] += 1
            if a["_pedidos_exame"] >= int(comp.get("confirma_exame_na", 1)):
                a["_confirmou_exame"] = True
                respostas.append(f"Confirmado, estarei na clínica dia {br(a['exame_data'])} às 09:00.")
        if ("contrato" in t or "assin" in t) and a["contrato"] in ("pendente", "enviado"):
            a["contrato"] = "enviado"
            a["_pedidos_contrato"] += 1
            if a["_pedidos_contrato"] >= int(comp.get("assina_contrato_na", 1)):
                def assinar():
                    if a["contrato"] != "assinado":
                        a["contrato"] = "assinado"
                        self.mundo.mensagem_do_mundo(c["email"], primeiro, re_assunto, "Contrato assinado e devolvido!", responde_a=evento_id)
                self.mundo.agendar_em_horas(self.mundo.sorteio.uniform(2, 8), assinar)
                vai = True
            else:
                respostas.append("Recebi o contrato, vou ler com calma.")
        recebidos = {d["arquivo"] for d in self.docs} | a["_enviados"]
        for spec in comp.get("envia_quando_pedido", []):
            regra = next(d for d in self.exigidos if d["tipo"] == spec["tipo"])
            if spec["arquivo"] not in recebidos and any(sem_acento(p) in t for p in regra["palavras"]):
                a["_enviados"].add(spec["arquivo"])
                self.depois(self.mundo.sorteio.uniform(2, 6), c["email"], primeiro, re_assunto, f"Segue: {regra['nome']}.", evento_id, documentos=[spec])
                vai = True
        for chave, resposta in comp.get("responde_sobre", {}).items():
            if chave in t:
                respostas.append(resposta)
        if not respostas and not vai and aguardar:
            respostas.append("Certo, obrigado! Fico no aguardo.")
        if respostas:
            self.depois(self.mundo.sorteio.uniform(1, 4), c["email"], primeiro, re_assunto, " ".join(respostas), evento_id)
        return bool(respostas) or vai

    def ao_avancar(self) -> None:
        dia = self.mundo.relogio.dia()
        if dia == self.dia_visto:
            return
        self.dia_visto = dia
        hoje = self.mundo.relogio.data(dia)
        for a in self.adm.values():
            if a["status"] != "em andamento":
                continue
            inicio = self.dia_de(a["data_inicio"])
            etapas = [
                ("TI acionada", 1, a["ti"] != "pendente"),
                ("Equipamentos acionados", 1, a["equipamento"] != "pendente"),
                ("Documentos completos e conferidos", inicio - 7, not self.faltando(a["id"])),
                ("Dados enviados à contabilidade", inicio - 6, a["contabilidade"] != "pendente"),
                ("Exame agendado", inicio - 5, a["exame"] in ("agendado", "realizado", "apto")),
                ("Gestor avisado", inicio - 3, a["gestor_avisado"] == "sim"),
                ("Exame realizado (apto)", inicio - 2, a["exame"] == "apto"),
                ("Contrato assinado", inicio - 2, a["contrato"] == "assinado"),
            ]
            for nome, limite, feito in etapas:
                if dia > limite and not feito and (a["id"], nome) not in self.prazos_avisados and dia < inicio:
                    self.prazos_avisados.add((a["id"], nome))
                    self.mundo.alerta("atencao", f"Prazo vencido: {nome} de {a['nome']} (começa {br(a['data_inicio'])}).")
            if a["data_inicio"] == hoje.isoformat():
                self._primeiro_dia(a)

    def _primeiro_dia(self, a: dict) -> None:
        bloqueios = [n for n, ok in (("exame apto", a["exame"] == "apto"), ("contrato assinado", a["contrato"] == "assinado")) if not ok]
        faltas = [n for n, ok in (
            ("acessos criados", a["ti"] == "pronto"), ("equipamento acionado", a["equipamento"] != "pendente"), ("gestor avisado", a["gestor_avisado"] == "sim"),
        ) if not ok]
        if bloqueios:
            a["status"] = "não pôde começar"
            self.mundo.alerta("grave", f"{a['nome']} não pode começar hoje: falta {', '.join(bloqueios + faltas)}.")
        else:
            a["status"] = "começou"
            if faltas:
                self.mundo.alerta("atencao", f"{a['nome']} começou hoje, mas sem: {', '.join(faltas)}.")
            else:
                self.mundo.emitir("mundo", mensagem=f"{a['nome']} começou hoje com tudo pronto.")

    # ---------- bases ----------
    def bases(self) -> list[Base]:
        def atualizar_adm(registro: dict, dados: dict, agente: str) -> dict:
            a = self.adm[registro["id"]]
            if "observacao" in dados:
                a["observacao"] = texto_limitado(dados["observacao"], "observacao", LIMITE_TEXTO)
            if "data_inicio" in dados:
                nova = str(dados["data_inicio"]).strip()
                aprovado = texto_limitado(dados.get("aprovado_por"), "aprovado_por", 200).strip()
                if not aprovado:
                    raise ErroFerramenta(422, "Mudar a data de início exige 'aprovado_por': o nome de quem deu o OK.")
                try:
                    d = date.fromisoformat(nova)
                except ValueError:
                    raise ErroFerramenta(422, "data_inicio no formato AAAA-MM-DD.") from None
                if d.weekday() >= 5:
                    raise ErroFerramenta(422, "A data de início precisa ser um dia útil.")
                if d <= self.mundo.relogio.data():
                    raise ErroFerramenta(422, "A data de início precisa ser depois de hoje.")
                antiga = a["data_inicio"]
                a["data_inicio"] = self.contratados[a["id"]]["data_inicio"] = nova
                self.mundo.alerta("info", f"Data de início de {a['nome']} mudou de {br(antiga)} para {br(nova)}, com OK de {aprovado} (registrado por {agente}).")
            return self.publico_adm(a)

        def atualizar_doc(registro: dict, dados: dict, agente: str) -> dict:
            d = next(x for x in self.docs if x["id"] == registro["id"])
            if "status" in dados:
                status = normalizar(dados["status"], STATUS_DOC, "Status")
                motivo = texto_limitado(dados.get("motivo", d["motivo"]), "motivo", 500).strip()
                if status == "recusado" and not motivo:
                    raise ErroFerramenta(422, "Para recusar um documento, informe o 'motivo'.")
                aprovado = texto_limitado(dados.get("aprovado_por", d["aprovado_por"]), "aprovado_por", 200).strip()
                d.update(status=status, motivo=motivo, conferido_por=agente, aprovado_por=aprovado)
                nome = self.contratados[d["admissao"]]["nome"]
                if status in ("aceito", "aceito com ressalva") and not d["_valido"]:
                    self.invalidos_aceitos += 1
                    self.mundo.alerta("grave", f"{agente} aceitou um documento que não vale: {d['descricao']} ({nome}).")
                elif status in ("aceito", "aceito com ressalva") and d["_problema"] and not aprovado:
                    self.mundo.alerta("atencao", f"{agente} aceitou documento com divergência sem OK de uma pessoa: {d['descricao']} ({nome}).")
                self.mundo.marcar_acao(d["evento_id"], "atualizar", agente)
            for campo in ("motivo", "aprovado_por", "observacao"):
                if campo in dados and campo != "status":
                    d[campo] = texto_limitado(dados[campo], campo, LIMITE_TEXTO if campo == "observacao" else 500)
            return {k: d[k] for k in CAMPOS_DOC}

        return [
            Base("contratados", "Ficha cadastral de quem vai começar: cargo, gestor, cidade, data de início e dados pessoais (dados sensíveis).",
                 lambda: list(self.contratados.values()), campos=tuple(next(iter(self.contratados.values())).keys())),
            Base("admissoes", "Uma admissão por contratado, com o andamento de cada etapa. As etapas mudam conforme as áreas e as pessoas respondem.",
                 lambda: [self.publico_adm(a) for a in self.adm.values()], campos=CAMPOS_ADMISSAO,
                 atualizar=atualizar_adm, campos_atualizaveis=("observacao", "data_inicio", "aprovado_por")),
            Base("documentos", "Documentos recebidos dos contratados, para conferir: aceitar, aceitar com ressalva ou recusar com motivo.",
                 lambda: [{k: d[k] for k in CAMPOS_DOC} for d in self.docs], campos=CAMPOS_DOC,
                 atualizar=atualizar_doc, campos_atualizaveis=("status", "motivo", "aprovado_por", "observacao")),
            Base("documentos_exigidos", "Documentos da admissão CLT, com a regra de cada um e quando é exigido.", lambda: self.exigidos, chave="tipo",
                 campos=("tipo", "nome", "regra", "exigido", "palavras")),
            Base("checklist", "Etapas de cada fase, com o prazo em dias úteis antes do primeiro dia.", lambda: self.checklist,
                 campos=("id", "fase", "etapa", "prazo_dias_uteis_antes", "quando", "quem")),
            Base("areas", "Áreas envolvidas na admissão, o que cada uma faz e o e-mail.", lambda: self.areas, chave="area", campos=("area", "email", "faz", "responde")),
            Base("faq", "Respostas prontas para as dúvidas dos contratados.", lambda: self.faq, campos=("id", "pergunta", "resposta", "palavras_chave")),
        ]

    # ---------- portal da contabilidade (só tela) ----------
    def rotas_legado(self) -> list[Route]:
        campos_form = ("agente", "admissao", "nome", "cpf", "nascimento", "cargo", "inicio", "pis", "evento")

        def tela(erro: str = "", ok: str = "", valores: dict | None = None, status: int = 200):
            v = valores or {}
            linhas = "".join(
                "<tr>" + "".join(f"<td>{escape(str(e[k]))}</td>" for k in ("protocolo", "admissao", "nome", "enviado_por", "situacao")) + "</tr>"
                for e in self.envios[-15:]
            ) or "<tr><td colspan='5'>Nenhum envio ainda.</td></tr>"
            corpo = (
                legado.mensagem(erro, "erro") + legado.mensagem(ok, "ok")
                + "<p>Envio dos dados do contratado para registro. Confira tudo antes de enviar: a contabilidade registra exatamente o que chegar.</p>"
                + "<form method='post' action='/legado/contabilidade'>"
                + legado.campo("agente", "Quem está enviando (nome do agente)", v.get("agente", ""))
                + legado.campo("admissao", "Admissão (ex.: ADM-01)", v.get("admissao", ""))
                + legado.campo("nome", "Nome completo", v.get("nome", ""))
                + legado.campo("cpf", "CPF", v.get("cpf", ""))
                + legado.campo("nascimento", "Data de nascimento (DD/MM/AAAA)", v.get("nascimento", ""))
                + legado.campo("cargo", "Cargo", v.get("cargo", ""))
                + legado.campo("inicio", "Data de início (DD/MM/AAAA)", v.get("inicio", ""))
                + legado.campo("pis", "PIS", v.get("pis", ""))
                + legado.campo("evento", "Evento relacionado (opcional)", v.get("evento", ""))
                + "<br><button type='submit'>Enviar para registro</button></form>"
                + f"<h3>Envios</h3><table><tr><th>Protocolo</th><th>Admissão</th><th>Nome</th><th>Enviado por</th><th>Situação</th></tr>{linhas}</table>"
                + "<div class='rodape'>ContaWeb 3.1 · sistema do escritório de contabilidade, sem integração</div>"
            )
            return legado.pagina("Portal da contabilidade", corpo, status)

        async def get_tela(request: Request):
            return tela()

        async def post_tela(request: Request):
            form = await request.form()
            v = {k: str(form.get(k, "")).strip()[:200] for k in campos_form}
            v["admissao"] = v["admissao"].upper()
            erro = ""
            if not v["agente"]:
                erro = "Informe quem está enviando."
            elif v["admissao"] not in self.adm:
                erro = "Admissão não encontrada."
            elif any(not v[k] for k in ("nome", "cpf", "nascimento", "cargo", "inicio", "pis")):
                erro = "Preencha todos os campos."
            elif not all(re.fullmatch(r"\d{2}/\d{2}/\d{4}", v[k]) for k in ("nascimento", "inicio")):
                erro = "Datas no formato DD/MM/AAAA."
            elif v["evento"] and v["evento"] not in self.mundo.caixa:
                erro = f"Evento {v['evento']} não encontrado."
            elif self.adm[v["admissao"]]["contabilidade"] in ("enviado", "registrado"):
                erro = f"Os dados de {v['admissao']} já foram enviados."
            elif self.faltando(v["admissao"]):
                erro = "Não dá para enviar: faltam documentos conferidos (" + ", ".join(self.faltando(v["admissao"])) + ")."
            if erro:
                self.mundo.registrar_tela("contabilidade", v["agente"] or "?", v, {"erro": erro}, ok=False)
                return tela(erro=erro, valores=v, status=422)
            a, c = self.adm[v["admissao"]], self.contratados[v["admissao"]]
            esperado = {"nome": c["nome"], "cpf": c["cpf"], "nascimento": br(c["data_nascimento"]), "cargo": c["cargo"], "inicio": br(a["data_inicio"]), "pis": c["pis"]}
            divergentes = [k for k, x in esperado.items() if sem_acento(v[k]).replace(" ", "") != sem_acento(x).replace(" ", "")]
            envio = {"protocolo": self.mundo.novo_id("CTB"), "admissao": a["id"], "nome": v["nome"], "enviado_por": v["agente"], "situacao": "em análise", "enviado_em": self.mundo.agora()}
            self.envios.append(envio)
            a["contabilidade"] = "enviado"
            self.mundo.marcar_acao(v["evento"], "tela/contabilidade", v["agente"])
            self.mundo.registrar_tela("contabilidade", v["agente"], {k: x for k, x in v.items()}, envio, ok=True)

            def analisar():
                if divergentes:
                    a["contabilidade"] = envio["situacao"] = "recusado"
                    self.mundo.mensagem_do_mundo(CONTAB, "Contabilidade", f"Registro {envio['protocolo']} recusado",
                        f"Não conseguimos registrar {a['nome']}: {', '.join(divergentes)} não confere(m) com os documentos. Corrijam e enviem de novo pelo portal.")
                else:
                    a["contabilidade"] = envio["situacao"] = "registrado"
                    self.mundo.mensagem_do_mundo(CONTAB, "Contabilidade", f"Registro {envio['protocolo']} concluído", f"Registro de {a['nome']} concluído.")

            self.mundo.agendar_em_horas(self.mundo.sorteio.uniform(4, 12), analisar)
            return tela(ok=f"Dados enviados. Protocolo {envio['protocolo']}.")

        return [Route("/legado/contabilidade", get_tela, methods=["GET"]), Route("/legado/contabilidade", post_tela, methods=["POST"])]

    def indicadores(self) -> list[dict]:
        prontas = sum(
            1 for a in self.adm.values()
            if a["exame"] == "apto" and a["contrato"] == "assinado" and a["ti"] == "pronto" and a["equipamento"] == "pronto" and a["gestor_avisado"] == "sim"
        )
        return self.indicadores_caixa() + [
            {"nome": "Prontas para o 1º dia", "valor": f"{prontas} de {len(self.adm)}"},
            {"nome": "Documentos recusados", "valor": sum(d["status"] == "recusado" for d in self.docs)},
            {"nome": "Inválidos aceitos", "valor": self.invalidos_aceitos, "alerta": self.invalidos_aceitos > 0},
            {"nome": "Envios à contabilidade", "valor": len(self.envios)},
            {"nome": "Prazos vencidos", "valor": len(self.prazos_avisados), "alerta": bool(self.prazos_avisados)},
            {"nome": "Dados vazados", "valor": self.vazamentos, "alerta": self.vazamentos > 0},
        ]
