"""Relatório de análise (rascunho para revisão) em HTML, DOCX ou PDF.

Contém filtros, alcance, totais, memória de cálculo com fonte/linha/SHA-256 de cada parcela,
fontes, avisos e imagens marcadas. O texto analítico é do analista; não é redigido pela IA.
"""

import base64
import html
import os

from . import VERSAO, escritores, pesquisa, util

LIMITE_MEMORIA = 3000

RESSALVAS = [
    "Rascunho gerado automaticamente para conferência; não é laudo.",
    "Totais incluem apenas registros aceitos e não consolidados como duplicata confirmada; pendentes e rejeitados estão fora.",
    "As mesmas operações podem constar em contas, arquivos ou abas diferentes; veja os avisos e a revisão de duplicatas.",
    "Coincidência de nome, documento, conta, valor ou data não demonstra autoria, titularidade efetiva, dolo, crime "
    "ou que uma saída utilizou o mesmo dinheiro de uma entrada.",
    "Ausência de registro na seleção não prova inexistência da operação.",
]


def dados(b, caso_id, filtros, observacoes, evidencias_ids, usuario, pasta_dados):
    caso = b.q1("SELECT * FROM casos WHERE id=?", (caso_id,))
    t = pesquisa.totais(b, caso_id, filtros)
    w, par = pesquisa._where(caso_id, filtros)
    memoria = b.q("SELECT l.id, l.data, l.hora, l.natureza, l.valor_centavos, l.titular_nome, l.conta, l.local, l.linha, "
                  "f.nome_original, f.sha256 FROM lancamentos l JOIN fontes f ON f.id=l.fonte_id "
                  "WHERE %s AND l.situacao='aceito' ORDER BY l.natureza, l.data, l.id LIMIT ?" % w, par + [LIMITE_MEMORIA + 1])
    truncada = len(memoria) > LIMITE_MEMORIA
    memoria = memoria[:LIMITE_MEMORIA]
    soma = {"C": 0, "D": 0}
    for m in memoria:
        soma[m["natureza"]] += m["valor_centavos"]
    fontes = b.q("SELECT DISTINCT f.id, f.nome_original, f.sha256, f.caminho_no_pacote, f.tamanho FROM fontes f "
                 "JOIN lancamentos l ON l.fonte_id=f.id WHERE " + w + " ORDER BY f.id", par)
    evid = []
    for eid in evidencias_ids or []:
        e = b.q1("SELECT e.*, f.nome_original FROM evidencias e LEFT JOIN fontes f ON f.id=e.fonte_id WHERE e.id=? AND e.caso_id=?",
                 (int(eid), caso_id))
        if e:
            with open(os.path.join(pasta_dados, e["arquivo_png"]), "rb") as fh:
                e["png"] = fh.read()
            if e.get("arquivo_jpg") and os.path.exists(os.path.join(pasta_dados, e["arquivo_jpg"])):
                with open(os.path.join(pasta_dados, e["arquivo_jpg"]), "rb") as fh:
                    e["jpg"] = fh.read()
            evid.append(e)
    return {"caso": caso, "totais": t, "filtros": pesquisa.descrever_filtros(b, filtros), "memoria": memoria,
            "memoria_truncada": truncada, "soma_memoria": soma, "fontes": fontes, "observacoes": observacoes or "",
            "evidencias": evid, "usuario": usuario, "gerado_em": util.agora_iso(), "versao": VERSAO}


def _linhas_memoria(d):
    return [[m["id"], m["data"], m["natureza"], util.formatar_centavos(m["valor_centavos"]), m["titular_nome"] or "",
             "%s | %s | linha %s" % (m["nome_original"], m["local"] or "-", m["linha"]), m["sha256"][:16] + "…"] for m in d["memoria"]]


def _texto_memoria(d):
    t = d["totais"]
    out = ["Créditos aceitos = soma de %d lançamentos = %s." % (t["n_creditos"], t["creditos_fmt"]),
           "Débitos aceitos = soma de %d lançamentos = %s." % (t["n_debitos"], t["debitos_fmt"])]
    if d["memoria_truncada"]:
        out.append("A lista abaixo foi limitada a %d linhas (subtotais listados: créditos %s, débitos %s). Exporte o CSV da "
                   "pesquisa com os mesmos filtros para a lista completa." % (
                       LIMITE_MEMORIA, util.formatar_centavos(d["soma_memoria"]["C"]), util.formatar_centavos(d["soma_memoria"]["D"])))
    else:
        ok = d["soma_memoria"]["C"] == t["creditos"] and d["soma_memoria"]["D"] == t["debitos"]
        out.append("Conferência: a soma das linhas listadas %s os totais." % ("reproduz" if ok else "NÃO reproduz"))
    return out


def html_relatorio(d):
    e = html.escape
    t = d["totais"]
    p = ["<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Relatório - %s</title>" % e(d["caso"]["nome"]),
         "<style>body{font-family:Arial,sans-serif;margin:2em;color:#111}table{border-collapse:collapse;width:100%;margin:.5em 0 1em}"
         "td,th{border:1px solid #999;padding:3px 5px;font-size:12px;vertical-align:top}th{background:#eee}"
         ".aviso{background:#fff4d6;border-left:4px solid #e0a800;padding:6px 10px;margin:4px 0}"
         "img{max-width:100%;border:1px solid #999}@media print{.np{display:none}}</style></head><body>",
         "<h1>Análise de movimentações - rascunho</h1>",
         "<p><b>Caso:</b> %s<br><b>Gerado em:</b> %s por %s<br><b>Programa:</b> Análise Bancária Local v%s</p>" % (
             e(d["caso"]["nome"]), e(d["gerado_em"]), e(d["usuario"] or "?"), e(d["versao"])),
         "<h2>Filtros e alcance</h2><ul>%s</ul>" % "".join("<li>%s</li>" % e(f) for f in d["filtros"]),
         "<p>%d registros na seleção; período %s a %s; %d arquivo(s).</p>" % (t["n_registros"], e(str(t["periodo"][0])),
                                                                             e(str(t["periodo"][1])), t["n_fontes"]),
         "<h2>Totais calculados</h2><table><tr><th>Item</th><th>Quantidade</th><th>Valor</th></tr>",
         "<tr><td>Créditos aceitos</td><td>%d</td><td>%s</td></tr>" % (t["n_creditos"], t["creditos_fmt"]),
         "<tr><td>Débitos aceitos</td><td>%d</td><td>%s</td></tr>" % (t["n_debitos"], t["debitos_fmt"]),
         "<tr><td>Pendentes (fora dos totais)</td><td>%d</td><td>%s</td></tr>" % (t["n_pendentes"], t["pendentes_fmt"]),
         "<tr><td>Rejeitados</td><td>%d</td><td>-</td></tr></table>" % t["n_rejeitados"]]
    for a in t["avisos"]:
        p.append("<div class='aviso'>%s</div>" % e(a))
    for nome, rk in (("Principais origens (créditos)", t["origens"]), ("Principais destinos (débitos)", t["destinos"])):
        p.append("<h3>%s</h3><table><tr><th>Contraparte</th><th>CPF/CNPJ</th><th>Lançamentos</th><th>Valor</th></tr>" % nome)
        for i in rk["itens"]:
            p.append("<tr><td>%s</td><td>%s</td><td>%d</td><td>%s</td></tr>" % (e(i["nome"] or "?"), e(i["doc"] or ""), i["n"], i["soma_fmt"]))
        p.append("<tr><td colspan=3>Não distribuído (parcelas divergentes/incompletas)</td><td>%s</td></tr>" % rk["nao_distribuido"]["soma_fmt"])
        p.append("<tr><td colspan=3>Sem contraparte identificada</td><td>%s</td></tr></table>" % rk["sem_contraparte"]["soma_fmt"])
    p.append("<h3>Por conta</h3><table><tr><th>Conta</th><th>Titular</th><th>Créditos</th><th>Débitos</th><th>Registros</th></tr>")
    for c in t["por_conta"]:
        p.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td></tr>" % (e(c["conta"]), e(c["titular"] or ""), c["c_fmt"], c["d_fmt"], c["n"]))
    p.append("</table>")
    if d["observacoes"].strip():
        p.append("<h2>Observações do analista</h2><p>%s</p>" % e(d["observacoes"]).replace("\n", "<br>"))
    for ev in d["evidencias"]:
        p.append("<h3>Imagem: %s</h3><p>Origem: %s, página %s; SHA-256 do original %s; SHA-256 da imagem %s.</p>" % (
            e(ev["descricao"] or ""), e(ev.get("nome_original") or "-"), ev["pagina"] or "-", ev["sha256_fonte"] or "-", ev["sha256_png"]))
        p.append("<img alt='%s' src='data:image/png;base64,%s'>" % (e(ev["descricao"] or ""), base64.b64encode(ev["png"]).decode()))
    p.append("<h2>Fontes</h2><table><tr><th>Arquivo</th><th>SHA-256</th><th>Bytes</th></tr>")
    for f in d["fontes"]:
        p.append("<tr><td>%s</td><td style='font-family:monospace'>%s</td><td>%s</td></tr>" % (
            e(f["caminho_no_pacote"] or f["nome_original"]), f["sha256"], f["tamanho"]))
    p.append("</table><h2>Memória de cálculo</h2>")
    p += ["<p>%s</p>" % e(x) for x in _texto_memoria(d)]
    p.append("<table><tr><th>ID</th><th>Data</th><th>Nat.</th><th>Valor</th><th>Titular</th><th>Fonte / local / linha</th><th>SHA-256</th></tr>")
    for ln in _linhas_memoria(d):
        p.append("<tr>%s</tr>" % "".join("<td>%s</td>" % e(str(x)) for x in ln))
    p.append("</table><h2>Ressalvas</h2><ul>%s</ul></body></html>" % "".join("<li>%s</li>" % e(r) for r in RESSALVAS))
    return "".join(p).encode("utf-8")


def _estrutura(doc, d):
    t = d["totais"]
    doc.titulo("Análise de movimentações - rascunho", 16)
    doc.paragrafo("Caso: %s" % d["caso"]["nome"])
    doc.paragrafo("Gerado em %s por %s - Análise Bancária Local v%s" % (d["gerado_em"], d["usuario"] or "?", d["versao"]))
    doc.titulo("Filtros e alcance")
    for f in d["filtros"]:
        doc.paragrafo("- " + f)
    doc.paragrafo("%d registros na seleção; período %s a %s; %d arquivo(s)." % (t["n_registros"], t["periodo"][0], t["periodo"][1], t["n_fontes"]))
    doc.titulo("Totais calculados")
    doc.tabela(["Item", "Quantidade", "Valor"], [["Créditos aceitos", t["n_creditos"], t["creditos_fmt"]],
                                                 ["Débitos aceitos", t["n_debitos"], t["debitos_fmt"]],
                                                 ["Pendentes (fora dos totais)", t["n_pendentes"], t["pendentes_fmt"]],
                                                 ["Rejeitados", t["n_rejeitados"], "-"]])
    for a in t["avisos"]:
        doc.paragrafo("Aviso: " + a)
    for nome, rk in (("Principais origens (créditos)", t["origens"]), ("Principais destinos (débitos)", t["destinos"])):
        doc.titulo(nome, 12)
        linhas = [[i["nome"] or "?", i["doc"] or "", i["n"], i["soma_fmt"]] for i in rk["itens"]]
        linhas.append(["Não distribuído (parcelas divergentes/incompletas)", "", rk["nao_distribuido"]["n"], rk["nao_distribuido"]["soma_fmt"]])
        linhas.append(["Sem contraparte identificada", "", rk["sem_contraparte"]["n"], rk["sem_contraparte"]["soma_fmt"]])
        doc.tabela(["Contraparte", "CPF/CNPJ", "Lançamentos", "Valor"], linhas)
    doc.titulo("Por conta", 12)
    doc.tabela(["Conta", "Titular", "Créditos", "Débitos", "Registros"],
               [[c["conta"], c["titular"] or "", c["c_fmt"], c["d_fmt"], c["n"]] for c in t["por_conta"]])
    if d["observacoes"].strip():
        doc.titulo("Observações do analista")
        doc.paragrafo(d["observacoes"])


def docx_relatorio(d):
    doc = escritores.DOCX()
    _estrutura(doc, d)
    for ev in d["evidencias"]:
        doc.titulo("Imagem: %s" % (ev["descricao"] or ""), 12)
        doc.paragrafo("Origem: %s, página %s; SHA-256 do original %s; SHA-256 da imagem %s." % (
            ev.get("nome_original") or "-", ev["pagina"] or "-", ev["sha256_fonte"] or "-", ev["sha256_png"]))
        doc.imagem_png(ev["png"], descricao=ev["descricao"] or "")
    doc.titulo("Fontes")
    doc.tabela(["Arquivo", "SHA-256", "Bytes"], [[f["caminho_no_pacote"] or f["nome_original"], f["sha256"], f["tamanho"]] for f in d["fontes"]])
    doc.titulo("Memória de cálculo")
    for x in _texto_memoria(d):
        doc.paragrafo(x)
    doc.tabela(["ID", "Data", "Nat.", "Valor", "Titular", "Fonte / local / linha", "SHA-256"], _linhas_memoria(d))
    doc.titulo("Ressalvas")
    for r in RESSALVAS:
        doc.paragrafo("- " + r)
    return doc.gerar()


class _PDFAdaptado(escritores.PDF):
    def paragrafo(self, texto, negrito=False, tam=None):
        self.texto(texto, tam or 10, negrito)

    def tabela(self, cab, linhas, larguras=None):
        super().tabela(cab, linhas, larguras or [1] * len(cab))


def pdf_relatorio(d):
    doc = _PDFAdaptado()
    _estrutura(doc, d)
    for ev in d["evidencias"]:
        doc.titulo("Imagem: %s" % (ev["descricao"] or ""), 12)
        doc.texto("Origem: %s, página %s; SHA-256 do original %s; SHA-256 da imagem %s." % (
            ev.get("nome_original") or "-", ev["pagina"] or "-", ev["sha256_fonte"] or "-", ev["sha256_png"]), 8)
        if ev.get("jpg"):
            doc.imagem_jpeg(ev["jpg"])
        else:
            doc.texto("(imagem disponível no relatório DOCX/HTML)", 8)
    doc.titulo("Fontes")
    doc.tabela(["Arquivo", "SHA-256", "Bytes"], [[f["caminho_no_pacote"] or f["nome_original"], f["sha256"], f["tamanho"]] for f in d["fontes"]],
               [3, 6, 1])
    doc.titulo("Memória de cálculo")
    for x in _texto_memoria(d):
        doc.texto(x)
    doc.tabela(["ID", "Data", "Nat.", "Valor", "Titular", "Fonte / local / linha", "SHA-256"], _linhas_memoria(d), [1, 2, 1, 2, 3, 4, 2])
    doc.titulo("Ressalvas")
    for r in RESSALVAS:
        doc.texto("- " + r)
    return doc.gerar()


def gerar(b, caso_id, formato, filtros, observacoes, evidencias_ids, usuario, pasta_dados):
    d = dados(b, caso_id, filtros, observacoes, evidencias_ids, usuario, pasta_dados)
    if formato == "docx":
        return docx_relatorio(d), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "relatorio.docx"
    if formato == "pdf":
        return pdf_relatorio(d), "application/pdf", "relatorio.pdf"
    return html_relatorio(d), "text/html; charset=utf-8", "relatorio.html"
