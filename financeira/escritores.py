"""Geração de PDF, DOCX e XLSX simples, apenas com a biblioteca padrão."""

import io
import struct
import zipfile
from xml.sax.saxutils import escape

# ---------------------------------------------------------------- PDF

_LARG_HELV = {}
for _c in range(32, 256):
    _LARG_HELV[_c] = 556
for _ch, _w in {" ": 278, "!": 278, "'": 191, "(": 333, ")": 333, ",": 278, "-": 333, ".": 278, "/": 278,
                ":": 278, ";": 278, "I": 278, "J": 500, "f": 278, "i": 222, "j": 222, "l": 222, "r": 333,
                "t": 278, "m": 833, "w": 722, "M": 833, "W": 944, "m": 833, "|": 260}.items():
    _LARG_HELV[ord(_ch)] = _w


def _cp1252(texto):
    return str(texto).encode("cp1252", "replace")


def _esc_pdf(b):
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _largura(texto, tam):
    return sum(_LARG_HELV.get(c, 556) for c in _cp1252(texto)) * tam / 1000.0


def _quebrar(texto, tam, largura_max):
    linhas = []
    for par in str(texto).split("\n"):
        palavras = par.split(" ")
        atual = ""
        for p in palavras:
            cand = (atual + " " + p) if atual else p
            if _largura(cand, tam) <= largura_max:
                atual = cand
            else:
                if atual:
                    linhas.append(atual)
                while _largura(p, tam) > largura_max and len(p) > 1:
                    corte = len(p)
                    while corte > 1 and _largura(p[:corte], tam) > largura_max:
                        corte -= 1
                    linhas.append(p[:corte])
                    p = p[corte:]
                atual = p
        linhas.append(atual)
    return linhas


def _jpeg_dim(dados):
    i = 2
    while i < len(dados):
        if dados[i] != 0xFF:
            i += 1
            continue
        marca = dados[i + 1]
        if marca in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", dados[i + 5:i + 9])
            return w, h
        tam = struct.unpack(">H", dados[i + 2:i + 4])[0]
        i += 2 + tam
    raise ValueError("JPEG sem dimensões")


class PDF:
    """Documento A4 com texto Helvetica e imagens JPEG."""

    L, A, M = 595.0, 842.0, 50.0

    def __init__(self):
        self.paginas = []
        self.imagens = []
        self._nova()

    def _nova(self):
        self.ops = []
        self.paginas.append(self.ops)
        self.y = self.A - self.M

    def _espaco(self, h):
        if self.y - h < self.M:
            self._nova()

    def texto(self, texto, tam=10, negrito=False, recuo=0):
        fonte = "F2" if negrito else "F1"
        for ln in _quebrar(texto, tam, self.L - 2 * self.M - recuo):
            self._espaco(tam * 1.35)
            self.y -= tam * 1.35
            self.ops.append(b"BT /%s %d Tf %.1f %.1f Td (%s) Tj ET" % (
                fonte.encode(), tam, self.M + recuo, self.y, _esc_pdf(_cp1252(ln))))

    def espaco(self, h=6):
        self.y -= h

    def titulo(self, texto, tam=14):
        self.espaco(6)
        self.texto(texto, tam, True)
        self.espaco(2)

    def tabela(self, cabecalho, linhas, larguras, tam=8):
        total = sum(larguras)
        larg_util = self.L - 2 * self.M
        cols = [w * larg_util / total for w in larguras]

        def linha(valores, negrito):
            partes = [_quebrar(str(v if v is not None else ""), tam, c - 4) for v, c in zip(valores, cols)]
            alt = max(len(p) for p in partes) * tam * 1.25 + 4
            self._espaco(alt)
            topo = self.y
            x = self.M
            fonte = b"F2" if negrito else b"F1"
            for p, c in zip(partes, cols):
                yy = topo - tam - 1
                for ln in p:
                    self.ops.append(b"BT /%s %d Tf %.1f %.1f Td (%s) Tj ET" % (
                        fonte, tam, x + 2, yy, _esc_pdf(_cp1252(ln))))
                    yy -= tam * 1.25
                self.ops.append(b"%.1f %.1f %.1f %.1f re S" % (x, topo - alt, c, alt))
                x += c
            self.y = topo - alt
        linha(cabecalho, True)
        for ln in linhas:
            linha(ln, False)
        self.espaco(6)

    def imagem_jpeg(self, dados, largura_max=None):
        w, h = _jpeg_dim(dados)
        largura_max = largura_max or (self.L - 2 * self.M)
        esc = min(largura_max / w, (self.A - 2 * self.M) / h, 1.0)
        lw, lh = w * esc, h * esc
        self._espaco(lh + 4)
        self.y -= lh
        nome = "Im%d" % (len(self.imagens) + 1)
        self.imagens.append((nome, dados, w, h))
        self.ops.append(b"q %.2f 0 0 %.2f %.1f %.1f cm /%s Do Q" % (lw, lh, self.M, self.y, nome.encode()))
        self.espaco(4)

    def gerar(self):
        objs = []

        def add(b):
            objs.append(b)
            return len(objs)

        add(b"<< /Type /Catalog /Pages 2 0 R >>")
        add(b"")
        f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        xobjs = []
        for nome, dados, w, h in self.imagens:
            n = add(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
                    b"/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n" % (w, h, len(dados))
                    + dados + b"\nendstream")
            xobjs.append(b"/%s %d 0 R" % (nome.encode(), n))
        recursos = b"<< /Font << /F1 %d 0 R /F2 %d 0 R >> /XObject << %s >> >>" % (f1, f2, b" ".join(xobjs))
        kids = []
        total = len(self.paginas)
        for i, ops in enumerate(self.paginas):
            rodape = b"BT /F1 8 Tf %.1f 25 Td (%s) Tj ET" % (self.M, _esc_pdf(_cp1252("Página %d de %d" % (i + 1, total))))
            conteudo = b"\n".join(ops + [rodape])
            c = add(b"<< /Length %d >>\nstream\n" % len(conteudo) + conteudo + b"\nendstream")
            p = add(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources %s /Contents %d 0 R >>" % (
                int(self.L), int(self.A), recursos, c))
            kids.append(b"%d 0 R" % p)
        objs[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(kids), len(kids))
        out = io.BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offs = []
        for i, o in enumerate(objs):
            offs.append(out.tell())
            out.write(b"%d 0 obj\n" % (i + 1) + o + b"\nendobj\n")
        xref = out.tell()
        out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
        for off in offs:
            out.write(b"%010d 00000 n \n" % off)
        out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
        return out.getvalue()


# ---------------------------------------------------------------- DOCX

_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ' \
     'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ' \
     'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" ' \
     'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ' \
     'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'


def _png_dim(dados):
    if dados[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG inválido")
    return struct.unpack(">II", dados[16:24])


class DOCX:
    def __init__(self):
        self.corpo = []
        self.midias = []

    def _run(self, texto, negrito=False, tam=None):
        props = ""
        if negrito or tam:
            props = "<w:rPr>%s%s</w:rPr>" % ("<w:b/>" if negrito else "", '<w:sz w:val="%d"/>' % (tam * 2) if tam else "")
        partes = str(texto).split("\n")
        xml = []
        for i, p in enumerate(partes):
            if i:
                xml.append("<w:br/>")
            xml.append('<w:t xml:space="preserve">%s</w:t>' % escape(p))
        return "<w:r>%s%s</w:r>" % (props, "".join(xml))

    def paragrafo(self, texto, negrito=False, tam=None):
        self.corpo.append("<w:p>%s</w:p>" % self._run(texto, negrito, tam))

    def titulo(self, texto, tam=14):
        self.corpo.append('<w:p><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>%s</w:p>' % self._run(texto, True, tam))

    def tabela(self, cabecalho, linhas):
        borda = '<w:tblBorders>%s</w:tblBorders>' % "".join(
            '<w:%s w:val="single" w:sz="4" w:space="0" w:color="999999"/>' % b
            for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
        xml = ['<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>%s</w:tblPr>' % borda]
        for i, ln in enumerate([cabecalho] + list(linhas)):
            xml.append("<w:tr>")
            for v in ln:
                xml.append('<w:tc><w:p>%s</w:p></w:tc>' % self._run("" if v is None else v, i == 0, 8))
            xml.append("</w:tr>")
        xml.append("</w:tbl><w:p/>")
        self.corpo.append("".join(xml))

    def imagem_png(self, dados, largura_cm=16.0, descricao=""):
        w, h = _png_dim(dados)
        n = len(self.midias) + 1
        self.midias.append(("image%d.png" % n, dados))
        cx = int(largura_cm * 360000)
        cy = int(cx * h / w)
        rid = "rIdImg%d" % n
        self.corpo.append(
            '<w:p><w:r><w:drawing><wp:inline><wp:extent cx="%d" cy="%d"/><wp:docPr id="%d" name="Imagem %d" descr="%s"/>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic><pic:nvPicPr><pic:cNvPr id="%d" name="image%d.png"/><pic:cNvPicPr/></pic:nvPicPr>'
            '<pic:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
            % (cx, cy, n, n, escape(descricao, {'"': "&quot;"}), n, n, rid, cx, cy))

    def gerar(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                       '<Default Extension="xml" ContentType="application/xml"/>'
                       '<Default Extension="png" ContentType="image/png"/>'
                       '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                       '</Types>')
            z.writestr("_rels/.rels",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                       '</Relationships>')
            rels = "".join(
                '<Relationship Id="rIdImg%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/%s"/>'
                % (i + 1, nome) for i, (nome, _) in enumerate(self.midias))
            z.writestr("word/_rels/document.xml.rels",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>' % rels)
            for nome, dados in self.midias:
                z.writestr("word/media/" + nome, dados)
            z.writestr("word/document.xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document %s><w:body>%s'
                       '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>'
                       '</w:body></w:document>' % (_W, "".join(self.corpo)))
        return out.getvalue()


# ---------------------------------------------------------------- XLSX (exemplos e exportação)

def _col(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def gerar_xlsx(abas):
    """abas: lista de (nome, linhas). Textos como inlineStr, int/float como número."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   + "".join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1) for i in range(len(abas)))
                   + '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (escape(n, {'"': "&quot;"}), i + 1, i + 1) for i, (n, _) in enumerate(abas))
                   + '</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1) for i in range(len(abas)))
                   + '</Relationships>')
        for i, (_, linhas) in enumerate(abas):
            xml = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
            for r, ln in enumerate(linhas):
                xml.append('<row r="%d">' % (r + 1))
                for c, v in enumerate(ln):
                    ref = "%s%d" % (_col(c), r + 1)
                    if isinstance(v, bool) or v is None or v == "":
                        continue
                    if isinstance(v, (int, float)):
                        xml.append('<c r="%s"><v>%s</v></c>' % (ref, v))
                    else:
                        xml.append('<c r="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (ref, escape(str(v))))
                xml.append("</row>")
            xml.append("</sheetData></worksheet>")
            z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), "".join(xml))
    return out.getvalue()
