"""Motor de gravação das importações.

Cada linha importada guarda fonte, local (aba/página/arquivo interno), linha física e os
dados brutos. Um lançamento é gravado uma única vez; origens/destinos ficam em `partes`
com o valor da parcela quando informado. As parcelas são conferidas com o valor do
lançamento e nunca são distribuídas automaticamente.
"""

import hashlib

from . import auditoria, identificadores, util

LOTE = 5000


class Importador:
    def __init__(self, b, caso_id, fonte, adaptador, usuario, parametros=None, leiaute=None,
                 remessa_id=None, local=None, progresso=None):
        self.b = b
        self.caso_id = caso_id
        self.fonte = fonte
        self.usuario = usuario
        self.remessa_id = remessa_id if remessa_id is not None else fonte.get("remessa_id")
        self.progresso = progresso or (lambda n, msg="": None)
        self.rel = {
            "aceitos": 0, "pendentes": 0, "rejeitados": 0, "duplicatas": 0,
            "acessos": 0, "titulares": 0, "partes": 0,
            "totais_aceitos": {"C": 0, "D": 0}, "totais_pendentes": 0,
            "motivos": {}, "linhas_problema": [], "avisos": [],
            "parcelas": {"conferidas": 0, "divergentes": 0, "incompletas": 0, "unica": 0, "sem_parcelas": 0},
        }
        self.ids_lanc = []
        self._contador = 0
        self.imp_id = b.x(
            "INSERT INTO importacoes(caso_id, fonte_id, remessa_id, adaptador, leiaute, local, parametros_json, "
            "criado_em, criado_por, estado) VALUES (?,?,?,?,?,?,?,?,?, 'em_andamento')",
            (caso_id, fonte["id"], self.remessa_id, adaptador, leiaute, local, util.json_dump(parametros or {}),
             util.agora_iso(), usuario))
        self._abrir()

    # ------------------------------------------------------------ transação em lotes
    def _abrir(self):
        self.b.trava.acquire()
        self.b.con.execute("BEGIN")

    def _passo(self):
        self._contador += 1
        if self._contador % LOTE == 0:
            self.b.con.execute("COMMIT")
            self.b.trava.release()
            self.progresso(self._contador, "%d registros gravados" % self._contador)
            self._abrir()

    def _fechar(self, ok=True):
        try:
            self.b.con.execute("COMMIT" if ok else "ROLLBACK")
        finally:
            self.b.trava.release()

    # ------------------------------------------------------------ registros
    def aviso(self, texto):
        if texto not in self.rel["avisos"]:
            self.rel["avisos"].append(texto)

    def _problema(self, situacao, motivo, local, linha):
        self.rel["motivos"][motivo] = self.rel["motivos"].get(motivo, 0) + 1
        if len(self.rel["linhas_problema"]) < 1000:
            self.rel["linhas_problema"].append({"situacao": situacao, "motivo": motivo, "local": local, "linha": linha})

    def _ident(self, tipo, original, tabela, reg_id, local, linha, papel):
        if original is None or str(original).strip() == "":
            return
        if tipo == "doc":
            tipo, _ = identificadores.tipo_documento(original)
            if tipo is None:
                return
        norm = identificadores.normalizar(tipo, original)
        if not norm:
            return
        self.b.con.execute(
            "INSERT INTO ocorrencias_ident(caso_id, tipo, valor_norm, valor_original, tabela, registro_id, fonte_id, "
            "local, linha, papel, importacao_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (self.caso_id, tipo, norm, str(original), tabela, reg_id, self.fonte["id"], local, linha, papel, self.imp_id))

    @staticmethod
    def _conta_txt(banco, agencia, conta):
        if not (agencia or conta):
            return None
        return "BANCO %s AG %s CONTA %s" % (banco or "?", agencia or "?", conta or "?")

    def lancamento(self, d, partes=None):
        partes = partes or []
        situacao = d.get("situacao") or "aceito"
        motivo = d.get("motivo") or ""
        if situacao == "aceito":
            if d.get("valor_centavos") is None:
                situacao, motivo = "pendente", motivo or "valor não reconhecido"
            elif d.get("natureza") not in ("C", "D"):
                situacao, motivo = "pendente", motivo or "natureza não reconhecida"
            elif not d.get("data"):
                situacao, motivo = "pendente", motivo or "data não reconhecida"

        com_valor = [p for p in partes if p.get("valor_centavos") is not None]
        if not partes:
            estado = "sem_parcelas"
        elif len(com_valor) == len(partes):
            soma = sum(p["valor_centavos"] for p in partes)
            estado = "conferidas" if soma == d.get("valor_centavos") else "divergentes"
            if estado == "divergentes":
                self.aviso("Há lançamentos cujas parcelas de origem/destino não somam o valor do lançamento; "
                           "as parcelas desses lançamentos ficam fora dos totais por contraparte.")
        elif len(partes) == 1 and not com_valor:
            estado = "unica"
        else:
            estado = "incompletas"
            self.aviso("Há lançamentos com várias origens/destinos sem valor por parcela; o valor não foi distribuído.")
        self.rel["parcelas"][estado] += 1

        base_hash = "|".join(str(x or "") for x in (
            d.get("data"), d.get("hora"), d.get("valor_centavos"), d.get("natureza"), d.get("banco"),
            util.so_digitos(d.get("agencia")), util.so_digitos(d.get("conta")), d.get("documento"),
            util.normalizar_nome(d.get("descricao")),
            ";".join(sorted(util.so_digitos(p.get("doc")) + ":" + str(p.get("valor_centavos")) for p in partes))))
        h = hashlib.sha256(base_hash.encode("utf-8")).hexdigest()

        local, linha = d.get("local"), d.get("linha")
        tdoc_tipo = None
        if d.get("titular_doc"):
            tdoc_tipo, _ = util.classificar_documento(d.get("titular_doc"))
        cur = self.b.con.execute(
            "INSERT INTO lancamentos(caso_id, importacao_id, fonte_id, remessa_id, local, linha, chave_local, data, hora, "
            "fuso, data_original, valor_centavos, valor_original, natureza, natureza_original, situacao, motivo, "
            "titular_nome, titular_doc, titular_doc_tipo, titular_obs, titular_nome_norm, titular_doc_norm, banco, agencia, conta, conta_qtd_titulares, "
            "descricao, tipo_operacao, documento, pix_chave, pix_tipo, pix_id, ip, porta, mac, cidade, uf, interface, "
            "status_origem, parcelas_estado, bruto_json, hash_conteudo) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.caso_id, self.imp_id, self.fonte["id"], self.remessa_id, local, linha, d.get("chave_local"),
             d.get("data"), d.get("hora"), d.get("fuso"), d.get("data_original"), d.get("valor_centavos"),
             d.get("valor_original"), d.get("natureza"), d.get("natureza_original"), situacao, motivo,
             d.get("titular_nome"), d.get("titular_doc"), tdoc_tipo, d.get("titular_obs"),
             util.normalizar_nome(d.get("titular_nome")) or None, util.norm_doc(d.get("titular_doc")), d.get("banco"),
             d.get("agencia"), d.get("conta"), d.get("conta_qtd_titulares"), d.get("descricao"),
             d.get("tipo_operacao"), d.get("documento"), d.get("pix_chave"), d.get("pix_tipo"), d.get("pix_id"),
             d.get("ip"), d.get("porta"), d.get("mac"), d.get("cidade"), d.get("uf"), d.get("interface"),
             d.get("status_origem"), estado, util.json_dump(d.get("bruto") or {}), h))
        lid = cur.lastrowid
        self.ids_lanc.append(lid)
        if situacao == "aceito":
            self.rel["aceitos"] += 1
            self.rel["totais_aceitos"][d["natureza"]] += d["valor_centavos"]
        else:
            self.rel[situacao + "s"] += 1
            if situacao == "pendente" and d.get("valor_centavos"):
                self.rel["totais_pendentes"] += d["valor_centavos"]
            self._problema(situacao, motivo, local, linha)

        self._ident("nome", d.get("titular_nome"), "lancamentos", lid, local, linha, "titular")
        self._ident("doc", d.get("titular_doc"), "lancamentos", lid, local, linha, "titular")
        self._ident("banco", d.get("banco"), "lancamentos", lid, local, linha, "titular")
        self._ident("conta", self._conta_txt(d.get("banco"), d.get("agencia"), d.get("conta")), "lancamentos", lid, local, linha, "titular")
        self._ident("pix", d.get("pix_chave"), "lancamentos", lid, local, linha, "transacao")
        self._ident("pix_id", d.get("pix_id"), "lancamentos", lid, local, linha, "transacao")
        self._ident("ip", d.get("ip"), "lancamentos", lid, local, linha, "transacao")
        self._ident("dispositivo", d.get("mac"), "lancamentos", lid, local, linha, "transacao")
        if d.get("cidade") or d.get("uf"):
            self._ident("cidade", " / ".join(x for x in (d.get("cidade"), d.get("uf")) if x), "lancamentos", lid, local, linha, "transacao")
        self._ident("data", d.get("data"), "lancamentos", lid, local, linha, "lancamento")
        for i, p in enumerate(partes):
            papel = p.get("papel") or ({"C": "origem", "D": "destino"}.get(d.get("natureza"), "indefinido"))
            doc_tipo = None
            if p.get("doc"):
                doc_tipo, _ = util.classificar_documento(p.get("doc"), p.get("tipo_pessoa"))
            pcur = self.b.con.execute(
                "INSERT INTO partes(lancamento_id, caso_id, papel, ordem, chave_od, nome, doc, doc_tipo, nome_norm, doc_norm, banco, agencia, "
                "conta, tipo_conta, pix_chave, pix_tipo, pix_id, comentario, valor_centavos, valor_original, observacao, "
                "fonte_id, local, linha, bruto_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (lid, self.caso_id, papel, i + 1, p.get("chave_od"), p.get("nome"), p.get("doc"), doc_tipo,
                 util.normalizar_nome(p.get("nome")) or None, util.norm_doc(p.get("doc")),
                 p.get("banco"), p.get("agencia"), p.get("conta"), p.get("tipo_conta"), p.get("pix_chave"),
                 p.get("pix_tipo"), p.get("pix_id"), p.get("comentario"), p.get("valor_centavos"),
                 p.get("valor_original"), p.get("observacao"), p.get("fonte_id") or self.fonte["id"],
                 p.get("local", local), p.get("linha", linha), util.json_dump(p.get("bruto") or {})))
            pid = pcur.lastrowid
            self.rel["partes"] += 1
            pl, pn = p.get("local", local), p.get("linha", linha)
            self._ident("nome", p.get("nome"), "partes", pid, pl, pn, papel)
            self._ident("doc", p.get("doc"), "partes", pid, pl, pn, papel)
            self._ident("banco", p.get("banco"), "partes", pid, pl, pn, papel)
            self._ident("conta", self._conta_txt(p.get("banco"), p.get("agencia"), p.get("conta")), "partes", pid, pl, pn, papel)
            self._ident("pix", p.get("pix_chave"), "partes", pid, pl, pn, papel)
            self._ident("pix_id", p.get("pix_id"), "partes", pid, pl, pn, papel)
        self._passo()
        return lid

    def acesso(self, d):
        cur = self.b.con.execute(
            "INSERT INTO acessos(caso_id, importacao_id, fonte_id, local, linha, data, hora, fuso, data_original, ip, "
            "porta, latitude, longitude, precisao, cidade, uf, pais, endereco, dispositivo, sistema, evento, nome, doc, "
            "telefone, email, banco, conta, bruto_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.caso_id, self.imp_id, self.fonte["id"], d.get("local"), d.get("linha"), d.get("data"), d.get("hora"),
             d.get("fuso"), d.get("data_original"), d.get("ip"), d.get("porta"), d.get("latitude"), d.get("longitude"),
             d.get("precisao"), d.get("cidade"), d.get("uf"), d.get("pais"), d.get("endereco"), d.get("dispositivo"),
             d.get("sistema"), d.get("evento"), d.get("nome"), d.get("doc"), d.get("telefone"), d.get("email"),
             d.get("banco"), d.get("conta"), util.json_dump(d.get("bruto") or {})))
        aid = cur.lastrowid
        self.rel["acessos"] += 1
        loc, ln = d.get("local"), d.get("linha")
        self._ident("ip", d.get("ip"), "acessos", aid, loc, ln, "acesso")
        if d.get("latitude") and d.get("longitude"):
            self._ident("coordenada", "%s,%s" % (d["latitude"], d["longitude"]), "acessos", aid, loc, ln, "acesso")
        if d.get("cidade") or d.get("uf"):
            self._ident("cidade", " / ".join(x for x in (d.get("cidade"), d.get("uf")) if x), "acessos", aid, loc, ln, "acesso")
        self._ident("dispositivo", d.get("dispositivo"), "acessos", aid, loc, ln, "acesso")
        self._ident("nome", d.get("nome"), "acessos", aid, loc, ln, "acesso")
        self._ident("doc", d.get("doc"), "acessos", aid, loc, ln, "acesso")
        self._ident("telefone", d.get("telefone"), "acessos", aid, loc, ln, "acesso")
        self._ident("email", d.get("email"), "acessos", aid, loc, ln, "acesso")
        self._ident("banco", d.get("banco"), "acessos", aid, loc, ln, "acesso")
        self._ident("data", d.get("data"), "acessos", aid, loc, ln, "acesso")
        self._passo()
        return aid

    def titular(self, d):
        doc_tipo = None
        if d.get("doc"):
            doc_tipo, _ = util.classificar_documento(d.get("doc"), d.get("tipo_pessoa"))
        cur = self.b.con.execute(
            "INSERT INTO titulares(caso_id, importacao_id, fonte_id, remessa_id, local, linha, banco, agencia, conta, "
            "tipo_conta, tipo_vinculo, pessoa_investigada, tipo_pessoa, doc, doc_tipo, nome, endereco, cidade, uf, cep, "
            "telefone, email, dispositivo, data_inicio, data_fim, bruto_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.caso_id, self.imp_id, self.fonte["id"], self.remessa_id, d.get("local"), d.get("linha"), d.get("banco"),
             d.get("agencia"), d.get("conta"), d.get("tipo_conta"), d.get("tipo_vinculo"), d.get("pessoa_investigada"),
             d.get("tipo_pessoa"), d.get("doc"), doc_tipo, d.get("nome"), d.get("endereco"), d.get("cidade"),
             d.get("uf"), d.get("cep"), d.get("telefone"), d.get("email"), d.get("dispositivo"), d.get("data_inicio"),
             d.get("data_fim"), util.json_dump(d.get("bruto") or {})))
        tid = cur.lastrowid
        self.rel["titulares"] += 1
        loc, ln = d.get("local"), d.get("linha")
        papel = "cadastro:" + (d.get("tipo_vinculo") or "")
        self._ident("nome", d.get("nome"), "titulares", tid, loc, ln, papel)
        self._ident("doc", d.get("doc"), "titulares", tid, loc, ln, papel)
        self._ident("banco", d.get("banco"), "titulares", tid, loc, ln, papel)
        self._ident("conta", self._conta_txt(d.get("banco"), d.get("agencia"), d.get("conta")), "titulares", tid, loc, ln, papel)
        self._ident("telefone", d.get("telefone"), "titulares", tid, loc, ln, papel)
        for em in str(d.get("email") or "").split(";"):
            self._ident("email", em.strip(), "titulares", tid, loc, ln, papel)
        self._ident("dispositivo", d.get("dispositivo"), "titulares", tid, loc, ln, papel)
        if d.get("cidade") or d.get("uf"):
            self._ident("cidade", " / ".join(x for x in (d.get("cidade"), d.get("uf")) if x), "titulares", tid, loc, ln, papel)
        self._passo()
        return tid

    def ident_texto(self, texto, tabela, reg_id, local, linha, papel="texto"):
        for tipo, original, _ in identificadores.extrair(texto):
            self._ident(tipo, original, tabela, reg_id, local, linha, papel)

    # ------------------------------------------------------------ finalização
    def _duplicatas(self):
        if not self.ids_lanc:
            return 0
        con = self.b.con
        ini, fim = min(self.ids_lanc), max(self.ids_lanc)
        n = 0
        # Cada registro é comparado só com o anterior equivalente mais próximo, para não gerar
        # pares em quantidade quadrática quando há muitas linhas iguais (ex.: tarifas).
        regras = [
            ("conteudo_identico",
             "SELECT a.id AS b_id, (SELECT MAX(o.id) FROM lancamentos o WHERE o.caso_id=a.caso_id "
             "AND o.hash_conteudo=a.hash_conteudo AND o.id < a.id AND o.situacao!='rejeitado') AS a_id "
             "FROM lancamentos a WHERE a.importacao_id=? AND a.id BETWEEN ? AND ? AND a.situacao!='rejeitado'",
             "mesmos data, valor, natureza, conta, documento, descrição e contrapartes"),
            ("dois_lados",
             "SELECT DISTINCT a.id AS b_id, o.id AS a_id FROM lancamentos a "
             "JOIN partes pa ON pa.lancamento_id=a.id AND pa.doc_norm IS NOT NULL "
             "JOIN lancamentos o INDEXED BY ix_lanc_tdoc2 ON o.caso_id=a.caso_id AND o.titular_doc_norm=pa.doc_norm AND o.id!=a.id "
             "AND o.data=a.data AND o.valor_centavos=a.valor_centavos AND o.natureza!=a.natureza AND o.situacao='aceito' "
             "WHERE a.importacao_id=? AND a.id BETWEEN ? AND ? AND a.situacao='aceito' LIMIT 200000",
             "débito de uma conta e crédito de outra com mesma data e valor, contraparte = titular da outra conta"),
        ]
        for criterio, sql, detalhe in regras:
            for r in con.execute(sql, (self.imp_id, ini, fim)).fetchall():
                if r["a_id"] is None:
                    continue
                a, b_ = sorted((r["a_id"], r["b_id"]))
                cur = con.execute("INSERT OR IGNORE INTO duplicatas(caso_id, lanc_a, lanc_b, criterio, detalhe) "
                                  "VALUES (?,?,?,?,?)", (self.caso_id, a, b_, criterio, detalhe))
                n += cur.rowcount
        n += self._mesma_conta_outro_arquivo()
        return n

    def _mesma_conta_outro_arquivo(self):
        """Mesma conta, data, valor e natureza em outro arquivo/aba: pareia com o registro mais
        recente de cada outro arquivo/aba (custo linear, sem pares quadráticos)."""
        con = self.b.con
        chaves = con.execute("SELECT DISTINCT data, valor_centavos, natureza FROM lancamentos WHERE importacao_id=? "
                             "AND situacao='aceito' AND data IS NOT NULL", (self.imp_id,)).fetchall()
        n = 0
        detalhe = "mesma conta, data, valor e natureza em arquivo ou aba diferente (possível repetição entre abas/arquivos)"
        for k in chaves:
            linhas = con.execute("SELECT id, importacao_id, hash_conteudo, fonte_id, local, conta, titular_doc_norm FROM lancamentos "
                                 "WHERE caso_id=? AND data=? AND valor_centavos=? AND natureza=? AND situacao='aceito' ORDER BY id",
                                 (self.caso_id, k["data"], k["valor_centavos"], k["natureza"])).fetchall()
            ultimo = {}
            for r in linhas:
                conta = (r["conta"] or "", r["titular_doc_norm"] or "")
                grupo = (r["fonte_id"], r["local"] or "")
                if r["importacao_id"] == self.imp_id:
                    cands = [u for g, u in ultimo.get(conta, {}).items() if g != grupo and u["hash_conteudo"] != r["hash_conteudo"]]
                    if cands:
                        o = max(cands, key=lambda x: x["id"])
                        cur = con.execute("INSERT OR IGNORE INTO duplicatas(caso_id, lanc_a, lanc_b, criterio, detalhe) "
                                          "VALUES (?,?,?,?,?)", (self.caso_id, o["id"], r["id"], "mesma_conta_data_valor", detalhe))
                        n += cur.rowcount
                ultimo.setdefault(conta, {})[grupo] = r
        return n

    def finalizar(self, controle=None):
        try:
            self.rel["duplicatas"] = self._duplicatas()
            if self.rel["duplicatas"]:
                self.aviso("Foram apontadas duplicatas prováveis. Nada foi descartado: revise na aba Duplicatas.")
            if controle:
                self.rel["controle"] = conferir_controle(self.rel, controle)
            self.b.con.execute(
                "UPDATE importacoes SET aceitos=?, pendentes=?, rejeitados=?, duplicatas=?, relatorio_json=?, estado='concluida' "
                "WHERE id=?", (self.rel["aceitos"], self.rel["pendentes"], self.rel["rejeitados"], self.rel["duplicatas"],
                               util.json_dump(self.rel), self.imp_id))
            self._fechar(True)
        except Exception:
            self._fechar(False)
            raise
        auditoria.registrar(self.b, self.caso_id, self.usuario, "importacao",
                            {"importacao_id": self.imp_id, "fonte_id": self.fonte["id"], "sha256": self.fonte["sha256"],
                             "aceitos": self.rel["aceitos"], "pendentes": self.rel["pendentes"],
                             "rejeitados": self.rel["rejeitados"], "duplicatas": self.rel["duplicatas"]})
        self.rel["importacao_id"] = self.imp_id
        return self.rel

    def abortar(self, erro):
        try:
            self._fechar(False)
        except Exception:  # noqa: BLE001
            pass
        desfazer(self.b, self.imp_id, self.usuario, "falha: %s" % erro)


def conferir_controle(rel, controle):
    res = {"itens": [], "ok": True}
    for chave, rotulo, obtido in (("creditos", "Créditos aceitos", rel["totais_aceitos"]["C"]),
                                  ("debitos", "Débitos aceitos", rel["totais_aceitos"]["D"])):
        txt = str(controle.get(chave) or "").strip()
        if not txt:
            continue
        esperado = util.parse_valor(txt)["centavos"]
        ok = esperado == obtido
        res["ok"] &= ok
        res["itens"].append({"item": rotulo, "esperado": util.formatar_centavos(esperado),
                             "obtido": util.formatar_centavos(obtido), "ok": ok})
    qtd = str(controle.get("quantidade") or "").strip()
    if qtd:
        ok = qtd.isdigit() and int(qtd) == rel["aceitos"] + rel["pendentes"] + rel["rejeitados"]
        res["ok"] &= ok
        res["itens"].append({"item": "Quantidade de lançamentos lidos", "esperado": qtd,
                             "obtido": str(rel["aceitos"] + rel["pendentes"] + rel["rejeitados"]), "ok": ok})
    return res


def desfazer(b, importacao_id, usuario, motivo="desfeita pelo usuário"):
    imp = b.q1("SELECT * FROM importacoes WHERE id=?", (importacao_id,))
    if not imp:
        raise KeyError("importação inexistente")
    with b.transacao():
        con = b.con
        con.execute("DELETE FROM duplicatas WHERE lanc_a IN (SELECT id FROM lancamentos WHERE importacao_id=?) "
                    "OR lanc_b IN (SELECT id FROM lancamentos WHERE importacao_id=?)", (importacao_id, importacao_id))
        con.execute("DELETE FROM partes WHERE lancamento_id IN (SELECT id FROM lancamentos WHERE importacao_id=?)", (importacao_id,))
        con.execute("DELETE FROM lancamentos WHERE importacao_id=?", (importacao_id,))
        con.execute("DELETE FROM acessos WHERE importacao_id=?", (importacao_id,))
        con.execute("DELETE FROM titulares WHERE importacao_id=?", (importacao_id,))
        con.execute("DELETE FROM ocorrencias_ident WHERE importacao_id=?", (importacao_id,))
        con.execute("UPDATE importacoes SET estado='desfeita' WHERE id=?", (importacao_id,))
    auditoria.registrar(b, imp["caso_id"], usuario, "importacao_desfeita", {"importacao_id": importacao_id, "motivo": motivo})
