"""Relatório de Inteligência Financeira (RIF).

RIF é comunicação de inteligência, não extrato: este módulo nunca cria lançamentos. As
comunicações, envolvidos e ocorrências ficam em tabelas próprias, com fonte e linha, e os
identificadores aparecem na Pesquisa geral marcados como "RIF".
"""

import os
import zipfile

from . import adaptadores, auditoria, protocolo, util

RESTRICAO_PADRAO = ("RIF: documento de inteligência financeira com sigilo. Não é prova de movimentação nem de "
                    "ilicitude; não pode ser somado a extratos. Uso restrito à investigação autorizada.")

COLUNAS = {
    "comunicacoes": {
        "id_comunicacao": ["IDCOMUNICACAO"], "numero_ocorrencia": ["NUMEROOCORRENCIABC", "NUMEROOCORRENCIA"],
        "data_recebimento": ["DATADORECEBIMENTO", "DATARECEBIMENTO"], "data_operacao": ["DATADAOPERACAO", "DATAOPERACAO"],
        "data_fim": ["DATAFIMFATO", "DATAFIM"], "comunicante_doc": ["CPFCNPJCOMUNICANTE"],
        "comunicante_nome": ["NOMECOMUNICANTE"], "cidade": ["CIDADEAGENCIA"], "uf": ["UFAGENCIA"],
        "agencia": ["NUMEROAGENCIA", "NOMEAGENCIA"], "informacoes": ["INFORMACOESADICIONAIS"],
        "segmento": ["CODIGOSEGMENTO", "SEGMENTO"],
    },
    "envolvidos": {
        "id_comunicacao": ["IDCOMUNICACAO"], "doc": ["CPFCNPJENVOLVIDO", "CPFCNPJ"], "nome": ["NOMEENVOLVIDO", "NOME"],
        "tipo_envolvido": ["TIPOENVOLVIDO"], "agencia": ["AGENCIAENVOLVIDO"], "conta": ["CONTAENVOLVIDO"],
        "data_abertura": ["DATAABERTURACONTA"], "data_atualizacao": ["DATAATUALIZACAOCONTA"],
    },
    "ocorrencias": {"id_comunicacao": ["IDCOMUNICACAO"], "ocorrencia": ["OCORRENCIA"]},
}


def _chave(h):
    return util.normalizar_cabecalho(h).replace("_", "")


def tipo_arquivo(cabecalho):
    k = set(_chave(h) for h in cabecalho)
    if "OCORRENCIA" in k:
        return "ocorrencias"
    if k & {"CPFCNPJENVOLVIDO", "NOMEENVOLVIDO", "TIPOENVOLVIDO"}:
        return "envolvidos"
    if k & {"NOMECOMUNICANTE", "CPFCNPJCOMUNICANTE", "DATADORECEBIMENTO", "INFORMACOESADICIONAIS"}:
        return "comunicacoes"
    return None


def _resolver_rif_id(imp, opcoes):
    """Reusa o RIF do lote (comunicações + envolvidos + ocorrências em arquivos separados)."""
    rid = opcoes.get("rif_id")
    if rid not in (None, "", 0, "0"):
        r = imp.b.q1("SELECT id FROM rif_relatorios WHERE id=? AND caso_id=?", (int(rid), imp.caso_id))
        if not r:
            raise ValueError("O RIF indicado não pertence a este caso.")
        return r["id"]
    if opcoes.get("anexar_ao_ultimo"):
        r = imp.b.q1("SELECT id FROM rif_relatorios WHERE caso_id=? ORDER BY id DESC LIMIT 1", (imp.caso_id,))
        if r:
            return r["id"]
    return None


def _tabelas(caminho, tipo, nome):
    """Lista de (nome_local, cabecalho, linhas[(n, dict)])."""
    _, gen, local = adaptadores.ler_tabela(caminho, tipo)
    cab, linhas = None, []
    for n, campos in gen:
        if cab is None:
            if sum(1 for c in campos if str(c).strip()) >= 2:
                cab = [str(c).strip() for c in campos]
            continue
        if not any(str(c).strip() for c in campos):
            continue
        linhas.append((n, {cab[i]: (campos[i] if i < len(campos) else "") for i in range(len(cab))}))
    return [(local or nome, cab or [], linhas)]


def importar(imp, caminho, tipo_fonte, nome_fonte, opcoes, pasta_tmp):
    tabelas = []
    if tipo_fonte == "zip":
        with zipfile.ZipFile(caminho) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                ext = os.path.splitext(info.filename.lower())[1]
                if ext not in (".csv", ".txt", ".xlsx"):
                    continue
                destino = os.path.join(pasta_tmp, "rif_%d_%s" % (imp.imp_id, os.path.basename(info.filename)))
                with z.open(info) as src, open(destino, "wb") as dst:
                    dst.write(src.read())
                try:
                    for _, cab, linhas in _tabelas(destino, "xlsx" if ext == ".xlsx" else "delimitado", info.filename):
                        tabelas.append((info.filename, cab, linhas))
                finally:
                    os.remove(destino)
    else:
        tabelas = _tabelas(caminho, tipo_fonte, nome_fonte)

    rif_id = _resolver_rif_id(imp, opcoes)
    if rif_id is None:
        rif_id = imp.b.con.execute(
            "INSERT INTO rif_relatorios(caso_id, fonte_id, numero, observacao, restricao, criado_em, criado_por) VALUES (?,?,?,?,?,?,?)",
            (imp.caso_id, imp.fonte["id"], opcoes.get("numero_rif"), opcoes.get("observacao"),
             opcoes.get("restricao") or RESTRICAO_PADRAO, util.agora_iso(), imp.usuario)).lastrowid
    elif opcoes.get("numero_rif"):
        imp.b.con.execute("UPDATE rif_relatorios SET numero=COALESCE(NULLIF(numero,''), ?) WHERE id=?",
                          (opcoes.get("numero_rif"), rif_id))
    col_valor = opcoes.get("coluna_valor")
    reconhecidas = 0
    n_com = n_env = n_oc = 0
    for local, cab, linhas in tabelas:
        tipo = tipo_arquivo(cab)
        if tipo is None:
            imp.aviso("Arquivo %s não reconhecido como comunicações, envolvidos ou ocorrências; guardado apenas como fonte." % local)
            continue
        reconhecidas += 1
        mapa = {}
        for campo, sins in COLUNAS[tipo].items():
            for h in cab:
                if _chave(h) in sins:
                    mapa[campo] = h
                    break
        for n, reg in linhas:
            g = {c: str(reg.get(h, "")).strip() or None for c, h in mapa.items()}
            if tipo == "comunicacoes":
                valor, valor_orig = None, None
                if col_valor and col_valor in reg:
                    valor_orig = reg[col_valor]
                    valor = util.parse_valor(valor_orig)["centavos"]
                cid = imp.b.con.execute(
                    "INSERT INTO rif_comunicacoes(rif_id, caso_id, fonte_id, local, linha, id_comunicacao, numero_ocorrencia, "
                    "data_recebimento, data_operacao, data_fim, comunicante_doc, comunicante_nome, segmento, cidade, uf, "
                    "agencia, valor_centavos, valor_original, informacoes, bruto_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rif_id, imp.caso_id, imp.fonte["id"], local, n, g.get("id_comunicacao"), g.get("numero_ocorrencia"),
                     util.parse_data(g.get("data_recebimento"))["data"] or g.get("data_recebimento"),
                     util.parse_data(g.get("data_operacao"))["data"] or g.get("data_operacao"),
                     util.parse_data(g.get("data_fim"))["data"] or g.get("data_fim"),
                     g.get("comunicante_doc"), g.get("comunicante_nome"), g.get("segmento"), g.get("cidade"), g.get("uf"),
                     g.get("agencia"), valor, valor_orig, g.get("informacoes"), util.json_dump(reg))).lastrowid
                imp._ident("nome", g.get("comunicante_nome"), "rif_comunicacoes", cid, local, n, "RIF comunicante")
                imp._ident("doc", g.get("comunicante_doc"), "rif_comunicacoes", cid, local, n, "RIF comunicante")
                if g.get("cidade") or g.get("uf"):
                    imp._ident("cidade", " / ".join(x for x in (g.get("cidade"), g.get("uf")) if x), "rif_comunicacoes", cid, local, n, "RIF")
                if g.get("informacoes"):
                    imp.ident_texto(g["informacoes"], "rif_comunicacoes", cid, local, n, "RIF informações adicionais")
                n_com += 1
            elif tipo == "envolvidos":
                doc_tipo = util.classificar_documento(g.get("doc"))[0] if g.get("doc") else None
                eid = imp.b.con.execute(
                    "INSERT INTO rif_envolvidos(rif_id, caso_id, fonte_id, local, linha, id_comunicacao, doc, doc_tipo, nome, "
                    "tipo_envolvido, agencia, conta, data_abertura, data_atualizacao, bruto_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rif_id, imp.caso_id, imp.fonte["id"], local, n, g.get("id_comunicacao"), g.get("doc"), doc_tipo,
                     g.get("nome"), g.get("tipo_envolvido"), g.get("agencia"), g.get("conta"), g.get("data_abertura"),
                     g.get("data_atualizacao"), util.json_dump(reg))).lastrowid
                papel = "RIF envolvido: %s" % (g.get("tipo_envolvido") or "?")
                imp._ident("nome", g.get("nome"), "rif_envolvidos", eid, local, n, papel)
                imp._ident("doc", g.get("doc"), "rif_envolvidos", eid, local, n, papel)
                if g.get("conta"):
                    imp._ident("conta", "AG %s CONTA %s" % (g.get("agencia") or "?", g.get("conta")), "rif_envolvidos", eid, local, n, papel)
                n_env += 1
            else:
                imp.b.con.execute(
                    "INSERT INTO rif_ocorrencias(rif_id, caso_id, fonte_id, local, linha, id_comunicacao, ocorrencia, bruto_json) "
                    "VALUES (?,?,?,?,?,?,?,?)", (rif_id, imp.caso_id, imp.fonte["id"], local, n, g.get("id_comunicacao"),
                                                 g.get("ocorrencia"), util.json_dump(reg)))
                n_oc += 1
            imp._passo()
    if not reconhecidas:
        raise ValueError("Nenhum arquivo de comunicações, envolvidos ou ocorrências foi reconhecido.")
    imp.aviso(RESTRICAO_PADRAO)
    if n_com and not col_valor:
        imp.aviso("Nenhuma coluna de valor da comunicação foi indicada; valores do RIF não foram lidos.")
    imp.rel["rif_id"] = rif_id
    imp.rel["rif_comunicacoes"] = n_com
    imp.rel["rif_envolvidos"] = n_env
    imp.rel["rif_ocorrencias"] = n_oc
    return rif_id


def adicionar_citacao(b, caso_id, rif_id, fonte_id, pagina, trecho, id_comunicacao, usuario):
    auditoria.exigir(b, caso_id, usuario, "analista")
    cid = b.x("INSERT INTO rif_citacoes(rif_id, caso_id, fonte_id, pagina, trecho, id_comunicacao, criado_por, criado_em) "
              "VALUES (?,?,?,?,?,?,?,?)", (rif_id, caso_id, fonte_id, pagina, trecho, id_comunicacao, usuario, util.agora_iso()))
    auditoria.registrar(b, caso_id, usuario, "rif_citacao", {"rif_id": rif_id, "fonte_id": fonte_id, "pagina": pagina})
    return cid


def resumo(b, caso_id):
    ids = protocolo.escopo(b, caso_id)
    w, par = util.sql_in("r.caso_id", ids)
    rifs = b.q("SELECT r.*, f.nome_original, f.sha256 FROM rif_relatorios r JOIN fontes f ON f.id=r.fonte_id WHERE " + w, par)
    for r in rifs:
        r["comunicacoes"] = b.q("SELECT * FROM rif_comunicacoes WHERE rif_id=? ORDER BY id LIMIT 2000", (r["id"],))
        r["envolvidos"] = b.q("SELECT * FROM rif_envolvidos WHERE rif_id=? ORDER BY id LIMIT 5000", (r["id"],))
        r["ocorrencias"] = b.q("SELECT * FROM rif_ocorrencias WHERE rif_id=? ORDER BY id LIMIT 5000", (r["id"],))
        r["citacoes"] = b.q("SELECT * FROM rif_citacoes WHERE rif_id=? ORDER BY id", (r["id"],))
        docs = set(util.so_digitos(e["doc"]) for e in r["envolvidos"] if e.get("doc"))
        r["envolvidos_com_movimentacao"] = []
        for d in sorted(docs):
            if not d:
                continue
            wo, po = util.sql_in("caso_id", ids)
            n = b.q1("SELECT COUNT(*) AS n FROM ocorrencias_ident WHERE " + wo + " AND tipo IN ('cpf','cnpj') AND valor_norm=? "
                     "AND tabela IN ('lancamentos','partes')", list(po) + [d])["n"]
            if n:
                r["envolvidos_com_movimentacao"].append({"doc": d, "ocorrencias_em_extratos": n})
        r["restricao"] = r["restricao"] or RESTRICAO_PADRAO
    return rifs

