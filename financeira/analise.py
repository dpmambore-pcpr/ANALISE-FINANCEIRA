"""Análise preliminar determinística do caso.

Cruza extratos, RIF e texto de BO/relatório. Não usa modelo de linguagem: os números
vêm do banco local, com fonte e linha. Tudo que não está no documento é hipótese de
trabalho, não conclusão de autoria, dolo ou ilicitude.
"""

import datetime as dt
import re

from . import auditoria, pesquisa, protocolo, util

AVISO = (
    "Análise preliminar automática: aponta padrões documentais e hipóteses de trabalho. "
    "Não é laudo, não afirma crime, autoria, titularidade efetiva nem que uma saída usou o "
    "mesmo dinheiro de uma entrada. Confira fonte, página, linha e cálculos."
)

PAPEIS_DOC = ("boletim", "relatorio_investigacao", "rif", "documento")

HIPOTESES = ("auto", "trafico", "estelionato", "lavagem", "outro")

_RE_CPF = re.compile(r"\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b")
_RE_VITIMA = re.compile(
    r"(?:v[ií]tima|ofendid[oa]|comunicante)[:\s\-–]+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç' ]{4,80})",
    re.I)
_RE_INVEST = re.compile(
    r"(?:investigad[oa]|indiciad[oa]|autor(?:a)? do fato|suspeito|representad[oa]|alvo)[:\s\-–]+"
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç' ]{4,80})",
    re.I)

_TRAFICO = ("trafico", "tráfico", "entorpecente", "drogas", "maconha", "cocaina", "cocaína",
            "crack", "skank", "lolo", "loló", "ecstasy", "mdma", "k9")
_ESTELIONATO = ("estelionato", "golpe", "fraude", "phishing", "boleto falso", "falso advogado",
                "falso aogado", "pix indevido", "conta de laranja", "engan", "estelionat")
_LAVAGEM = ("lavagem", "ocultacao", "ocultação", "dissimulacao", "dissimulação", "credito espurio",
            "crédito espúrio", "recursos de origem ilícita")


def classificar_historico(texto):
    """Categoria operacional a partir do histórico/tipo. Hipótese de leitura, não classificação bancária."""
    t = util.normalizar_nome(texto or "")
    if not t:
        return "outro"
    if any(p in t for p in ("TARIFA", "IOF", "ANUIDADE", "PACOTE", "JUROS", "Cesta".upper(), "MANUTENCAO")):
        return "tarifa"
    if any(p in t for p in ("BINANCE", "BITCOIN", "MERCADO BITCOIN", "FOXBIT", "CRIPTO", "USDT", "NOONER")):
        return "cripto"
    if any(p in t for p in ("BET365", "SPORTINGBET", "BLAZE", "PIXBET", "APOSTA", " BET", "CASA DE APOST")):
        return "apostas"
    if any(p in t for p in ("SAQUE", "ATM", "24H", "ESPECIE", "RETIRADA", "CASH", "WITHDRAW")):
        return "saque"
    if any(p in t for p in ("CARTAO", "MASTERCARD", "VISA ", "ELO ", "HIPERCARD", "DEBITO AUTOMATICO CART",
                            "CREDITO CART", "COMPRA CARTAO", "CDEB", "CCRED")):
        return "cartao"
    if t.startswith("PIX") or " PIX " in " %s " % t or t.endswith(" PIX"):
        return "pix"
    if any(p in t for p in (" TED", "TED ", "DOC ", " DOC", "TEF ", "TRANSFERENCIA", "TRANSF ")):
        return "ted"
    if any(p in t for p in ("BOLETO", "CONTA DE LUZ", "CONTA DE AGUA", "FATURA", "SUPERMERCADO",
                            "FARMACIA", "PAGAMENTO", "DEBITO AUTOMATICO", "COMPRA ")):
        return "compra"
    return "outro"


def parse_pessoas(texto, origem="informado pelo analista"):
    out = []
    for ln in (texto or "").splitlines():
        ln = ln.strip(" -;,\t")
        if not ln:
            continue
        dig = util.so_digitos(ln)
        doc = dig if len(dig) in (11, 14) else None
        nome = re.sub(r"[\d./\-]+", " ", ln)
        nome = re.sub(r"\s+", " ", nome).strip(" -;")
        if not nome and not doc:
            continue
        out.append({
            "nome": nome or None,
            "doc": util.formatar_documento(doc) if doc else None,
            "nome_norm": util.normalizar_nome(nome) if nome else None,
            "doc_norm": doc,
            "origem": origem,
        })
    return out


def _pessoa_bate(pessoa, nome_norm, doc_norm):
    if pessoa.get("doc_norm") and doc_norm and pessoa["doc_norm"] == doc_norm:
        return "cpf_cnpj"
    if pessoa.get("nome_norm") and nome_norm and pessoa["nome_norm"] == nome_norm:
        return "nome"
    return None


def _dt(data, hora):
    if not data:
        return None
    h = (hora or "00:00:00")[:8]
    if len(h) == 5:
        h += ":00"
    try:
        return dt.datetime.fromisoformat("%sT%s" % (data, h))
    except ValueError:
        try:
            return dt.datetime.fromisoformat(data)
        except ValueError:
            return None


def _ev(l, extra=None):
    d = {"lancamento_id": l["id"], "fonte": l.get("fonte_nome") or l.get("nome_original"),
         "sha256": (l.get("sha256") or "")[:16], "local": l.get("local"), "linha": l.get("linha"),
         "data": l.get("data"), "hora": l.get("hora"), "natureza": l.get("natureza"),
         "valor_fmt": util.formatar_centavos(l.get("valor_centavos")),
         "descricao": (l.get("descricao") or l.get("tipo_operacao") or "")[:120],
         "titular": l.get("titular_nome"), "conta": l.get("conta")}
    if extra:
        d.update(extra)
    return d


def _achar(lista, tipo):
    return [a for a in lista if a["tipo"] == tipo]


def contexto(b, caso_id):
    row = b.q1("SELECT * FROM caso_contexto WHERE caso_id=?", (caso_id,))
    if not row:
        return {"caso_id": caso_id, "hipotese_crime": "auto", "vitimas": [], "investigados": [],
                "analise": None, "analise_em": None, "analise_por": None}
    return {
        "caso_id": caso_id,
        "hipotese_crime": row.get("hipotese_crime") or "auto",
        "vitimas": util.json_load(row["vitimas_json"]) if row.get("vitimas_json") else [],
        "investigados": util.json_load(row["investigados_json"]) if row.get("investigados_json") else [],
        "analise": util.json_load(row["analise_json"]) if row.get("analise_json") else None,
        "analise_em": row.get("analise_em"),
        "analise_por": row.get("analise_por"),
    }


def salvar_contexto(b, caso_id, usuario, hipotese_crime=None, vitimas=None, investigados=None):
    auditoria.exigir(b, caso_id, usuario, "analista")
    atual = contexto(b, caso_id)
    if hipotese_crime is not None:
        if hipotese_crime not in HIPOTESES:
            raise ValueError("hipótese inválida: %s" % hipotese_crime)
        atual["hipotese_crime"] = hipotese_crime
    if vitimas is not None:
        atual["vitimas"] = vitimas if isinstance(vitimas, list) else parse_pessoas(vitimas)
    if investigados is not None:
        atual["investigados"] = investigados if isinstance(investigados, list) else parse_pessoas(investigados)
    b.x("INSERT INTO caso_contexto(caso_id, hipotese_crime, vitimas_json, investigados_json, atualizado_em, atualizado_por) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT(caso_id) DO UPDATE SET hipotese_crime=excluded.hipotese_crime, "
        "vitimas_json=excluded.vitimas_json, investigados_json=excluded.investigados_json, "
        "atualizado_em=excluded.atualizado_em, atualizado_por=excluded.atualizado_por",
        (caso_id, atual["hipotese_crime"], util.json_dump(atual["vitimas"]), util.json_dump(atual["investigados"]),
         util.agora_iso(), usuario))
    auditoria.registrar(b, caso_id, usuario, "caso_contexto",
                        {"hipotese_crime": atual["hipotese_crime"], "n_vitimas": len(atual["vitimas"]),
                         "n_investigados": len(atual["investigados"])})
    return contexto(b, caso_id)


def definir_papel_fonte(b, fonte_id, papel, usuario):
    if papel not in PAPEIS_DOC and papel not in ("extrato", "acessos", "cadastro", None, ""):
        raise ValueError("papel de documento inválido")
    f = b.q1("SELECT * FROM fontes WHERE id=?", (fonte_id,))
    if not f:
        raise KeyError("fonte inexistente")
    auditoria.exigir(b, f["caso_id"], usuario, "analista")
    b.x("UPDATE fontes SET papel=? WHERE id=?", (papel or None, fonte_id))
    auditoria.registrar(b, f["caso_id"], usuario, "fonte_papel", {"fonte_id": fonte_id, "papel": papel})
    return b.q1("SELECT id, nome_original, tipo, papel, sha256 FROM fontes WHERE id=?", (fonte_id,))


def _docs_texto(b, caso_id, max_chars=20000):
    w, par = util.sql_in("f.caso_id", caso_id)
    pags = b.q("SELECT f.id AS fonte_id, f.nome_original, f.sha256, f.papel, p.pagina, p.texto "
               "FROM paginas p JOIN fontes f ON f.id=p.fonte_id WHERE " + w + " ORDER BY f.id, p.pagina", par)
    blocos, total = [], 0
    for p in pags:
        trecho = (p["texto"] or "").strip()
        if not trecho:
            continue
        cab = "[%s | papel %s | p. %d | SHA-256 %s]\n" % (
            p["nome_original"], p["papel"] or "documento", p["pagina"], p["sha256"])
        if total + len(cab) + len(trecho) > max_chars:
            resto = max_chars - total - len(cab)
            if resto > 200:
                blocos.append({"fonte": p["nome_original"], "papel": p["papel"], "pagina": p["pagina"],
                               "sha256": p["sha256"], "texto": trecho[:resto] + "\n[truncado]"})
            break
        blocos.append({"fonte": p["nome_original"], "papel": p["papel"], "pagina": p["pagina"],
                       "sha256": p["sha256"], "texto": trecho})
        total += len(cab) + len(trecho)
    return blocos


def _detectar_crime(textos, rif_txt):
    t = util.normalizar_nome(" ".join(textos) + " " + (rif_txt or ""))
    votos = []
    if any(util.normalizar_nome(p) in t for p in _TRAFICO):
        votos.append("trafico")
    if any(util.normalizar_nome(p) in t for p in _ESTELIONATO):
        votos.append("estelionato")
    if any(util.normalizar_nome(p) in t for p in _LAVAGEM):
        votos.append("lavagem")
    return votos


def _pessoas_dos_docs(blocos):
    vit, inv = [], []
    for b in blocos:
        txt = b.get("texto") or ""
        origem = "%s p. %d" % (b["fonte"], b["pagina"])
        for m in _RE_VITIMA.finditer(txt):
            vit.extend(parse_pessoas(m.group(1), "documento: " + origem))
        for m in _RE_INVEST.finditer(txt):
            inv.extend(parse_pessoas(m.group(1), "documento: " + origem))
        papel = (b.get("papel") or "")
        if papel in ("boletim", "relatorio_investigacao"):
            for m in _RE_CPF.finditer(txt):
                pessoas = parse_pessoas(m.group(1), "cpf no documento: " + origem)
                baixo = txt[max(0, m.start() - 80):m.start() + 80].lower()
                if any(w in baixo for w in ("vítima", "vitima", "ofendid")):
                    vit.extend(pessoas)
                elif any(w in baixo for w in ("investigad", "indiciad", "autor", "suspeito", "alvo")):
                    inv.extend(pessoas)
    return _unicos(vit), _unicos(inv)


def _unicos(pessoas):
    seen, out = set(), []
    for p in pessoas:
        k = p.get("doc_norm") or p.get("nome_norm")
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def _lancamentos(b, caso_id, filtros):
    w, par = pesquisa._where(caso_id, filtros)
    linhas = b.q(
        "SELECT l.id, l.data, l.hora, l.natureza, l.valor_centavos, l.parcelas_estado, l.banco, l.agencia, l.conta, "
        "l.titular_nome, l.titular_doc_norm, l.titular_nome_norm, l.descricao, l.tipo_operacao, l.local, l.linha, "
        "l.situacao, f.nome_original AS fonte_nome, f.sha256 "
        "FROM lancamentos l JOIN fontes f ON f.id=l.fonte_id WHERE %s AND l.situacao='aceito' "
        "ORDER BY l.data, l.hora, l.id" % w, par)
    partes = {}
    ids = [l["id"] for l in linhas]
    if ids:
        ph = ",".join("?" * len(ids))
        for p in b.q("SELECT * FROM partes WHERE lancamento_id IN (%s)" % ph, ids):
            partes.setdefault(p["lancamento_id"], []).append(p)
    for l in linhas:
        l["partes"] = partes.get(l["id"], [])
        l["categoria"] = classificar_historico(" ".join(x for x in (l.get("tipo_operacao"), l.get("descricao")) if x))
        l["cp_nome"] = l["partes"][0]["nome"] if l["partes"] else None
        l["cp_doc"] = l["partes"][0]["doc"] if l["partes"] else None
        l["cp_doc_norm"] = l["partes"][0]["doc_norm"] if l["partes"] else None
        l["cp_nome_norm"] = l["partes"][0]["nome_norm"] if l["partes"] else None
    return linhas


def _uso_conta(lancs):
    por = {}
    for l in lancs:
        ck = "%s|%s|%s" % (l.get("banco") or "?", l.get("agencia") or "?", l.get("conta") or "?")
        u = por.setdefault(ck, {
            "conta": ck, "titular": l.get("titular_nome"), "doc": l.get("titular_doc_norm"),
            "n_c": 0, "n_d": 0, "c": 0, "d": 0,
            "cats": {k: {"n": 0, "v": 0} for k in ("saque", "cartao", "compra", "pix", "ted", "tarifa",
                                                    "cripto", "apostas", "outro")},
            "contrapartes_c": set(), "contrapartes_d": set(), "evidencias": [],
        })
        if l["natureza"] == "C":
            u["n_c"] += 1
            u["c"] += l["valor_centavos"] or 0
            if l.get("cp_doc_norm") or l.get("cp_nome_norm"):
                u["contrapartes_c"].add(l.get("cp_doc_norm") or l.get("cp_nome_norm"))
        elif l["natureza"] == "D":
            u["n_d"] += 1
            u["d"] += l["valor_centavos"] or 0
            cat = l["categoria"]
            u["cats"][cat]["n"] += 1
            u["cats"][cat]["v"] += l["valor_centavos"] or 0
            if l.get("cp_doc_norm") or l.get("cp_nome_norm"):
                u["contrapartes_d"].add(l.get("cp_doc_norm") or l.get("cp_nome_norm"))
            if cat in ("saque", "cartao", "compra") and len(u["evidencias"]) < 12:
                u["evidencias"].append(_ev(l, {"categoria": cat}))
    out = []
    for u in por.values():
        d = u["d"] or 0
        trans = u["cats"]["pix"]["v"] + u["cats"]["ted"]["v"]
        efetivo = u["cats"]["saque"]["v"] + u["cats"]["cartao"]["v"] + u["cats"]["compra"]["v"]
        pct_trans = int(100 * trans / d) if d else 0
        pct_efet = int(100 * efetivo / d) if d else 0
        if d == 0:
            perfil = "sem débitos no recorte"
        elif pct_trans >= 85 and pct_efet <= 10:
            perfil = "conta de passagem (hipótese): quase só transferências, pouco uso pessoal"
        elif pct_efet >= 25:
            perfil = "uso efetivo aparente: saques, cartão ou compras diversas"
        else:
            perfil = "uso misto"
        out.append({
            "conta": u["conta"], "titular": u["titular"], "doc": u["doc"],
            "creditos_fmt": util.formatar_centavos(u["c"]), "debitos_fmt": util.formatar_centavos(u["d"]),
            "n_creditos": u["n_c"], "n_debitos": u["n_d"],
            "n_origens": len(u["contrapartes_c"]), "n_destinos": len(u["contrapartes_d"]),
            "pct_transferencias": pct_trans, "pct_uso_efetivo": pct_efet,
            "saques_fmt": util.formatar_centavos(u["cats"]["saque"]["v"]),
            "n_saques": u["cats"]["saque"]["n"],
            "cartao_fmt": util.formatar_centavos(u["cats"]["cartao"]["v"]),
            "n_cartao": u["cats"]["cartao"]["n"],
            "compras_fmt": util.formatar_centavos(u["cats"]["compra"]["v"]),
            "cripto_fmt": util.formatar_centavos(u["cats"]["cripto"]["v"]),
            "apostas_fmt": util.formatar_centavos(u["cats"]["apostas"]["v"]),
            "perfil": perfil, "categorias": {k: {"n": v["n"], "soma_fmt": util.formatar_centavos(v["v"])}
                                             for k, v in u["cats"].items() if v["n"]},
            "evidencias": u["evidencias"],
        })
    out.sort(key=lambda x: -(x["n_creditos"] + x["n_debitos"]))
    return out


def _clusters_valores(lancs, natureza="C", min_n=4, min_pessoas=3):
    grupos = {}
    for l in lancs:
        if l["natureza"] != natureza or not l.get("valor_centavos"):
            continue
        v = l["valor_centavos"]
        # agrupamento exato e por dezena de reais (a partir de R$ 50)
        chaves = [v]
        if v >= 5000:
            chaves.append(("faixa10", (v // 1000) * 1000))
        for k in chaves:
            g = grupos.setdefault(k, {"valor": v if isinstance(k, int) else k[1], "faixa": not isinstance(k, int),
                                      "n": 0, "pessoas": set(), "itens": []})
            g["n"] += 1
            g["pessoas"].add(l.get("cp_doc_norm") or l.get("cp_nome_norm") or "?")
            if len(g["itens"]) < 30:
                g["itens"].append(l)
    out = []
    seen_vals = set()
    for g in sorted(grupos.values(), key=lambda x: -x["n"]):
        if g["n"] < min_n or len(g["pessoas"]) < min_pessoas:
            continue
        if g["valor"] in seen_vals and not g["faixa"]:
            continue
        seen_vals.add(g["valor"])
        out.append({
            "valor_fmt": util.formatar_centavos(g["valor"]),
            "faixa": g["faixa"],
            "n": g["n"],
            "n_contrapartes": len(g["pessoas"]),
            "evidencias": [_ev(l, {"contraparte": l.get("cp_nome") or l.get("cp_doc")}) for l in g["itens"][:15]],
        })
    return out[:20]


def _in_out(lancs, janela_horas=24, tolerancia_pct=5):
    por_conta = {}
    for l in lancs:
        ck = "%s|%s|%s" % (l.get("banco") or "?", l.get("agencia") or "?", l.get("conta") or "?")
        por_conta.setdefault(ck, []).append(l)
    pares = []
    for ck, ls in por_conta.items():
        creds = [l for l in ls if l["natureza"] == "C" and l.get("valor_centavos")]
        debs = [l for l in ls if l["natureza"] == "D" and l.get("valor_centavos")]
        usados = set()
        for c in creds:
            tc = _dt(c["data"], c["hora"])
            if not tc:
                continue
            melhor = None
            for d in debs:
                if d["id"] in usados:
                    continue
                td = _dt(d["data"], d["hora"])
                if not td or td < tc:
                    continue
                horas = (td - tc).total_seconds() / 3600.0
                if horas > janela_horas:
                    continue
                teto = c["valor_centavos"] * (100 + tolerancia_pct) // 100
                if d["valor_centavos"] > teto:
                    continue
                melhor = (d, horas)
                break
            if melhor:
                d, horas = melhor
                usados.add(d["id"])
                pares.append({
                    "conta": ck, "horas": round(horas, 2),
                    "credito": _ev(c, {"contraparte": c.get("cp_nome") or c.get("cp_doc")}),
                    "debito": _ev(d, {"contraparte": d.get("cp_nome") or d.get("cp_doc"),
                                      "categoria": d["categoria"]}),
                    "mesmo_valor": c["valor_centavos"] == d["valor_centavos"],
                })
    return pares


def _rastrear_vitima(lancs, vitima, janela_dias=7):
    entradas, destinos = [], []
    for l in lancs:
        if l["natureza"] != "C":
            continue
        como = _pessoa_bate(vitima, l.get("cp_nome_norm"), l.get("cp_doc_norm"))
        if not como:
            continue
        t0 = _dt(l["data"], l["hora"])
        entradas.append(_ev(l, {"identificacao": como, "contraparte": l.get("cp_nome") or l.get("cp_doc")}))
        resto = l["valor_centavos"] or 0
        ck = "%s|%s|%s" % (l.get("banco") or "?", l.get("agencia") or "?", l.get("conta") or "?")
        for d in lancs:
            if resto <= 0:
                break
            if d["natureza"] != "D":
                continue
            ck2 = "%s|%s|%s" % (d.get("banco") or "?", d.get("agencia") or "?", d.get("conta") or "?")
            if ck2 != ck:
                continue
            td = _dt(d["data"], d["hora"])
            if not td or not t0 or td < t0:
                continue
            if (td - t0).days > janela_dias:
                continue
            usa = min(resto, d["valor_centavos"] or 0)
            resto -= usa
            destinos.append({
                "entrada_id": l["id"],
                "identificacao_vitima": como,
                "categoria": d["categoria"],
                "valor_atribuido_fmt": util.formatar_centavos(usa),
                "resto_fmt": util.formatar_centavos(resto),
                "horas_depois": round((td - t0).total_seconds() / 3600.0, 2),
                "qualificacao": ("HIPÓTESE: coincidência de conta, data posterior e valor; não comprova que o "
                                 "mesmo dinheiro da vítima foi usado nesta saída."),
                "entrada": _ev(l),
                "saida": _ev(d, {"contraparte": d.get("cp_nome") or d.get("cp_doc")}),
            })
    return entradas, destinos


def analisar(b, caso_id, usuario, filtros=None, hipotese_crime=None, vitimas=None, investigados=None,
             janela_vitima_dias=7):
    auditoria.exigir(b, caso_id, usuario, "analista")
    ctx = salvar_contexto(b, caso_id, usuario, hipotese_crime, vitimas, investigados)
    hip = (hipotese_crime or ctx.get("hipotese_crime") or "auto")
    vitimas = ctx.get("vitimas") or []
    investigados = ctx.get("investigados") or []

    ids = protocolo.escopo(b, caso_id)
    blocos = _docs_texto(b, ids)
    wr, pr = util.sql_in("r.caso_id", ids)
    rifs = b.q("SELECT r.numero, r.restricao, f.nome_original, f.sha256 FROM rif_relatorios r "
               "JOIN fontes f ON f.id=r.fonte_id WHERE " + wr, pr)
    wc, pc = util.sql_in("caso_id", ids)
    coms = b.q("SELECT informacoes, comunicante_nome, id_comunicacao FROM rif_comunicacoes WHERE " + wc, pc)
    ocs = b.q("SELECT ocorrencia, id_comunicacao FROM rif_ocorrencias WHERE " + wc, pc)
    envs = b.q("SELECT nome, doc, tipo_envolvido FROM rif_envolvidos WHERE " + wc, pc)
    rif_txt = " ".join((c.get("informacoes") or "") for c in coms) + " " + " ".join((o.get("ocorrencia") or "") for o in ocs)
    votos = _detectar_crime([bl["texto"] for bl in blocos], rif_txt)
    if hip == "auto":
        hip_usada = votos[0] if len(votos) == 1 else ("misto" if votos else "outro")
    else:
        hip_usada = hip

    v_doc, i_doc = _pessoas_dos_docs(blocos)
    vitimas = _unicos(vitimas + v_doc)
    investigados = _unicos(investigados + i_doc)
    for e in envs:
        if (e.get("tipo_envolvido") or "").lower() == "titular":
            investigados = _unicos(investigados + parse_pessoas(
                " ".join(x for x in (e.get("nome"), e.get("doc")) if x), "RIF titular"))

    lancs = _lancamentos(b, caso_id, filtros)
    totais = pesquisa.totais(b, caso_id, filtros)
    usos = _uso_conta(lancs)
    clusters_c = _clusters_valores(lancs, "C")
    clusters_d = _clusters_valores(lancs, "D", min_n=3, min_pessoas=2)
    pares = _in_out(lancs)
    achados = []

    def add(tipo, titulo, texto, evidencias=None, metricas=None, qualificacao="hipotese", crime=None):
        achados.append({
            "id": "A%d" % (len(achados) + 1), "tipo": tipo, "titulo": titulo, "texto": texto,
            "qualificacao": qualificacao, "hipotese_crime": crime or hip_usada,
            "evidencias": evidencias or [], "metricas": metricas or {},
        })

    add("alcance", "Alcance da análise",
        "Seleção com %d lançamentos aceitos; créditos %s em %d; débitos %s em %d; período %s a %s; %d arquivo(s). "
        "Hipótese de trabalho: %s%s." % (
            totais["n_registros"], totais["creditos_fmt"], totais["n_creditos"], totais["debitos_fmt"],
            totais["n_debitos"], totais["periodo"][0], totais["periodo"][1], totais["n_fontes"], hip_usada,
            (" (detectada no BO/RIF: %s)" % ", ".join(votos) if votos and hip == "auto" else "")),
        qualificacao="fato", crime=hip_usada)

    if clusters_c:
        top = clusters_c[0]
        add("valores_semelhantes", "Muitos créditos de valores iguais ou próximos",
            "Há %d crédito(s) em torno de %s vindos de %d contraparte(s) distintas. Em investigação de tráfico, "
            "valores repetidos (ex.: R$ 50, 100, 150, 200, 250) com muitos remetentes são um indício operacional a "
            "verificar — não provam venda de droga. %d agrupamento(s) semelhantes no recorte." % (
                top["n"], top["valor_fmt"], top["n_contrapartes"], len(clusters_c)),
            top["evidencias"], {"agrupamentos": clusters_c[:8]}, crime="trafico")

    if pares:
        iguais = sum(1 for p in pares if p["mesmo_valor"])
        add("lavagem_in_out", "Recebimento com débito em seguida (mesmo dia / 24 h)",
            "%d par(es) crédito→débito na mesma conta em até 24 h, dos quais %d com o mesmo valor. Padrão compatível "
            "com conta de passagem / layering (Carta-Circular 4.001/2020, IV-ad), sempre como hipótese: a coincidência "
            "de valor e data não prova que o mesmo dinheiro foi repassado." % (len(pares), iguais),
            [dict(p["credito"], saida=p["debito"], horas=p["horas"]) for p in pares[:12]],
            {"n_pares": len(pares), "n_mesmo_valor": iguais}, crime="lavagem")

    for u in usos:
        if "passagem" in u["perfil"]:
            add("conta_passagem", "Conta com perfil de passagem: %s" % (u["titular"] or u["conta"]),
                "Na conta %s, %d%% dos débitos são transferências (PIX/TED) e só %d%% aparecem como saque, cartão ou "
                "compra. %d origem(ns) e %d destino(s). Hipótese de conta usada para receber e repassar, não para "
                "gasto pessoal." % (u["conta"], u["pct_transferencias"], u["pct_uso_efetivo"],
                                    u["n_origens"], u["n_destinos"]),
                u["evidencias"], u, crime="lavagem")
        elif "uso efetivo" in u["perfil"]:
            add("uso_conta", "Uso efetivo aparente da conta: %s" % (u["titular"] or u["conta"]),
                "Na conta %s há saques (%s, %d), uso de cartão (%s, %d) e/ou compras/pagamentos (%s). Isso sugere "
                "uso pessoal da conta — relevante no estelionato para distinguir titular que gasta do laranja que "
                "só repassa." % (u["conta"], u["saques_fmt"], u["n_saques"], u["cartao_fmt"], u["n_cartao"],
                                 u["compras_fmt"]),
                u["evidencias"], u, crime="estelionato")
        if u["n_saques"]:
            add("saques", "Saques em espécie na conta %s" % (u["titular"] or u["conta"]),
                "%d saque(s) somando %s. Em tráfico e estelionato, o saque após PIX é um caminho clássico de "
                "realização em espécie (hipótese)." % (u["n_saques"], u["saques_fmt"]),
                [e for e in u["evidencias"] if e.get("categoria") == "saque"][:10],
                {"n": u["n_saques"], "soma_fmt": u["saques_fmt"]})

    rastreios = []
    for v in vitimas:
        ent, dest = _rastrear_vitima(lancs, v, janela_vitima_dias)
        rastreios.append({"vitima": v, "entradas": ent, "destinos": dest})
        if ent:
            cats = {}
            for d in dest:
                cats[d["categoria"]] = cats.get(d["categoria"], 0) + 1
            resumo_cat = ", ".join("%s (%d)" % (k, n) for k, n in sorted(cats.items(), key=lambda x: -x[1])) or "nenhuma saída posterior no recorte"
            add("destino_vitima",
                "O que houve após o dinheiro da vítima %s" % (v.get("nome") or v.get("doc") or "?"),
                "Foram localizados %d crédito(s) em que a contraparte coincide com a vítima (%s). Nas %d hora(s)/dia(s) "
                "seguintes, na mesma conta, as saídas classificadas pelo histórico foram: %s. Cada elo é possibilidade "
                "por data e valor, não rastreio do mesmo cédula/PIX." % (
                    len(ent), v.get("origem") or "informada", janela_vitima_dias, resumo_cat),
                dest[:20] if dest else ent, {"n_entradas": len(ent), "n_saidas": len(dest)},
                crime="estelionato")
        elif v.get("doc_norm") or v.get("nome_norm"):
            add("destino_vitima",
                "Vítima %s sem crédito correspondente no recorte" % (v.get("nome") or v.get("doc")),
                "A vítima foi informada ou extraída do BO/relatório, mas nenhum crédito com essa contraparte foi "
                "encontrado nos extratos importados (filtros atuais). Confira grafia do nome, CPF e se o extrato da "
                "conta do investigado cobre a data do golpe.",
                [], {"n_entradas": 0}, crime="estelionato")

    if rifs:
        alinea = [o["ocorrencia"] for o in ocs if o.get("ocorrencia")]
        add("rif", "RIF no caso (inteligência, não prova)",
            "%d RIF(s), %d comunicação(ões), %d envolvido(s). Ocorrências comunicadas: %s. RIF não entra nos totais "
            "e não prova movimentação." % (
                len(rifs), len(coms), len(envs),
                "; ".join(a[:160] for a in alinea[:4]) or "(sem ocorrência textual)"),
            [{"fonte": r["nome_original"], "sha256": r["sha256"][:16], "numero": r["numero"]} for r in rifs],
            qualificacao="fato")

    narrativa = _redigir(hip_usada, totais, achados, vitimas, investigados, usos, votos, blocos)
    resultado = {
        "aviso": AVISO,
        "hipotese_crime": hip_usada,
        "hipoteses_detectadas": votos,
        "filtros": pesquisa.descrever_filtros(b, filtros),
        "vitimas": vitimas,
        "investigados": investigados,
        "totais": {"creditos_fmt": totais["creditos_fmt"], "debitos_fmt": totais["debitos_fmt"],
                   "n_creditos": totais["n_creditos"], "n_debitos": totais["n_debitos"],
                   "n_registros": totais["n_registros"], "periodo": list(totais["periodo"])},
        "uso_contas": usos,
        "valores_semelhantes": clusters_c,
        "valores_semelhantes_saida": clusters_d,
        "in_out": [{"horas": p["horas"], "mesmo_valor": p["mesmo_valor"],
                    "credito": p["credito"], "debito": p["debito"]} for p in pares[:40]],
        "rastreio_vitimas": rastreios,
        "documentos": [{"fonte": bl["fonte"], "papel": bl["papel"], "pagina": bl["pagina"],
                        "sha256": bl["sha256"][:16], "trecho": (bl["texto"] or "")[:400]} for bl in blocos[:12]],
        "rif": {"n": len(rifs), "restricao": rifs[0]["restricao"] if rifs else None},
        "achados": achados,
        "narrativa": narrativa,
        "gerado_em": util.agora_iso(),
        "gerado_por": usuario,
    }
    b.x("INSERT INTO caso_contexto(caso_id, hipotese_crime, vitimas_json, investigados_json, analise_json, analise_em, "
        "analise_por, atualizado_em, atualizado_por) VALUES (?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(caso_id) DO UPDATE SET hipotese_crime=excluded.hipotese_crime, vitimas_json=excluded.vitimas_json, "
        "investigados_json=excluded.investigados_json, analise_json=excluded.analise_json, analise_em=excluded.analise_em, "
        "analise_por=excluded.analise_por, atualizado_em=excluded.atualizado_em, atualizado_por=excluded.atualizado_por",
        (caso_id, ctx.get("hipotese_crime") or hip, util.json_dump(vitimas), util.json_dump(investigados),
         util.json_dump(resultado), resultado["gerado_em"], usuario, resultado["gerado_em"], usuario))
    auditoria.registrar(b, caso_id, usuario, "analise_preliminar",
                        {"hipotese": hip_usada, "n_achados": len(achados), "n_lancamentos": totais["n_registros"]})
    return resultado


def _redigir(hip, totais, achados, vitimas, investigados, usos, votos, blocos):
    linhas = [AVISO, "",
              "ANÁLISE PRELIMINAR AUTOMÁTICA — hipótese de trabalho: %s." % hip.upper(),
              "Alcance: %d lançamentos aceitos; créditos %s (%d); débitos %s (%d); período %s a %s." % (
                  totais["n_registros"], totais["creditos_fmt"], totais["n_creditos"], totais["debitos_fmt"],
                  totais["n_debitos"], totais["periodo"][0], totais["periodo"][1])]
    if votos:
        linhas.append("Palavras-chave de crime nos documentos/RIF: %s." % ", ".join(votos))
    if vitimas:
        linhas.append("Vítimas consideradas: " + "; ".join(
            "%s %s (%s)" % (v.get("nome") or "", v.get("doc") or "", v.get("origem")) for v in vitimas))
    if investigados:
        linhas.append("Investigados/titulares considerados: " + "; ".join(
            "%s %s" % (v.get("nome") or "", v.get("doc") or "") for v in investigados[:8]))
    if blocos:
        linhas.append("Documentos com texto (BO/relatório/PDF): " + ", ".join(sorted(set(b["fonte"] for b in blocos))))
    linhas.append("")
    if hip in ("trafico", "misto", "auto", "outro", "lavagem"):
        linhas.append("TRÁFICO / VALORES CARACTERÍSTICOS")
        ach = _achar(achados, "valores_semelhantes")
        linhas.append(ach[0]["texto"] if ach else
                      "Não houve agrupamento de créditos repetidos (mínimo 4 lançamentos e 3 remetentes). "
                      "Isso não afasta o tráfico: o recorte ou a grafia dos valores pode não ter agrupado.")
        linhas.append("")
    if hip in ("estelionato", "misto", "auto", "outro"):
        linhas.append("ESTELIONATO / DESTINO DO DINHEIRO DA VÍTIMA")
        dest = _achar(achados, "destino_vitima")
        if dest:
            for a in dest:
                linhas.append("- " + a["titulo"] + ": " + a["texto"])
        else:
            linhas.append("Informe a vítima (CPF/nome) ou importe o BO/relatório com o campo vítima para o programa "
                          "localizar os créditos correspondentes e as saídas seguintes (saque, PIX, cartão).")
        linhas.append("")
    linhas.append("USO DA CONTA E INDÍCIOS DE LAVAGEM / PASSAGEM")
    for a in achados:
        if a["tipo"] in ("conta_passagem", "uso_conta", "lavagem_in_out", "saques"):
            linhas.append("- " + a["titulo"] + ": " + a["texto"])
    if not any(a["tipo"] in ("conta_passagem", "uso_conta", "lavagem_in_out") for a in achados):
        linhas.append("Sem padrão forte de passagem ou de débito imediato no recorte atual.")
    linhas.append("")
    linhas.append("ACHADOS (todos com fonte/linha nas evidências da tela)")
    for a in achados:
        if a["tipo"] == "alcance":
            continue
        linhas.append("[%s / %s] %s" % (a["id"], a["qualificacao"], a["titulo"]))
    linhas.append("")
    linhas.append("Diligências sugeridas (não ampliam a autorização judicial): conferir grafia da vítima nos "
                  "créditos; cruzar CPF dos destinatários com outras contas do caso; revisar duplicatas; no RIF, "
                  "tratar comunicações como inteligência.")
    return "\n".join(linhas)


def responder_local(analise, pergunta):
    """Resposta determinística a partir da análise já calculada (funciona sem Ollama)."""
    if not analise:
        return ("Não há análise preliminar salva. Clique em «Gerar análise preliminar» (funciona sem Ollama) "
                "ou importe extratos/BO e tente de novo.")
    q = util.normalizar_nome(pergunta or "")
    if not q or any(p in q for p in ("ANALISE", "PRELIMINAR", "RESUMO", "RELATORIO")):
        return analise.get("narrativa") or AVISO
    trechos = [AVISO, ""]
    def add_tipo(*tipos):
        n = 0
        for tipo in tipos:
            for a in analise.get("achados") or []:
                if a["tipo"] == tipo:
                    trechos.append("%s — %s\n%s" % (a["id"], a["titulo"], a["texto"]))
                    for e in (a.get("evidencias") or [])[:8]:
                        if isinstance(e, dict) and e.get("lancamento_id"):
                            trechos.append("  lanç. %s %s %s %s %s fonte %s linha %s" % (
                                e.get("lancamento_id"), e.get("data") or "", e.get("natureza") or "",
                                e.get("valor_fmt") or "", (e.get("contraparte") or e.get("descricao") or "")[:60],
                                e.get("fonte") or "", e.get("linha") or ""))
                        elif isinstance(e, dict) and e.get("entrada"):
                            s, en = e.get("saida") or {}, e.get("entrada") or {}
                            trechos.append("  após crédito lanç. %s → saída lanç. %s %s %s %s (%s, %s h)" % (
                                en.get("lancamento_id"), s.get("lancamento_id"), s.get("data"), s.get("valor_fmt"),
                                (s.get("contraparte") or s.get("descricao") or "")[:50], e.get("categoria"),
                                e.get("horas_depois")))
                    n += 1
        return n
    if any(p in q for p in ("VITIMA", "GOLPE", "ESTELIONATO", "DINHEIRO DA", "PARA ONDE", "QUEM RECEBEU")):
        if not add_tipo("destino_vitima", "uso_conta", "saques"):
            trechos.append("Não há rastreio de vítima. Informe o CPF/nome da vítima e gere a análise de novo.")
    elif any(p in q for p in ("TRAFICO", "DROGA", "VALORES PARECID", "SEMELHANT", "CARACTERIST")):
        if not add_tipo("valores_semelhantes"):
            trechos.append("Não foram agrupados créditos repetidos com muitos remetentes neste recorte.")
    elif any(p in q for p in ("LAVAGEM", "PASSAGEM", "IMEDIAT", "IN OUT", "LAYER")):
        if not add_tipo("lavagem_in_out", "conta_passagem"):
            trechos.append("Não há pares crédito→débito em 24 h nem perfil forte de conta de passagem.")
    elif any(p in q for p in ("SAQUE", "CARTAO", "USO DA CONTA", "COMPRA", "EFETIVO")):
        if not add_tipo("uso_conta", "saques", "conta_passagem"):
            trechos.append("Sem classificação de uso pessoal (saque/cartão/compra) neste recorte.")
    elif any(p in q for p in ("RIF", "COAF")):
        add_tipo("rif")
    else:
        # documento ou CPF na pergunta
        dig = util.so_digitos(pergunta or "")
        achou = False
        if len(dig) in (11, 14):
            for a in analise.get("achados") or []:
                blob = util.json_dump(a)
                if dig in blob:
                    trechos.append("%s — %s\n%s" % (a["id"], a["titulo"], a["texto"]))
                    achou = True
        if not achou:
            trechos.append(analise.get("narrativa") or "")
            trechos.append("\nPara uma pergunta mais dirigida, use: destino da vítima; valores semelhantes; "
                           "lavagem/passagem; uso da conta (saque/cartão); ou um CPF.")
    trechos.append("\n" + AVISO)
    return "\n".join(trechos)
