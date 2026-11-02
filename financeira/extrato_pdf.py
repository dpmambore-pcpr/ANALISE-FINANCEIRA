"""Importação de PDF "EXTRATO DETALHADO" (relatório com texto selecionável, uma tabela por conta).

O relatório lido aqui é gerado por sistema de análise a partir das respostas das instituições; não é o
documento original do banco. Cada linha da tabela vira um lançamento com página e linha de origem, o
texto bruto preservado e conferência com os totais que o próprio relatório informa (créditos, débitos
e saldos). Linhas que o programa não consegue interpretar ficam como pendentes, nunca são descartadas.

Colunas do relatório: Data, Histórico, CNAB, Doc., Valor (R$), D/C, CPF/CNPJ, Nome Benef/Depos, Bco, Ag,
Conta, Observações. A natureza vem da coluna D/C. Um CPF que perdeu zeros à esquerda é restaurado somente
quando o resultado tem dígitos verificadores válidos, e isso fica registrado.
"""

import re

from . import leitores, util

_DINHEIRO = r"-?\d{1,3}(?:\.\d{3})*,\d{2}"
RE_LINHA = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{3})\s+(\S+)\s+(%s)\s+([CD])(?:\s+(.*))?$" % _DINHEIRO)
RE_TITULAR = re.compile(r"^Titular:\s*(.+?)\s*(?:\(([^)]*)\))?\s*(CPF|CNPJ):\s*(\S*)\s*(?:Início Rel\.:\s*(\S*))?\s*(?:Fim Rel\.:\s*(\S*))?\s*$")
RE_REPRES = re.compile(r"^Representante:\s*(.+?)\s*(?:\(([^)]*)\))?\s*(CPF|CNPJ):\s*(\S*)")
RE_BANCO = re.compile(r"^Banco:\s*(.+?)\s+N[ºo°]\s*Banco:\s*(\d+)")
RE_AG = re.compile(r"^Ag:\s*(\S*)\s+Inicio Mov\.:\s*(\S*)\s+Extrato \(créditos\):\s*R\$\s*(%s)\s+Extrato \(débitos\):\s*R\$\s*(%s)" % (_DINHEIRO, _DINHEIRO))
RE_CC = re.compile(r"^C/C\.:\s*(\S*)\s+Fim Mov\.:\s*(\S*)")
RE_TIPO = re.compile(r"^Tipo:\s*(.*?)\s*Saldo Inicial:\s*R\$\s*(%s)" % _DINHEIRO)
RE_ABERT = re.compile(r"^Abert\.:\s*(\S*)\s+Saldo Final:\s*R\$\s*(%s)" % _DINHEIRO)
RE_LOCAL = re.compile(r"^Local transação:\s*(.*)$")
RE_CIDADE = re.compile(r"-\s*([^/-]+?)/([A-Z]{2})\s*$")
RE_DOC_IDENT = re.compile(r"Numero doc\. indentificação:\s*(\d+)")
IGNORAR = ("Tipo #", "Base pesquisada:", "EXTRATO DETALHADO", "Data Histórico CNAB", "Usuário:", "Encer.:")
PALAVRAS_DESCRITIVAS = ("COMPRAS", "CIRCULAR", "DEVOLVIDA", "DEBITO", "CREDITO", "SALDO", "TARIFA")
MARCADORES = ("NAO-CORRENTISTA", "CORRENTISTA")


def _centavos(txt):
    txt = txt.strip()
    neg = txt.startswith("-")
    c = util.parse_valor(txt.lstrip("-"))["centavos"]
    return -c if (neg and c is not None) else c


def reconhecer(paginas):
    """True se o texto tem o cabeçalho e a tabela do extrato detalhado."""
    txt = "\n".join(paginas[:3])
    return "EXTRATO DETALHADO" in txt and "Data Histórico CNAB" in txt and "Titular:" in txt


def _doc_restaurado(txt):
    """(doc, nota). Restaura zeros à esquerda só quando o CPF/CNPJ resultante é válido."""
    d = util.so_digitos(txt)
    if not d or set(d) == {"9"} or len(d) < 4:
        return None, None
    if len(d) in (11, 14):
        return d, None
    if len(d) in (9, 10) and util.cpf_valido(d.zfill(11)):
        return d.zfill(11), "CPF com %d dígitos no relatório; zeros à esquerda restaurados (dígitos verificadores válidos)" % len(d)
    if len(d) in (12, 13) and util.cnpj_valido(d.zfill(14)):
        return d.zfill(14), "CNPJ com %d dígitos no relatório; zeros à esquerda restaurados (dígitos verificadores válidos)" % len(d)
    return d, "documento com %d dígitos no relatório; não foi possível validar" % len(d)


def _nome_plausivel(txt):
    if not txt or re.search(r"\d", txt):
        return False
    return not any(p in txt.upper() for p in PALAVRAS_DESCRITIVAS)


def interpretar_resto(resto):
    """Separa CPF/CNPJ, nome, banco, agência, conta e marcador da parte final da linha."""
    out = {"doc": None, "doc_nota": None, "nome": None, "banco": None, "agencia": None, "conta": None,
           "marcador": None, "texto_livre": None, "obs_texto": None}
    resto = (resto or "").strip()
    for m in MARCADORES:
        if resto.endswith(m):
            out["marcador"] = m
            resto = resto[: -len(m)].strip()
            break
    if not resto:
        return out
    m = re.match(r"^(\d{4,20})\s+(.*)$", resto)
    if m:
        out["doc"], out["doc_nota"] = _doc_restaurado(m.group(1))
        resto = m.group(2).strip()
    t = re.match(r"^([^\d]*?)\s*\b(\d{3})\s+(\d+)\s+(\d+)(?:\s+(.*))?$", resto)
    if t:
        resto, out["banco"], out["agencia"], out["conta"] = t.group(1).strip(), t.group(2), t.group(3), t.group(4)
        out["obs_texto"] = (t.group(5) or "").strip() or None
    if not resto or set(resto.replace(" ", "")) == {"9"}:
        return out
    if out["doc"] or out["banco"] or _nome_plausivel(resto):
        out["nome"] = resto
    else:
        out["texto_livre"] = resto
    return out


def analisar(paginas):
    """Percorre as páginas e devolve {contas, linhas, avisos}. Não grava nada."""
    contas, linhas, avisos = [], [], []
    conta = None
    ultima = None
    for np, texto in enumerate(paginas, start=1):
        for nl, bruto in enumerate(texto.splitlines(), start=1):
            ln = bruto.strip()
            if not ln:
                continue
            m = RE_TITULAR.match(ln)
            if m:
                conta = {"titular": m.group(1).strip(), "marca": (m.group(2) or "").strip(), "doc_tipo": m.group(3),
                         "doc": m.group(4), "inicio_rel": m.group(5) or "", "fim_rel": m.group(6) or "", "pagina": np,
                         "representante": None, "banco_nome": "", "banco": "", "agencia": "", "conta": "", "tipo": "",
                         "inicio_mov": "", "fim_mov": "", "creditos_rel": None, "debitos_rel": None, "saldo_inicial": None,
                         "saldo_final": None, "abertura": "", "lancamentos": 0, "creditos": 0, "debitos": 0}
                contas.append(conta)
                ultima = None
                continue
            if conta is None:
                continue
            m = RE_REPRES.match(ln)
            if m:
                conta["representante"] = {"nome": m.group(1).strip(), "doc": m.group(4), "doc_tipo": m.group(3)}
                continue
            m = RE_BANCO.match(ln)
            if m:
                conta["banco_nome"], conta["banco"] = m.group(1).strip(), m.group(2)
                continue
            m = RE_AG.match(ln)
            if m:
                conta["agencia"], conta["inicio_mov"] = m.group(1), m.group(2)
                conta["creditos_rel"], conta["debitos_rel"] = _centavos(m.group(3)), _centavos(m.group(4))
                continue
            m = RE_CC.match(ln)
            if m:
                conta["conta"], conta["fim_mov"] = m.group(1), m.group(2)
                continue
            m = RE_TIPO.match(ln)
            if m:
                conta["tipo"], conta["saldo_inicial"] = m.group(1).strip(), _centavos(m.group(2))
                continue
            m = RE_ABERT.match(ln)
            if m:
                conta["abertura"], conta["saldo_final"] = m.group(1), _centavos(m.group(2))
                continue
            m = RE_LOCAL.match(ln)
            if m or (ultima is not None and ln.startswith("Nome doc.")):
                if ultima is not None:
                    ultima["local_transacao"] = (ultima.get("local_transacao", "") + " " + (m.group(1) if m else ln)).strip()
                    ultima["bruto"] += "\n" + ln
                continue
            if ln.startswith(IGNORAR) or re.match(r"^Data:\s*\d{2}/\d{2}/\d{4}\s+Página", ln) \
                    or re.match(r"^Página \d+ de \d+$", ln):
                continue
            m = RE_LINHA.match(ln)
            if m:
                c = _centavos(m.group(5))
                ultima = {"conta": conta, "pagina": np, "linha": nl, "data": m.group(1), "historico": m.group(2).strip(),
                          "cnab": m.group(3), "doc": m.group(4), "valor": m.group(5), "centavos": c, "dc": m.group(6),
                          "resto": m.group(7) or "", "bruto": ln}
                linhas.append(ultima)
                conta["lancamentos"] += 1
                if c is not None:
                    conta["creditos" if m.group(6) == "C" else "debitos"] += c
                continue
            if re.match(r"^\d{2}/\d{2}/\d{4}\b", ln):
                linhas.append({"conta": conta, "pagina": np, "linha": nl, "nao_reconhecida": True, "bruto": ln})
                ultima = None
                continue
            avisos.append("Página %d, linha %d não interpretada (ignorada): %s" % (np, nl, ln[:90]))
    return {"contas": contas, "linhas": linhas, "avisos": avisos}


def resumo(analise):
    return {"contas": [{"titular": c["titular"], "doc": c["doc"], "banco": c["banco"], "banco_nome": c["banco_nome"],
                        "agencia": c["agencia"], "conta": c["conta"], "tipo": c["tipo"], "lancamentos": c["lancamentos"],
                        "creditos": util.formatar_centavos(c["creditos"]), "debitos": util.formatar_centavos(c["debitos"])}
                       for c in analise["contas"]],
            "lancamentos": sum(1 for r in analise["linhas"] if not r.get("nao_reconhecida")),
            "nao_reconhecidas": sum(1 for r in analise["linhas"] if r.get("nao_reconhecida"))}


def _rotulo_conta(c):
    return "%s - %s, banco %s ag. %s conta %s%s" % (c["titular"], c["doc"], c["banco"], c["agencia"], c["conta"],
                                                      " (%s)" % c["tipo"] if c["tipo"] else "")


def _conferir(imp, contas):
    itens, ok = [], True
    for c in contas:
        rotulo = _rotulo_conta(c)
        for chave_rel, obtido, nome in (("creditos_rel", c["creditos"], "créditos"), ("debitos_rel", c["debitos"], "débitos")):
            esperado = c[chave_rel]
            if esperado is None:
                continue
            bate = esperado == obtido
            ok &= bate
            itens.append({"item": "%s: %s" % (rotulo, nome), "esperado": util.formatar_centavos(esperado),
                          "obtido": util.formatar_centavos(obtido), "ok": bate})
        if None not in (c["saldo_inicial"], c["saldo_final"]):
            calc = c["saldo_inicial"] + c["creditos"] - c["debitos"]
            bate = calc == c["saldo_final"]
            itens.append({"item": "%s: saldo final, informativo (inicial + créditos - débitos)" % rotulo,
                          "esperado": util.formatar_centavos(c["saldo_final"]), "obtido": util.formatar_centavos(calc), "ok": bate})
    imp.rel["controle"] = {"itens": itens, "ok": ok}
    if not all(i["ok"] for i in itens if "saldo final" not in i["item"]):
        imp.aviso("O total de créditos ou débitos calculado a partir das linhas não confere com o que o relatório informa. "
                  "Veja o quadro de conferência: pode haver linha não lida ou página faltando. Nada foi ajustado automaticamente.")
    if not all(i["ok"] for i in itens if "saldo final" in i["item"]):
        imp.aviso("Em alguma conta, saldo inicial + créditos - débitos não é igual ao saldo final informado no relatório "
                  "(pode haver movimentos fora do período, rendimentos ou saldo não zerado). Os lançamentos não foram alterados.")


def importar(imp, caminho):
    paginas, avisos_leitura = leitores.texto_pdf(caminho)
    for a in avisos_leitura:
        imp.aviso(a)
    if not reconhecer(paginas):
        raise ValueError("Este PDF não tem o layout 'EXTRATO DETALHADO' (cabeçalho Titular/Banco e tabela Data, Histórico, CNAB, "
                         "Doc., Valor, D/C...). Se for digitalizado, use o OCR; se for outro layout, use a extração de texto.")
    analise = analisar(paginas)
    if not any(not r.get("nao_reconhecida") for r in analise["linhas"]):
        raise ValueError("Nenhum lançamento reconhecido na tabela do PDF.")
    imp.aviso("Relatório 'EXTRATO DETALHADO' gerado por sistema de análise: não é o documento original da instituição. "
              "Confira com as respostas originais antes de usar em conclusões.")
    imp.aviso("Cidade/UF e canal vêm do campo 'Local transação' do relatório (agência ou canal), não de geolocalização.")
    for a in analise["avisos"][:50]:
        imp.aviso(a)
    if len(analise["avisos"]) > 50:
        imp.aviso("... e mais %d linhas não interpretadas." % (len(analise["avisos"]) - 50))
    notas = set()

    for c in analise["contas"]:
        tipo_conta = c["tipo"] or None
        for vinc, nome, doc, tipo_doc, invest in (
                ("titular", c["titular"], c["doc"], c["doc_tipo"], "investigado" in c["marca"].lower()),
                ("representante", (c["representante"] or {}).get("nome"), (c["representante"] or {}).get("doc"),
                 (c["representante"] or {}).get("doc_tipo"), False)):
            if not nome:
                continue
            imp.titular({"local": "página %d" % c["pagina"], "linha": None, "banco": c["banco"], "agencia": c["agencia"],
                         "conta": c["conta"], "tipo_conta": tipo_conta, "tipo_vinculo": vinc,
                         "pessoa_investigada": 1 if invest else 0, "tipo_pessoa": "2" if tipo_doc == "CNPJ" else "1",
                         "doc": util.so_digitos(doc), "nome": nome, "data_inicio": util.parse_data(c["inicio_rel"])["data"],
                         "data_fim": util.parse_data(c["fim_rel"])["data"] if c["fim_rel"] else None,
                         "bruto": {"banco_nome": c["banco_nome"], "marca": c["marca"]}})

    for r in analise["linhas"]:
        c = r["conta"]
        local = "página %d" % r["pagina"]
        if r.get("nao_reconhecida"):
            imp.lancamento({"situacao": "pendente", "motivo": "linha com data não interpretada (colunas fora do padrão)",
                            "local": local, "linha": r["linha"], "titular_nome": c["titular"],
                            "titular_doc": util.so_digitos(c["doc"]), "banco": c["banco"], "agencia": c["agencia"],
                            "conta": c["conta"], "bruto": {"texto": r["bruto"]}})
            continue
        dt = util.parse_data(r["data"])
        info = interpretar_resto(r["resto"])
        if info["doc_nota"]:
            notas.add(info["doc_nota"])
        conta_txt = c["conta"] if c["tipo"] in ("", "Conta Corrente") else "%s (%s)" % (c["conta"], c["tipo"])
        cidade = uf = None
        interface = None
        if r.get("local_transacao"):
            lt = r["local_transacao"]
            parte_local = re.split(r"\s+Nome doc\.", lt)[0].strip()
            mc = RE_CIDADE.search(parte_local)
            if mc:
                cidade, uf = mc.group(1).strip().title(), mc.group(2)
            if not parte_local.startswith("Ag:"):
                interface = parte_local
        motivos = []
        if dt["data"] is None:
            motivos.append("data inválida: " + r["data"])
        if r["centavos"] is None:
            motivos.append("valor inválido: " + r["valor"])
        titular_doc = util.so_digitos(c["doc"])
        d = {"data": dt["data"], "data_original": r["data"], "valor_centavos": r["centavos"], "valor_original": r["valor"],
             "natureza": r["dc"], "natureza_original": r["dc"], "situacao": "pendente" if motivos else "aceito",
             "motivo": "; ".join(motivos), "titular_nome": c["titular"], "titular_doc": titular_doc,
             "titular_obs": "; ".join(x for x in (c["marca"], c["tipo"]) if x) or None, "banco": c["banco"],
             "agencia": c["agencia"], "conta": conta_txt, "descricao": r["historico"], "tipo_operacao": r["historico"],
             "documento": r["doc"], "cidade": cidade, "uf": uf, "interface": interface, "local": local, "linha": r["linha"],
             "bruto": {"linha_original": r["bruto"], "cnab": r["cnab"], "banco_nome": c["banco_nome"],
                       "conta_tipo": c["tipo"], "local_transacao": r.get("local_transacao"), "interpretado": {
                           k: v for k, v in info.items() if v}}}
        if info["texto_livre"]:
            d["descricao"] = "%s | %s" % (r["historico"], info["texto_livre"])
        partes = []
        if any(info[k] for k in ("doc", "nome", "banco", "conta")):
            obs = "; ".join(x for x in (info["marcador"], info["obs_texto"], info["doc_nota"]) if x) or None
            partes.append({"nome": info["nome"], "doc": info["doc"], "banco": info["banco"], "agencia": info["agencia"],
                           "conta": info["conta"], "observacao": obs, "local": local, "linha": r["linha"],
                           "bruto": {"resto": r["resto"]}})
            m = RE_DOC_IDENT.search(r.get("local_transacao") or "")
            if m and not info["doc"]:
                partes[0]["doc"] = m.group(1)
        imp.lancamento(d, partes)
    for n in sorted(notas):
        imp.aviso(n)
    _conferir(imp, analise["contas"])
    imp.rel["pdf_extrato"] = resumo(analise)
    return imp.rel
