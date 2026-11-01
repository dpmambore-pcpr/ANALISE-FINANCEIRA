"""Revisão humana de duplicatas prováveis. Nada é consolidado sem decisão de um revisor."""

from . import auditoria, util

ESTADOS = {
    "mesma_operacao": "Mesma operação registrada duas vezes (o segundo registro sai dos totais)",
    "distintas": "Operações distintas (ambas permanecem)",
    "dois_lados_confirmado": "Dois lados da mesma transferência (contas diferentes; ambos permanecem em cada conta)",
    "pendente": "Pendente de revisão",
}


def listar(b, caso_id, estado=None, limite=1000):
    cond, par = ["d.caso_id=?"], [caso_id]
    if estado:
        cond.append("d.estado=?")
        par.append(estado)
    linhas = b.q("SELECT d.* FROM duplicatas d WHERE %s ORDER BY d.estado='pendente' DESC, d.id LIMIT ?" % " AND ".join(cond), par + [limite])
    for d in linhas:
        for lado in ("a", "b"):
            l = b.q1("SELECT l.id, l.data, l.hora, l.natureza, l.valor_centavos, l.titular_nome, l.conta, l.descricao, l.local, "
                     "l.linha, l.situacao, l.consolidado_em, f.nome_original, f.sha256 FROM lancamentos l JOIN fontes f ON f.id=l.fonte_id "
                     "WHERE l.id=?", (d["lanc_" + lado],))
            if l:
                l["valor_fmt"] = util.formatar_centavos(l["valor_centavos"])
            d[lado] = l
    return linhas


def decidir(b, dup_id, estado, justificativa, usuario):
    d = b.q1("SELECT * FROM duplicatas WHERE id=?", (dup_id,))
    if not d:
        raise KeyError("duplicata inexistente")
    auditoria.exigir(b, d["caso_id"], usuario, "revisor")
    if estado not in ESTADOS:
        raise ValueError("estado inválido")
    if not str(justificativa or "").strip() and estado != "pendente":
        raise ValueError("Informe a justificativa da decisão.")
    if estado == "mesma_operacao" and d["criterio"] == "dois_lados":
        raise ValueError("Débito e crédito em contas diferentes não são consolidados: use 'dois lados da mesma transferência'.")
    with b.transacao():
        if d["estado"] == "mesma_operacao":
            b.con.execute("UPDATE lancamentos SET consolidado_em=NULL WHERE id=? AND consolidado_em=?", (d["lanc_b"], d["lanc_a"]))
        if estado == "mesma_operacao":
            b.con.execute("UPDATE lancamentos SET consolidado_em=? WHERE id=?", (d["lanc_a"], d["lanc_b"]))
        b.con.execute("UPDATE duplicatas SET estado=?, decidido_por=?, decidido_em=?, justificativa=? WHERE id=?",
                      (estado, usuario, util.agora_iso(), justificativa, dup_id))
    auditoria.registrar(b, d["caso_id"], usuario, "duplicata_decisao",
                        {"duplicata_id": dup_id, "de": d["estado"], "para": estado, "justificativa": justificativa,
                         "lanc_a": d["lanc_a"], "lanc_b": d["lanc_b"]})
