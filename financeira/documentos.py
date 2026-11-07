"""Documentos PDF: texto por página, OCR local opcional e revisão humana.

OCR usa somente programas instalados no próprio computador (Tesseract e pdftoppm/Poppler),
procurados na pasta ferramentas_ocr da aplicação ou no PATH. Nada é enviado à rede.
"""

import csv
import io
import os
import shutil
import subprocess

from . import auditoria, leitores, util

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _programa(nome):
    exe = nome + (".exe" if os.name == "nt" else "")
    for pasta in (os.path.join(RAIZ, "ferramentas_ocr", "tesseract"), os.path.join(RAIZ, "ferramentas_ocr", "poppler", "bin"),
                  os.path.join(RAIZ, "ferramentas_ocr", "poppler", "Library", "bin"), os.path.join(RAIZ, "ferramentas_ocr")):
        c = os.path.join(pasta, exe)
        if os.path.isfile(c):
            return c
    return shutil.which(nome)


def ocr_disponivel():
    t, p = _programa("tesseract"), _programa("pdftoppm")
    idiomas = []
    if t:
        try:
            saida = subprocess.run([t, "--list-langs"], capture_output=True, text=True, timeout=20)
            idiomas = [ln.strip() for ln in saida.stdout.splitlines()[1:] if ln.strip()]
        except (OSError, subprocess.SubprocessError):
            pass
    return {"tesseract": t, "pdftoppm": p, "idiomas": idiomas, "disponivel": bool(t and p)}


def ler_texto_arquivo(caminho):
    with open(caminho, "rb") as f:
        bruto = f.read()
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return bruto.decode(enc)
        except UnicodeDecodeError:
            continue
    return bruto.decode("latin-1", "replace")


def extrair_texto(imp, caminho):
    paginas, avisos = leitores.texto_pdf(caminho)
    for a in avisos:
        imp.aviso(a)
    vazias = 0
    for i, texto in enumerate(paginas, start=1):
        if not texto.strip():
            vazias += 1
        pid = imp.b.con.execute("INSERT INTO paginas(caso_id, fonte_id, pagina, texto, metodo) VALUES (?,?,?,?, 'texto')",
                                (imp.caso_id, imp.fonte["id"], i, texto)).lastrowid
        imp.ident_texto(texto, "paginas", pid, "página %d" % i, None, "texto do PDF")
        imp._passo()
    imp.rel["paginas"] = len(paginas)
    if vazias:
        imp.aviso("%d página(s) sem texto selecionável: provavelmente digitalizadas. Use o OCR local e revise." % vazias)
    imp.aviso("Texto extraído de PDF pode conter erros e não é convertido em lançamentos. Confira a página original.")
    return len(paginas)


def extrair_texto_livre(imp, caminho):
    texto = ler_texto_arquivo(caminho)
    if not texto.strip():
        imp.aviso("O arquivo de texto está vazio.")
    pid = imp.b.con.execute("INSERT INTO paginas(caso_id, fonte_id, pagina, texto, metodo) VALUES (?,?,?,?, 'texto')",
                            (imp.caso_id, imp.fonte["id"], 1, texto)).lastrowid
    imp.ident_texto(texto, "paginas", pid, "arquivo", 1, "texto do documento")
    imp.rel["paginas"] = 1
    imp.aviso("Texto de arquivo (TXT/MD) extraído para a análise. Não vira lançamento bancário.")
    return 1


def renderizar_pagina(pasta_dados, fonte, caminho_pdf, pagina, dpi=150):
    pdftoppm = _programa("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("pdftoppm (Poppler) não encontrado. Veja ferramentas_ocr/LEIA.txt.")
    destino_dir = os.path.join(pasta_dados, "casos", "caso_%d" % fonte["caso_id"], "derivados", "paginas")
    os.makedirs(destino_dir, exist_ok=True)
    base = os.path.join(destino_dir, "f%d_p%d_%d" % (fonte["id"], pagina, dpi))
    if not os.path.exists(base + ".png"):
        subprocess.run([pdftoppm, "-f", str(pagina), "-l", str(pagina), "-r", str(dpi), "-png", "-singlefile", caminho_pdf, base],
                       check=True, capture_output=True, timeout=300)
    return base + ".png"


def ocr_pagina(b, pasta_dados, fonte, caminho_pdf, pagina, usuario, idioma="por"):
    tesseract = _programa("tesseract")
    if not tesseract:
        raise RuntimeError("Tesseract não encontrado. Veja ferramentas_ocr/LEIA.txt.")
    png = renderizar_pagina(pasta_dados, fonte, caminho_pdf, pagina, dpi=300)
    disp = ocr_disponivel()["idiomas"]
    if idioma not in disp:
        idioma = "eng" if "eng" in disp else (disp[0] if disp else "eng")
    saida = subprocess.run([tesseract, png, "stdout", "-l", idioma, "tsv"], capture_output=True, text=True, timeout=600,
                           encoding="utf-8", errors="replace")
    if saida.returncode != 0:
        raise RuntimeError("Tesseract falhou: %s" % saida.stderr[:500])
    palavras = []
    for r in csv.DictReader(io.StringIO(saida.stdout), delimiter="\t", quoting=csv.QUOTE_NONE):
        if r.get("level") == "5" and (r.get("text") or "").strip():
            palavras.append(r)
    linhas, atual, chave = [], [], None
    for r in palavras:
        k = (r["block_num"], r["par_num"], r["line_num"])
        if k != chave and atual:
            linhas.append(" ".join(atual))
            atual = []
        chave = k
        atual.append(r["text"])
    if atual:
        linhas.append(" ".join(atual))
    texto = "\n".join(linhas)
    with b.transacao():
        pg = b.q1("SELECT id FROM paginas WHERE fonte_id=? AND pagina=? AND metodo='ocr'", (fonte["id"], pagina))
        if pg:
            b.con.execute("DELETE FROM ocr_palavras WHERE pagina_id=?", (pg["id"],))
            b.con.execute("UPDATE paginas SET texto=?, revisado=0, imagem=? WHERE id=?", (texto, os.path.relpath(png, pasta_dados), pg["id"]))
            pid = pg["id"]
        else:
            pid = b.con.execute("INSERT INTO paginas(caso_id, fonte_id, pagina, texto, metodo, imagem) VALUES (?,?,?,?, 'ocr', ?)",
                                (fonte["caso_id"], fonte["id"], pagina, texto, os.path.relpath(png, pasta_dados))).lastrowid
        b.con.executemany("INSERT INTO ocr_palavras(pagina_id, texto, confianca, x, y, w, h) VALUES (?,?,?,?,?,?,?)",
                          [(pid, r["text"], float(r.get("conf") or -1), int(r["left"]), int(r["top"]), int(r["width"]),
                            int(r["height"])) for r in palavras])
    auditoria.registrar(b, fonte["caso_id"], usuario, "ocr_pagina", {"fonte_id": fonte["id"], "pagina": pagina, "idioma": idioma,
                                                                    "palavras": len(palavras)})
    return pid


def revisar_pagina(b, pagina_id, usuario, texto=None, correcoes=None):
    pg = b.q1("SELECT * FROM paginas WHERE id=?", (pagina_id,))
    if not pg:
        raise KeyError("página inexistente")
    auditoria.exigir(b, pg["caso_id"], usuario, "analista")
    with b.transacao():
        for c in correcoes or []:
            b.con.execute("UPDATE ocr_palavras SET texto_corrigido=?, revisado=1 WHERE id=? AND pagina_id=?",
                          (c["texto"], int(c["id"]), pagina_id))
        if texto is not None:
            b.con.execute("UPDATE paginas SET texto=? WHERE id=?", (texto, pagina_id))
        b.con.execute("UPDATE paginas SET revisado=1, revisado_por=?, revisado_em=? WHERE id=?", (usuario, util.agora_iso(), pagina_id))
    auditoria.registrar(b, pg["caso_id"], usuario, "pagina_revisada", {"pagina_id": pagina_id, "correcoes": len(correcoes or [])})
