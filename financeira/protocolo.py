"""Reconhece o número SIMBA/PCPR no nome do arquivo e monta o nome do caso."""

import os
import re

from . import util

# Ex.: 056-PCPR-000677-20  (foto do ofício/extrato SIMBA)
RE_PROTO = re.compile(
    r"(?P<pref>\d{2,4})[-_.\s]?(?P<orgao>PCPR|PMPR|MPPR|PF)[-_.\s]?(?P<num>\d{3,8})(?:[-_.\s](?P<ano>\d{2,4}))?",
    re.I,
)

# Palavras do tipo de arquivo, não apelido do investigado/conta.
GENERICO = {
    "extrato", "detalhado", "detalhada", "detalhados", "completo", "completa",
    "rif", "simba", "oficio", "ofício", "planilha", "resposta", "banco",
    "pdf", "csv", "xlsx", "xls", "xlsm", "zip", "txt", "md", "docx",
    "comunica", "comunicado", "comunicacao", "comunicação",
    "origem", "destino", "titulares", "acessos", "download",
    "copia", "cópia", "copy", "arquivo", "doc", "documento",
    "pcpr", "pmpr", "mppr", "relatorio", "relatório", "lancamentos",
    "lançamentos", "movimentacao", "movimentação", "conta", "corrente",
    "de", "da", "do", "das", "dos", "e", "em",
}

RE_SEP = re.compile(r"[-_.,;|/]+")


def _base(nome):
    return os.path.splitext(os.path.basename(str(nome or "").replace("\\", "/")))[0]


def ler_nome(nome):
    """Devolve protocolo, número (677), inscrição (elon musk) e nome sugerido (Caso 677 elon musk)."""
    bruto = _base(nome)
    m = RE_PROTO.search(bruto)
    protocolo = numero = ano = orgao = None
    resto = bruto
    if m:
        pref = m.group("pref")
        orgao = (m.group("orgao") or "PCPR").upper()
        num_bruto = m.group("num")
        ano = m.group("ano")
        numero = int(num_bruto)
        protocolo = "%s-%s-%s%s" % (pref, orgao, num_bruto, ("-" + ano) if ano else "")
        resto = (bruto[:m.start()] + " " + bruto[m.end():]).strip()
    resto = RE_SEP.sub(" ", resto)
    tokens = []
    for t in resto.split():
        n = util.normalizar_nome(t)
        if not n or n.lower() in GENERICO or n.isdigit():
            continue
        if len(n) < 2:
            continue
        tokens.append(t.strip())
    inscricao = " ".join(tokens).strip() or None
    if numero is not None:
        nome_sug = "Caso %d" % numero
        if inscricao:
            nome_sug = "%s %s" % (nome_sug, inscricao)
    else:
        nome_sug = inscricao or bruto or "Novo caso"
    return {
        "protocolo": protocolo,
        "numero": numero,
        "ano": ano,
        "orgao": orgao,
        "inscricao": inscricao,
        "nome_sugerido": nome_sug,
        "origem": os.path.basename(str(nome or "")),
    }


def ids_abrangidos(b, caso_id):
    """Caso simples: [id]. Caso conjunto: ids dos filhos (sem aninhar)."""
    seen, out = set(), []

    def walk(cid):
        cid = int(cid)
        if cid in seen:
            return
        seen.add(cid)
        row = b.q1("SELECT conjunto_json FROM casos WHERE id=?", (cid,))
        if not row:
            return
        filhos = util.json_load(row.get("conjunto_json")) or []
        if filhos:
            for f in filhos:
                walk(f)
        else:
            out.append(cid)

    walk(caso_id)
    return out or [int(caso_id)]


def escopo(b, caso_id):
    if isinstance(caso_id, (list, tuple)):
        return [int(x) for x in caso_id]
    return ids_abrangidos(b, caso_id)
