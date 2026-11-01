"""Pesquisa com filtros de múltipla seleção, totais e rankings determinísticos.

Regras de cálculo:
- Totais incluem apenas lançamentos 'aceito' e não consolidados como duplicata confirmada.
- Pendentes e rejeitados aparecem separados, fora dos totais.
- Rankings por contraparte usam o valor da parcela quando as parcelas conferem; quando há uma
  única contraparte sem valor, usam o valor do lançamento; parcelas divergentes/incompletas vão
  para a linha "não distribuído" (o valor nunca é repetido nem repartido).
"""

import csv
import io

from . import identificadores, util

# chave -> (rótulo, tipo, expressão de valor, expressão de rótulo)
FACETAS = [
    ("natureza", "Natureza", "l", "COALESCE(l.natureza,'(sem natureza)')", None),
    ("situacao", "Situação na importação", "l", "l.situacao", None),
    ("pessoa_doc", "CPF/CNPJ (titular ou contraparte)", "u_doc", None, None),
    ("pessoa_nome", "Nome (titular ou contraparte)", "u_nome", None, None),
    ("titular_doc", "Titular - CPF/CNPJ", "l", "COALESCE(l.titular_doc_norm,'(não informado)')", "MIN(COALESCE(l.titular_doc,'(não informado)'))"),
    ("titular_nome", "Titular - nome", "l", "COALESCE(l.titular_nome_norm,'(não informado)')", "MIN(COALESCE(l.titular_nome,'(não informado)'))"),
    ("conta", "Conta (banco/agência/conta)", "l", "COALESCE(l.banco,'?')||' | ag '||COALESCE(l.agencia,'?')||' | conta '||COALESCE(l.conta,'?')", None),
    ("banco", "Banco / instituição da conta", "l", "COALESCE(l.banco,'(não informado)')", None),
    ("cp_doc", "Contraparte - CPF/CNPJ", "p", "COALESCE(p.doc_norm,'(não informado)')", "MIN(COALESCE(p.doc,'(não informado)'))"),
    ("cp_nome", "Contraparte - nome", "p", "COALESCE(p.nome_norm,'(não informado)')", "MIN(COALESCE(p.nome,'(não informado)'))"),
    ("cp_banco", "Contraparte - banco", "p", "COALESCE(p.banco,'(não informado)')", None),
    ("cp_conta", "Contraparte - conta", "p", "COALESCE(p.banco,'?')||' | ag '||COALESCE(p.agencia,'?')||' | conta '||COALESCE(p.conta,'?')", None),
    ("pix", "Chave PIX (transação ou contraparte)", "u_pix", None, None),
    ("tipo_operacao", "Tipo de operação", "l", "COALESCE(l.tipo_operacao,'(não informado)')", None),
    ("descricao", "Descrição / histórico", "l", "COALESCE(l.descricao,'(vazia)')", None),
    ("mes", "Mês", "l", "COALESCE(substr(l.data,1,7),'(sem data)')", None),
    ("data", "Data", "l", "COALESCE(l.data,'(sem data)')", None),
    ("ip", "IP da transação", "l", "COALESCE(l.ip,'(não informado)')", None),
    ("cidade", "Cidade/UF da transação", "l", "COALESCE(l.cidade,'?')||' / '||COALESCE(l.uf,'?')", None),
    ("status_origem", "Status informado pelo banco", "l", "COALESCE(l.status_origem,'(não informado)')", None),
    ("fonte", "Arquivo de origem", "l", "CAST(l.fonte_id AS TEXT)", None),
    ("remessa", "Remessa", "l", "COALESCE(CAST(l.remessa_id AS TEXT),'(sem remessa)')", None),
]
FACETA = {f[0]: f for f in FACETAS}


def _where(caso_id, filtros, exceto=None):
    cond = ["l.caso_id=?"]
    par = [caso_id]
    f = filtros or {}
    for chave, (_, _, tipo, expr, _) in FACETA.items():
        vals = f.get(chave)
        if not vals or chave == exceto:
            continue
        ph = ",".join("?" * len(vals))
        if tipo == "l":
            cond.append("%s IN (%s)" % (expr, ph))
            par += list(vals)
        elif tipo == "p":
            cond.append("EXISTS (SELECT 1 FROM partes p WHERE p.lancamento_id=l.id AND %s IN (%s))" % (expr, ph))
            par += list(vals)
        elif tipo == "u_doc":
            cond.append("(l.titular_doc_norm IN (%s) OR EXISTS (SELECT 1 FROM partes p WHERE p.lancamento_id=l.id AND p.doc_norm IN (%s)))" % (ph, ph))
            par += list(vals) * 2
        elif tipo == "u_nome":
            cond.append("(l.titular_nome_norm IN (%s) OR EXISTS (SELECT 1 FROM partes p WHERE p.lancamento_id=l.id AND p.nome_norm IN (%s)))" % (ph, ph))
            par += list(vals) * 2
        elif tipo == "u_pix":
            cond.append("(l.pix_chave IN (%s) OR EXISTS (SELECT 1 FROM partes p WHERE p.lancamento_id=l.id AND p.pix_chave IN (%s)))" % (ph, ph))
            par += list(vals) * 2
    if f.get("data_ini"):
        cond.append("l.data >= ?")
        par.append(f["data_ini"])
    if f.get("data_fim"):
        cond.append("l.data <= ?")
        par.append(f["data_fim"])
    for k, op in (("valor_min", ">="), ("valor_max", "<=")):
        if str(f.get(k) or "").strip():
            c = util.parse_valor(f[k])["centavos"]
            if c is not None:
                cond.append("l.valor_centavos %s ?" % op)
                par.append(c)
    if str(f.get("texto") or "").strip():
        t = "%" + util.normalizar_nome(f["texto"]) + "%"
        cond.append("(l.titular_nome_norm LIKE ? OR upper(COALESCE(l.descricao,'')) LIKE ? OR COALESCE(l.titular_doc_norm,'') LIKE ? "
                    "OR EXISTS (SELECT 1 FROM partes p WHERE p.lancamento_id=l.id AND (p.nome_norm LIKE ? OR COALESCE(p.doc_norm,'') LIKE ?)))")
        par += [t, t, "%" + util.so_digitos(f["texto"]) + "%" if util.so_digitos(f["texto"]) else t, t,
                "%" + util.so_digitos(f["texto"]) + "%" if util.so_digitos(f["texto"]) else t]
    if not f.get("incluir_consolidados"):
        cond.append("l.consolidado_em IS NULL")
    return " AND ".join(cond), par


def descrever_filtros(b, filtros):
    out = []
    f = filtros or {}
    for chave, (_, rotulo, *_r) in FACETA.items():
        if f.get(chave):
            vals = f[chave]
            if chave == "fonte":
                nomes = []
                for v in vals:
                    fo = b.q1("SELECT nome_original FROM fontes WHERE id=?", (int(v),))
                    nomes.append(fo["nome_original"] if fo else v)
                vals = nomes
            elif chave in ("pessoa_doc", "titular_doc", "cp_doc"):
                vals = [util.formatar_documento(v) for v in vals]
            out.append("%s: %s" % (rotulo, "; ".join(str(v) for v in vals)))
    if f.get("data_ini") or f.get("data_fim"):
        out.append("Período: %s a %s" % (f.get("data_ini") or "início", f.get("data_fim") or "fim"))
    if f.get("valor_min") or f.get("valor_max"):
        out.append("Valor: %s a %s" % (f.get("valor_min") or "-", f.get("valor_max") or "-"))
    if f.get("texto"):
        out.append("Texto: %s" % f["texto"])
    return out or ["Sem filtros (todos os registros do caso)"]


def facetas(b, caso_id, filtros, limite=5000):
    """Para cada faceta, todos os valores possíveis (até `limite`) com contagem sob os demais filtros."""
    res = []
    fontes = {str(r["id"]): r["nome_original"] for r in b.q("SELECT id, nome_original FROM fontes WHERE caso_id=?", (caso_id,))}
    remessas = {str(r["id"]): r["rotulo"] for r in b.q("SELECT id, rotulo FROM remessas WHERE caso_id=?", (caso_id,))}
    for chave, rotulo, tipo, expr, expr_rot in FACETAS:
        w, par = _where(caso_id, filtros, exceto=chave)
        if tipo == "l":
            sql = ("SELECT %s AS v, %s AS r, COUNT(*) AS n, SUM(CASE WHEN l.situacao='aceito' THEN l.valor_centavos ELSE 0 END) AS s "
                   "FROM lancamentos l WHERE %s GROUP BY v ORDER BY n DESC, v LIMIT %d") % (expr, expr_rot or "NULL", w, limite)
        elif tipo == "p":
            sql = ("SELECT %s AS v, %s AS r, COUNT(DISTINCT l.id) AS n, NULL AS s FROM lancamentos l JOIN partes p ON p.lancamento_id=l.id "
                   "WHERE %s GROUP BY v ORDER BY n DESC, v LIMIT %d") % (expr, expr_rot or "NULL", w, limite)
        else:
            col_l, col_p, col_lr, col_pr = {
                "u_doc": ("l.titular_doc_norm", "p.doc_norm", "l.titular_doc", "p.doc"),
                "u_nome": ("l.titular_nome_norm", "p.nome_norm", "l.titular_nome", "p.nome"),
                "u_pix": ("l.pix_chave", "p.pix_chave", "l.pix_chave", "p.pix_chave"),
            }[tipo]
            sql = ("SELECT v, MIN(r) AS r, COUNT(DISTINCT lid) AS n, NULL AS s FROM ("
                   "SELECT %s AS v, %s AS r, l.id AS lid FROM lancamentos l WHERE %s AND %s IS NOT NULL "
                   "UNION ALL SELECT %s, %s, l.id FROM lancamentos l JOIN partes p ON p.lancamento_id=l.id WHERE %s AND %s IS NOT NULL"
                   ") GROUP BY v ORDER BY n DESC, v LIMIT %d") % (col_l, col_lr, w, col_l, col_p, col_pr, w, col_p, limite)
            par = par + par
        valores = []
        for r in b.q(sql, par):
            rot = r["r"] or r["v"]
            if chave == "fonte":
                rot = fontes.get(r["v"], r["v"])
            elif chave == "remessa":
                rot = remessas.get(r["v"], r["v"])
            elif chave in ("pessoa_doc", "titular_doc", "cp_doc") and r["v"] and util.so_digitos(r["v"]) == r["v"]:
                rot = util.formatar_documento(r["v"])
            valores.append({"valor": r["v"], "rotulo": rot, "n": r["n"], "soma": r["s"]})
        res.append({"chave": chave, "rotulo": rotulo, "valores": valores, "truncado": len(valores) >= limite})
    return res


def _ranking(b, w, par, natureza, filtros, limite=10):
    sql = ("SELECT COALESCE(p.doc_norm, 'NOME:'||COALESCE(p.nome_norm,'?')) AS k, MIN(p.nome) AS nome, MIN(p.doc) AS doc, "
           "COUNT(DISTINCT l.id) AS n, SUM(CASE WHEN l.parcelas_estado='conferidas' THEN p.valor_centavos ELSE l.valor_centavos END) AS s "
           "FROM lancamentos l JOIN partes p ON p.lancamento_id=l.id "
           "WHERE %s AND l.situacao='aceito' AND l.natureza=? AND l.parcelas_estado IN ('conferidas','unica') "
           "GROUP BY k ORDER BY s DESC LIMIT %d") % (w, limite)
    linhas = b.q(sql, par + [natureza])
    nd = b.q1("SELECT COUNT(*) AS n, COALESCE(SUM(l.valor_centavos),0) AS s FROM lancamentos l WHERE %s AND l.situacao='aceito' "
              "AND l.natureza=? AND l.parcelas_estado IN ('divergentes','incompletas')" % w, par + [natureza])
    sem = b.q1("SELECT COUNT(*) AS n, COALESCE(SUM(l.valor_centavos),0) AS s FROM lancamentos l WHERE %s AND l.situacao='aceito' "
               "AND l.natureza=? AND l.parcelas_estado='sem_parcelas'" % w, par + [natureza])
    return {"itens": [{"nome": r["nome"], "doc": r["doc"], "n": r["n"], "soma": r["s"], "soma_fmt": util.formatar_centavos(r["s"])}
                      for r in linhas],
            "nao_distribuido": {"n": nd["n"], "soma": nd["s"], "soma_fmt": util.formatar_centavos(nd["s"])},
            "sem_contraparte": {"n": sem["n"], "soma": sem["s"], "soma_fmt": util.formatar_centavos(sem["s"])}}


def totais(b, caso_id, filtros):
    w, par = _where(caso_id, filtros)
    t = b.q1("SELECT "
             "COALESCE(SUM(CASE WHEN l.situacao='aceito' AND l.natureza='C' THEN l.valor_centavos END),0) AS cred, "
             "SUM(CASE WHEN l.situacao='aceito' AND l.natureza='C' THEN 1 ELSE 0 END) AS n_cred, "
             "COALESCE(SUM(CASE WHEN l.situacao='aceito' AND l.natureza='D' THEN l.valor_centavos END),0) AS deb, "
             "SUM(CASE WHEN l.situacao='aceito' AND l.natureza='D' THEN 1 ELSE 0 END) AS n_deb, "
             "SUM(CASE WHEN l.situacao='pendente' THEN 1 ELSE 0 END) AS n_pend, "
             "COALESCE(SUM(CASE WHEN l.situacao='pendente' THEN l.valor_centavos END),0) AS pend, "
             "SUM(CASE WHEN l.situacao='rejeitado' THEN 1 ELSE 0 END) AS n_rej, COUNT(*) AS n, "
             "MIN(l.data) AS dmin, MAX(l.data) AS dmax, COUNT(DISTINCT l.fonte_id) AS n_fontes "
             "FROM lancamentos l WHERE " + w, par)
    for k in ("n_cred", "n_deb", "n_pend", "n_rej"):
        t[k] = t[k] or 0
    out = {
        "creditos": t["cred"], "creditos_fmt": util.formatar_centavos(t["cred"]), "n_creditos": t["n_cred"],
        "debitos": t["deb"], "debitos_fmt": util.formatar_centavos(t["deb"]), "n_debitos": t["n_deb"],
        "pendentes": t["pend"], "pendentes_fmt": util.formatar_centavos(t["pend"]), "n_pendentes": t["n_pend"],
        "n_rejeitados": t["n_rej"], "n_registros": t["n"], "periodo": [t["dmin"], t["dmax"]], "n_fontes": t["n_fontes"],
        "origens": _ranking(b, w, par, "C", filtros), "destinos": _ranking(b, w, par, "D", filtros),
        "avisos": [],
    }
    f = filtros or {}
    if f.get("cp_doc") or f.get("cp_nome") or f.get("pessoa_doc") or f.get("pessoa_nome"):
        cond, cpar = [], []
        for chave, col in (("cp_doc", "p.doc_norm"), ("cp_nome", "p.nome_norm"), ("pessoa_doc", "p.doc_norm"), ("pessoa_nome", "p.nome_norm")):
            if f.get(chave):
                cond.append("%s IN (%s)" % (col, ",".join("?" * len(f[chave]))))
                cpar += list(f[chave])
        sql = ("SELECT l.natureza AS nat, SUM(CASE WHEN l.parcelas_estado='conferidas' THEN p.valor_centavos ELSE l.valor_centavos END) AS s "
               "FROM lancamentos l JOIN partes p ON p.lancamento_id=l.id WHERE %s AND l.situacao='aceito' "
               "AND l.parcelas_estado IN ('conferidas','unica') AND (%s) GROUP BY l.natureza") % (w, " OR ".join(cond))
        atrib = {r["nat"]: r["s"] for r in b.q(sql, par + cpar)}
        out["atribuivel_contrapartes"] = {"C": util.formatar_centavos(atrib.get("C", 0)), "D": util.formatar_centavos(atrib.get("D", 0))}
        out["avisos"].append("Com filtro de contraparte, os totais mostram o valor integral dos lançamentos em que ela aparece. "
                             "O valor atribuível às contrapartes selecionadas (somente parcelas conferidas) é %s em créditos e %s em débitos."
                             % (out["atribuivel_contrapartes"]["C"], out["atribuivel_contrapartes"]["D"]))
    contas = b.q("SELECT COALESCE(l.banco,'?')||' | ag '||COALESCE(l.agencia,'?')||' | conta '||COALESCE(l.conta,'?') AS conta, "
                 "MIN(l.titular_nome) AS titular, "
                 "COALESCE(SUM(CASE WHEN l.situacao='aceito' AND l.natureza='C' THEN l.valor_centavos END),0) AS c, "
                 "COALESCE(SUM(CASE WHEN l.situacao='aceito' AND l.natureza='D' THEN l.valor_centavos END),0) AS d, COUNT(*) AS n "
                 "FROM lancamentos l WHERE %s GROUP BY conta ORDER BY n DESC LIMIT 50" % w, par)
    out["por_conta"] = [dict(r, c_fmt=util.formatar_centavos(r["c"]), d_fmt=util.formatar_centavos(r["d"])) for r in contas]
    if len(contas) > 1:
        out["avisos"].append("A seleção reúne %d contas. Se houver transferências entre elas, a mesma operação pode aparecer como "
                             "débito em uma e crédito em outra; o total geral não elimina essa repetição." % len(contas))
    dup = b.q1("SELECT COUNT(*) AS n FROM duplicatas d WHERE d.caso_id=? AND d.estado='pendente' AND "
               "(d.lanc_a IN (SELECT l.id FROM lancamentos l WHERE %s) OR d.lanc_b IN (SELECT l.id FROM lancamentos l WHERE %s))" % (w, w),
               [caso_id] + par + par)
    if dup["n"]:
        out["avisos"].append("%d par(es) de duplicatas prováveis ainda sem revisão envolvem registros desta seleção." % dup["n"])
    if t["n_pend"]:
        out["avisos"].append("%d registro(s) pendente(s) (%s) estão fora dos totais; veja o motivo em Detalhes." % (t["n_pend"], out["pendentes_fmt"]))
    nd = out["origens"]["nao_distribuido"]["n"] + out["destinos"]["nao_distribuido"]["n"]
    if nd:
        out["avisos"].append("%d lançamento(s) com parcelas divergentes ou incompletas não foram distribuídos entre contrapartes." % nd)
    return out


def registros(b, caso_id, filtros, limite=500, deslocamento=0, ordem="data"):
    w, par = _where(caso_id, filtros)
    ordens = {"data": "l.data, l.hora, l.id", "valor": "l.valor_centavos DESC, l.id", "linha": "l.fonte_id, l.local, l.linha"}
    linhas = b.q("SELECT l.id, l.data, l.hora, l.fuso, l.natureza, l.valor_centavos, l.situacao, l.motivo, l.titular_nome, "
                 "l.titular_doc, l.banco, l.agencia, l.conta, l.descricao, l.tipo_operacao, l.pix_chave, l.ip, l.local, l.linha, "
                 "l.fonte_id, l.parcelas_estado, l.status_origem, l.chave_local, f.nome_original AS fonte_nome, f.sha256 "
                 "FROM lancamentos l JOIN fontes f ON f.id=l.fonte_id WHERE %s ORDER BY %s LIMIT ? OFFSET ?"
                 % (w, ordens.get(ordem, ordens["data"])), par + [limite, deslocamento])
    ids = [r["id"] for r in linhas]
    partes = {}
    if ids:
        for p in b.q("SELECT lancamento_id, papel, nome, doc, banco, agencia, conta, pix_chave, valor_centavos FROM partes "
                     "WHERE lancamento_id IN (%s) ORDER BY lancamento_id, ordem" % ",".join("?" * len(ids)), ids):
            partes.setdefault(p["lancamento_id"], []).append(p)
    for r in linhas:
        r["valor_fmt"] = util.formatar_centavos(r["valor_centavos"])
        r["partes"] = partes.get(r["id"], [])
    total = b.q1("SELECT COUNT(*) AS n FROM lancamentos l WHERE " + w, par)["n"]
    return {"linhas": linhas, "total": total, "limite": limite, "deslocamento": deslocamento}


def detalhe(b, lanc_id):
    l = b.q1("SELECT l.*, f.nome_original AS fonte_nome, f.sha256, f.caminho_no_pacote, f.pai_id, r.rotulo AS remessa "
             "FROM lancamentos l JOIN fontes f ON f.id=l.fonte_id LEFT JOIN remessas r ON r.id=l.remessa_id WHERE l.id=?", (lanc_id,))
    if not l:
        return None
    l["valor_fmt"] = util.formatar_centavos(l["valor_centavos"])
    l["partes"] = b.q("SELECT * FROM partes WHERE lancamento_id=? ORDER BY ordem", (lanc_id,))
    for p in l["partes"]:
        p["valor_fmt"] = util.formatar_centavos(p["valor_centavos"])
    l["duplicatas"] = b.q("SELECT * FROM duplicatas WHERE lanc_a=? OR lanc_b=?", (lanc_id, lanc_id))
    return l


def exportar_csv(b, caso_id, filtros, limite=200000):
    w, par = _where(caso_id, dict(filtros or {}, incluir_consolidados=True))
    saida = io.StringIO()
    wr = csv.writer(saida, delimiter=";")
    wr.writerow(["id", "data", "hora", "fuso", "natureza", "valor", "situacao", "motivo", "consolidado_em", "titular", "cpf_cnpj_titular",
                 "banco", "agencia", "conta", "descricao", "tipo_operacao", "chave_pix", "ip", "contrapartes (papel|nome|doc|banco|ag|conta|parcela)",
                 "estado_parcelas", "arquivo", "sha256", "local", "linha", "chave_local"])
    for r in b.q("SELECT l.*, f.nome_original, f.sha256 FROM lancamentos l JOIN fontes f ON f.id=l.fonte_id WHERE %s "
                 "ORDER BY l.data, l.hora, l.id LIMIT ?" % w, par + [limite]):
        ps = b.q("SELECT * FROM partes WHERE lancamento_id=? ORDER BY ordem", (r["id"],))
        cps = " || ".join("%s|%s|%s|%s|%s|%s|%s" % (p["papel"], p["nome"] or "", p["doc"] or "", p["banco"] or "", p["agencia"] or "",
                                                     p["conta"] or "", util.formatar_centavos(p["valor_centavos"])) for p in ps)
        wr.writerow([r["id"], r["data"], r["hora"], r["fuso"], r["natureza"], util.formatar_centavos(r["valor_centavos"]), r["situacao"],
                     r["motivo"], r["consolidado_em"], r["titular_nome"], r["titular_doc"], r["banco"], r["agencia"], r["conta"],
                     r["descricao"], r["tipo_operacao"], r["pix_chave"], r["ip"], cps, r["parcelas_estado"], r["nome_original"],
                     r["sha256"], r["local"], r["linha"], r["chave_local"]])
    return "\ufeff" + saida.getvalue()


# ---------------------------------------------------------------- pesquisa geral (todos os documentos)

ROTULO_TABELA = {
    "lancamentos": "Extrato (lançamento)", "partes": "Extrato (origem/destino)", "titulares": "Cadastro / titulares",
    "acessos": "Acesso / IP / geolocalização", "paginas": "Texto de PDF", "rif_comunicacoes": "RIF - comunicação",
    "rif_envolvidos": "RIF - envolvido",
}


def facetas_identificadores(b, caso_id, busca=None, tabelas=None, limite=5000):
    cond, par = ["caso_id=?"], [caso_id]
    if busca:
        cond.append("(valor_norm LIKE ? OR upper(valor_original) LIKE ?)")
        t = "%" + str(busca).strip().upper() + "%"
        par += ["%" + (util.so_digitos(busca) or util.normalizar_nome(busca) or busca) + "%", t]
    if tabelas:
        cond.append("tabela IN (%s)" % ",".join("?" * len(tabelas)))
        par += list(tabelas)
    out = []
    for tipo, rotulo in identificadores.TIPOS.items():
        linhas = b.q("SELECT valor_norm AS v, MIN(valor_original) AS r, COUNT(*) AS n, COUNT(DISTINCT fonte_id) AS nf, "
                     "GROUP_CONCAT(DISTINCT tabela) AS tabs FROM ocorrencias_ident WHERE %s AND tipo=? "
                     "GROUP BY valor_norm ORDER BY n DESC, v LIMIT %d" % (" AND ".join(cond), limite), par + [tipo])
        if not linhas:
            continue
        for r in linhas:
            if tipo in ("cpf", "cnpj"):
                r["r"] = util.formatar_documento(r["v"])
            r["origens"] = [ROTULO_TABELA.get(t, t) for t in (r.pop("tabs") or "").split(",") if t]
        out.append({"tipo": tipo, "rotulo": rotulo, "valores": linhas, "truncado": len(linhas) >= limite})
    return out


def _contexto(b, tabela, reg_id):
    if tabela == "lancamentos":
        r = b.q1("SELECT data, hora, natureza, valor_centavos, titular_nome, descricao FROM lancamentos WHERE id=?", (reg_id,))
        if r:
            return "%s %s %s %s - %s - %s" % (r["data"] or "", r["hora"] or "", r["natureza"] or "?", util.formatar_centavos(r["valor_centavos"]),
                                             r["titular_nome"] or "", r["descricao"] or "")
    if tabela == "partes":
        r = b.q1("SELECT p.papel, p.nome, p.valor_centavos, l.data, l.natureza, l.valor_centavos AS vl, l.titular_nome, l.id AS lid "
                 "FROM partes p JOIN lancamentos l ON l.id=p.lancamento_id WHERE p.id=?", (reg_id,))
        if r:
            return "%s de lançamento %s %s %s (titular %s); parcela %s [lançamento %d]" % (
                r["papel"], r["data"] or "", r["natureza"] or "?", util.formatar_centavos(r["vl"]), r["titular_nome"] or "?",
                util.formatar_centavos(r["valor_centavos"]) or "não informada", r["lid"])
    if tabela == "acessos":
        r = b.q1("SELECT * FROM acessos WHERE id=?", (reg_id,))
        if r:
            return "%s %s %s IP %s %s %s %s" % (r["data"] or "", r["hora"] or "", r["fuso"] or "", r["ip"] or "-",
                                                ("lat/long %s,%s" % (r["latitude"], r["longitude"])) if r["latitude"] else "",
                                                r["cidade"] or "", r["evento"] or "")
    if tabela == "titulares":
        r = b.q1("SELECT * FROM titulares WHERE id=?", (reg_id,))
        if r:
            return "%s (%s) vínculo %s, banco %s ag %s conta %s" % (r["nome"], r["doc"], r["tipo_vinculo"] or "?", r["banco"] or "?",
                                                                    r["agencia"] or "?", r["conta"] or "?")
    if tabela == "paginas":
        r = b.q1("SELECT pagina FROM paginas WHERE id=?", (reg_id,))
        if r:
            return "página %d do PDF" % r["pagina"]
    if tabela == "rif_envolvidos":
        r = b.q1("SELECT * FROM rif_envolvidos WHERE id=?", (reg_id,))
        if r:
            return "Comunicação %s: %s (%s), %s" % (r["id_comunicacao"], r["nome"], r["doc"], r["tipo_envolvido"] or "")
    if tabela == "rif_comunicacoes":
        r = b.q1("SELECT * FROM rif_comunicacoes WHERE id=?", (reg_id,))
        if r:
            return "Comunicação %s de %s, recebida %s" % (r["id_comunicacao"], r["comunicante_nome"] or "?", r["data_recebimento"] or "?")
    return ""


def ocorrencias(b, caso_id, selecionados, limite=3000):
    if not selecionados:
        return []
    cond = " OR ".join("(o.tipo=? AND o.valor_norm=?)" for _ in selecionados)
    par = [caso_id]
    for s in selecionados:
        par += [s["tipo"], s["valor"]]
    linhas = b.q("SELECT o.*, f.nome_original AS fonte_nome, f.sha256 FROM ocorrencias_ident o JOIN fontes f ON f.id=o.fonte_id "
                 "WHERE o.caso_id=? AND (%s) ORDER BY o.tipo, o.valor_norm, o.fonte_id, o.local, o.linha LIMIT ?" % cond, par + [limite])
    for r in linhas:
        r["origem"] = ROTULO_TABELA.get(r["tabela"], r["tabela"])
        r["contexto"] = _contexto(b, r["tabela"], r["registro_id"])
    return linhas


# ---------------------------------------------------------------- acessos (IP / geolocalização)

FACETAS_ACESSO = [("ip", "IP"), ("data", "Data"), ("cidade", "Cidade"), ("uf", "UF"), ("dispositivo", "Dispositivo"),
                  ("evento", "Evento"), ("nome", "Nome"), ("doc", "CPF/CNPJ"), ("banco", "Banco"), ("fonte_id", "Arquivo")]


def _where_acessos(caso_id, filtros, exceto=None):
    cond, par = ["a.caso_id=?"], [caso_id]
    for k, _ in FACETAS_ACESSO:
        vals = (filtros or {}).get(k)
        if vals and k != exceto:
            cond.append("COALESCE(CAST(a.%s AS TEXT),'(vazio)') IN (%s)" % (k, ",".join("?" * len(vals))))
            par += list(vals)
    return " AND ".join(cond), par


def acessos(b, caso_id, filtros, limite=2000):
    fontes = {str(r["id"]): r["nome_original"] for r in b.q("SELECT id, nome_original FROM fontes WHERE caso_id=?", (caso_id,))}
    facs = []
    for k, rot in FACETAS_ACESSO:
        w, par = _where_acessos(caso_id, filtros, exceto=k)
        vals = b.q("SELECT COALESCE(CAST(a.%s AS TEXT),'(vazio)') AS v, COUNT(*) AS n FROM acessos a WHERE %s GROUP BY v "
                   "ORDER BY n DESC, v LIMIT 5000" % (k, w), par)
        for v in vals:
            v["rotulo"] = fontes.get(v["v"], v["v"]) if k == "fonte_id" else v["v"]
        facs.append({"chave": k, "rotulo": rot, "valores": [{"valor": v["v"], "rotulo": v["rotulo"], "n": v["n"]} for v in vals]})
    w, par = _where_acessos(caso_id, filtros)
    linhas = b.q("SELECT a.*, f.nome_original AS fonte_nome, f.sha256 FROM acessos a JOIN fontes f ON f.id=a.fonte_id WHERE %s "
                 "ORDER BY a.data, a.hora, a.id LIMIT ?" % w, par + [limite])
    total = b.q1("SELECT COUNT(*) AS n FROM acessos a WHERE " + w, par)["n"]
    return {"facetas": facs, "linhas": linhas, "total": total}
