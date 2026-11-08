"""Grafo de relações e sequências de repasses.

Tudo aqui é HIPÓTESE DE TRABALHO: as ligações são feitas por coincidência de identificador,
data e valor. O programa não afirma que o mesmo dinheiro foi seguido, nem que um débito usou
um crédito específico.
"""

import datetime as dt

from . import bancos, pesquisa, protocolo, util

AVISO = ("Relações por coincidência de identificador, data e valor. Não comprovam que o mesmo dinheiro foi "
         "transferido, nem autoria, titularidade efetiva ou ilicitude.")


def _conta_key(r):
    return "conta:%s|%s|%s" % (r.get("banco") or "?", r.get("agencia") or "?", r.get("conta") or "?")


def _cp_key(p):
    if p.get("doc_norm") and util.so_digitos(p["doc_norm"]) == p["doc_norm"]:
        return "doc:" + p["doc_norm"], "cpf_cnpj"
    if p.get("nome_norm"):
        return "nome:" + p["nome_norm"], "nome"
    return "anon:(não identificado)", "nenhuma"


def grafo(b, caso_id, filtros, max_nos=80, min_volume=0):
    caso_id = protocolo.escopo(b, caso_id)
    w, par = pesquisa._where(caso_id, filtros)
    contas = {}
    for r in b.q("SELECT DISTINCT l.banco, l.agencia, l.conta, l.titular_nome, l.titular_doc_norm FROM lancamentos l WHERE " + w, par):
        k = _conta_key(r)
        contas.setdefault(k, {"titulares": set(), "docs": set(), "banco": r.get("banco"), "agencia": r.get("agencia"), "conta": r.get("conta")})
        if r["titular_nome"]:
            contas[k]["titulares"].add(r["titular_nome"])
        if r["titular_doc_norm"]:
            contas[k]["docs"].add(r["titular_doc_norm"])
    arestas = {}
    nos = {}
    for k, c in contas.items():
        nos[k] = {"id": k, "tipo": "conta", "rotulo": "; ".join(sorted(c["titulares"])) or k[6:],
                  "detalhe": bancos.rotulo_conta_partes(c.get("banco"), c.get("agencia"), c.get("conta")),
                  "docs": sorted(c["docs"]), "volume": 0}
    linhas = b.q("SELECT l.id, l.natureza, l.valor_centavos, l.parcelas_estado, l.banco, l.agencia, l.conta, "
                 "p.doc_norm, p.nome_norm, p.nome, p.doc, p.valor_centavos AS pv FROM lancamentos l "
                 "LEFT JOIN partes p ON p.lancamento_id=l.id WHERE %s AND l.situacao='aceito'" % w, par)
    for r in linhas:
        ck = _conta_key(r)
        if r["parcelas_estado"] in ("conferidas", "unica") and (r["doc_norm"] or r["nome_norm"]):
            pk, ident = _cp_key(r)
            valor = r["pv"] if r["parcelas_estado"] == "conferidas" else r["valor_centavos"]
            rot = r["nome"] or r["doc"] or "(sem nome)"
            if r["doc"]:
                rot += " (%s)" % util.formatar_documento(r["doc"])
        elif r["parcelas_estado"] in ("divergentes", "incompletas"):
            pk, ident, rot, valor = "nd:(não distribuído)", "nenhuma", "(parcelas não distribuídas)", None
        else:
            pk, ident, rot, valor = "anon:(sem quem enviou ou recebeu)", "nenhuma", "(sem quem enviou ou recebeu)", r["valor_centavos"]
        if valor is None:
            if r["parcelas_estado"] in ("divergentes", "incompletas"):
                key = (pk, ck) if r["natureza"] == "C" else (ck, pk)
                if (key, "nd", r["id"]) in arestas:
                    continue
                arestas[(key, "nd", r["id"])] = {"de": key[0], "para": key[1], "valor": r["valor_centavos"], "n": 1, "lids": [r["id"]], "nd": True}
                nos.setdefault(pk, {"id": pk, "tipo": "nao_distribuido", "rotulo": rot, "volume": 0, "identificacao": ident})
                continue
        nos.setdefault(pk, {"id": pk, "tipo": "contraparte", "rotulo": rot, "volume": 0, "identificacao": ident})
        de, para = (pk, ck) if r["natureza"] == "C" else (ck, pk)
        a = arestas.setdefault((de, para), {"de": de, "para": para, "valor": 0, "n": 0, "lids": []})
        a["valor"] += valor or 0
        a["n"] += 1
        if len(a["lids"]) < 50:
            a["lids"].append(r["id"])
    agreg = {}
    for chave, a in arestas.items():
        k = (a["de"], a["para"])
        g = agreg.setdefault(k, {"de": a["de"], "para": a["para"], "valor": 0, "n": 0, "lids": [], "nd": a.get("nd", False)})
        g["valor"] += a["valor"] or 0
        g["n"] += a["n"]
        g["lids"] = (g["lids"] + a["lids"])[:50]
    for a in agreg.values():
        for k in (a["de"], a["para"]):
            nos[k]["volume"] += a["valor"]
    # mesma pessoa? só por documento completo; por nome fica como hipótese
    ligacoes = []
    for k, n in nos.items():
        if n["tipo"] != "contraparte":
            continue
        for ck, c in contas.items():
            if k.startswith("doc:") and k[4:] in c["docs"]:
                ligacoes.append({"de": k, "para": ck, "tipo": "mesmo CPF/CNPJ do titular", "hipotese": False})
            elif k.startswith("nome:") and any(util.normalizar_nome(t) == k[5:] for t in c["titulares"]):
                ligacoes.append({"de": k, "para": ck, "tipo": "HIPÓTESE: mesmo nome do titular (sem documento)", "hipotese": True})
    min_volume = int(min_volume or 0)
    if min_volume:
        agreg = {k: a for k, a in agreg.items() if (a["valor"] or 0) >= min_volume}
        usados = set()
        for a in agreg.values():
            usados.add(a["de"])
            usados.add(a["para"])
        nos = {k: n for k, n in nos.items() if k in usados or n["tipo"] == "conta"}
    max_nos = max(5, min(int(max_nos or 80), 300))
    escolhidos = sorted(nos.values(), key=lambda n: (n["tipo"] != "conta", -n["volume"]))[:max_nos]
    ids = set(n["id"] for n in escolhidos)
    out_arestas = [dict(a, valor_fmt=util.formatar_centavos(a["valor"])) for a in agreg.values() if a["de"] in ids and a["para"] in ids]
    return {"nos": escolhidos, "arestas": out_arestas, "ligacoes": [l for l in ligacoes if l["de"] in ids and l["para"] in ids],
            "omitidos": max(0, len(nos) - len(escolhidos)), "aviso": AVISO,
            "filtros": pesquisa.descrever_filtros(b, filtros), "max_nos": max_nos, "min_volume": min_volume}


def _d(s):
    return dt.date.fromisoformat(s) if s else None


def sequencias(b, caso_id, inicio, janela_dias=3, tolerancia_pct=0, profundidade=3, por_nome=False, limite=200,
               data_ini=None, data_fim=None):
    """inicio: CPF/CNPJ (dígitos) ou chave 'conta:banco|ag|conta'.

    Para cada débito da conta inicial a um recebedor que é titular (mesmo documento; nome só
    se por_nome=True) de outra conta presente no caso, procura débitos dessa outra conta dentro
    da janela, com valor até o valor recebido (+ tolerância). Repete até a profundidade.
    """
    caso_id = protocolo.escopo(b, caso_id)
    wl, pl = util.sql_in("l.caso_id", caso_id)
    lancs = b.q("SELECT l.id, l.data, l.hora, l.natureza, l.valor_centavos, l.parcelas_estado, l.banco, l.agencia, l.conta, "
                "l.titular_nome, l.titular_doc_norm, l.titular_nome_norm, l.local, l.linha, f.nome_original, f.sha256 "
                "FROM lancamentos l JOIN fontes f ON f.id=l.fonte_id WHERE " + wl + " AND l.situacao='aceito' "
                "AND l.consolidado_em IS NULL AND l.data IS NOT NULL", pl)
    partes = {}
    wp, pp = util.sql_in("caso_id", caso_id)
    for p in b.q("SELECT lancamento_id, doc_norm, nome_norm, nome, doc, valor_centavos FROM partes WHERE " + wp, pp):
        partes.setdefault(p["lancamento_id"], []).append(p)
    contas_por_doc, contas_por_nome, debitos, creditos = {}, {}, {}, {}
    for l in lancs:
        ck = _conta_key(l)
        if l["titular_doc_norm"]:
            contas_por_doc.setdefault(l["titular_doc_norm"], set()).add(ck)
        if l["titular_nome_norm"] and not l["titular_nome_norm"].startswith("CONTA CONJUNTA"):
            contas_por_nome.setdefault(l["titular_nome_norm"], set()).add(ck)
        (debitos if l["natureza"] == "D" else creditos).setdefault(ck, []).append(l)
    for v in debitos.values():
        v.sort(key=lambda x: (x["data"], x["hora"] or "", x["id"]))
    if inicio.startswith("conta:"):
        iniciais = {inicio}
    else:
        iniciais = set(contas_por_doc.get(util.so_digitos(inicio) or inicio, set()))
    if not iniciais:
        return {"cadeias": [], "aviso": AVISO, "mensagem": "Nenhuma conta do caso com esse titular/conta."}

    def valor_destino(l, p):
        if l["parcelas_estado"] == "conferidas":
            return p["valor_centavos"]
        if l["parcelas_estado"] == "unica":
            return l["valor_centavos"]
        return None

    def elo(l, p, ident, conta_destino):
        return {"lancamento_id": l["id"], "data": l["data"], "hora": l["hora"], "conta_origem": _conta_key(l)[6:],
                "titular_origem": l["titular_nome"], "destino": p["nome"] or p["doc"], "destino_doc": p["doc"],
                "valor": valor_destino(l, p), "valor_fmt": util.formatar_centavos(valor_destino(l, p)),
                "identificacao": ident, "conta_destino": conta_destino[6:] if conta_destino else None,
                "fonte": l["nome_original"], "sha256": l["sha256"], "local": l["local"], "linha": l["linha"]}

    def espelho(l, conta_destino, valor):
        for c in creditos.get(conta_destino, []):
            if c["data"] == l["data"] and c["valor_centavos"] == valor:
                return {"lancamento_id": c["id"], "fonte": c["nome_original"], "linha": c["linha"]}
        return None

    cadeias = []

    def expandir(conta, desde, teto, caminho, nivel):
        if len(cadeias) >= limite:
            return
        for l in debitos.get(conta, []):
            d = _d(l["data"])
            if desde is not None:
                if d < desde or d > desde + dt.timedelta(days=janela_dias):
                    continue
            if data_ini and l["data"] < data_ini or data_fim and l["data"] > data_fim:
                continue
            for p in partes.get(l["id"], []):
                v = valor_destino(l, p)
                if v is None:
                    continue
                if teto is not None and v > teto * (100 + tolerancia_pct) / 100:
                    continue
                destinos, ident = set(), None
                if p["doc_norm"] and p["doc_norm"] in contas_por_doc:
                    destinos, ident = contas_por_doc[p["doc_norm"]], "mesmo CPF/CNPJ"
                elif por_nome and p["nome_norm"] in contas_por_nome:
                    destinos, ident = contas_por_nome[p["nome_norm"]], "HIPÓTESE: apenas mesmo nome"
                destinos = destinos - {conta} - set(e.get("_conta") for e in caminho)
                if not destinos:
                    if nivel > 0:
                        e = elo(l, p, "destino sem conta no caso", None)
                        cadeias.append({"elos": caminho + [e], "nivel": nivel + 1})
                    continue
                for cd in destinos:
                    e = elo(l, p, ident, cd)
                    e["_conta"] = conta
                    e["registro_espelho_na_conta_destino"] = espelho(l, cd, v)
                    novo = caminho + [e]
                    if nivel + 1 >= profundidade:
                        cadeias.append({"elos": novo, "nivel": nivel + 1})
                    else:
                        antes = len(cadeias)
                        expandir(cd, d, v, novo, nivel + 1)
                        if len(cadeias) == antes:
                            cadeias.append({"elos": novo, "nivel": nivel + 1})
                    if len(cadeias) >= limite:
                        return

    for c in sorted(iniciais):
        expandir(c, None, None, [], 0)
    for cad in cadeias:
        for e in cad["elos"]:
            e.pop("_conta", None)
        cad["qualificacao"] = ("POSSIBILIDADE por coincidência de valor, data e identidade%s; não comprova que o mesmo dinheiro "
                               "foi repassado." % (" aproximada (nome)" if any("nome" in (e["identificacao"] or "") for e in cad["elos"]) else ""))
    return {"cadeias": cadeias, "aviso": AVISO, "parametros": {"inicio": inicio, "janela_dias": janela_dias,
            "tolerancia_pct": tolerancia_pct, "profundidade": profundidade, "por_nome": por_nome},
            "truncado": len(cadeias) >= limite}
