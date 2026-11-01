"""Leitores de arquivos usando apenas a biblioteca padrão (funciona no Python portátil do Windows).

Os leitores devolvem textos; nenhuma conversão de valor é feita aqui.
"""

import codecs
import csv
import io
import re
import zipfile
import zlib
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

csv.field_size_limit(64 * 1024 * 1024)

# ---------------------------------------------------------------- texto delimitado

DELIMITADORES = [";", ",", "\t", "|"]


def detectar_codificacao(amostra):
    if amostra.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if amostra.startswith(codecs.BOM_UTF16_LE) or amostra.startswith(codecs.BOM_UTF16_BE):
        return "utf-16"
    dec = codecs.getincrementaldecoder("utf-8")()
    try:
        dec.decode(amostra, final=False)
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def detectar_delimitador(linhas):
    melhor, melhor_pont = ";", -1
    for d in DELIMITADORES:
        contagens = [ln.count(d) for ln in linhas if ln.strip()]
        if not contagens or max(contagens) == 0:
            continue
        constantes = sum(1 for c in contagens if c == contagens[0])
        pont = constantes * 1000 + contagens[0]
        if pont > melhor_pont:
            melhor, melhor_pont = d, pont
    return melhor


def abrir_texto(caminho, codificacao=None):
    with open(caminho, "rb") as f:
        amostra = f.read(1024 * 1024)
    cod = codificacao or detectar_codificacao(amostra)
    erros = "strict" if cod.startswith("utf") else "replace"
    return open(caminho, "r", encoding=cod, errors=erros, newline=""), cod


def info_delimitado(caminho, codificacao=None, delimitador=None):
    f, cod = abrir_texto(caminho, codificacao)
    with f:
        linhas = []
        for _ in range(30):
            ln = f.readline()
            if not ln:
                break
            linhas.append(ln)
    return {"codificacao": cod, "delimitador": delimitador or detectar_delimitador(linhas)}


def linhas_delimitado(caminho, codificacao=None, delimitador=None):
    """Gera (numero_linha_fisica, lista_de_campos). Numeração começa em 1."""
    info = info_delimitado(caminho, codificacao, delimitador)
    f, _ = abrir_texto(caminho, info["codificacao"])
    with f:
        leitor = csv.reader(f, delimiter=info["delimitador"])
        for campos in leitor:
            yield leitor.line_num, campos


# ---------------------------------------------------------------- XLSX

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_FORMATOS_DATA = set(range(14, 23)) | {27, 30, 36, 45, 46, 47, 50, 57}


def _col_indice(ref):
    letras = ""
    for ch in ref:
        if ch.isalpha():
            letras += ch
        else:
            break
    n = 0
    for ch in letras.upper():
        n = n * 26 + (ord(ch) - 64)
    return n - 1


class LeitorXLSX:
    def __init__(self, caminho):
        self.caminho = caminho
        self.z = zipfile.ZipFile(caminho)
        self._abas = self._ler_abas()
        self._strings = None
        self._estilos_data = None

    def fechar(self):
        self.z.close()

    def abas(self):
        return [nome for nome, _ in self._abas]

    def _ler_abas(self):
        wb = ET.fromstring(self.z.read("xl/workbook.xml"))
        rels = {}
        try:
            rx = ET.fromstring(self.z.read("xl/_rels/workbook.xml.rels"))
            for r in rx:
                alvo = r.get("Target", "")
                if alvo.startswith("/"):
                    alvo = alvo[1:]
                elif not alvo.startswith("xl/"):
                    alvo = "xl/" + alvo
                rels[r.get("Id")] = alvo
        except KeyError:
            pass
        out = []
        sheets = wb.find(_NS + "sheets")
        for i, s in enumerate(sheets if sheets is not None else []):
            rid = s.get(_NS_R + "id")
            out.append((s.get("name"), rels.get(rid, "xl/worksheets/sheet%d.xml" % (i + 1))))
        return out

    def _carregar_strings(self):
        if self._strings is not None:
            return
        self._strings = []
        try:
            f = self.z.open("xl/sharedStrings.xml")
        except KeyError:
            return
        with f:
            for ev, el in ET.iterparse(f, events=("end",)):
                if el.tag == _NS + "si":
                    partes = []
                    for t in el.iter(_NS + "t"):
                        partes.append(t.text or "")
                    for rph in el.iter(_NS + "rPh"):
                        for t in rph.iter(_NS + "t"):
                            if t.text and t.text in partes:
                                partes.remove(t.text)
                    self._strings.append("".join(partes))
                    el.clear()

    def _carregar_estilos(self):
        if self._estilos_data is not None:
            return
        self._estilos_data = []
        try:
            st = ET.fromstring(self.z.read("xl/styles.xml"))
        except KeyError:
            return
        personal = {}
        nf = st.find(_NS + "numFmts")
        if nf is not None:
            for f in nf:
                codigo = re.sub(r'"[^"]*"|\[[^\]]*\]', "", f.get("formatCode", "")).lower()
                personal[int(f.get("numFmtId"))] = bool(re.search(r"[dy]", codigo)) or ("h" in codigo and "m" in codigo)
        xfs = st.find(_NS + "cellXfs")
        for xf in (xfs if xfs is not None else []):
            fid = int(xf.get("numFmtId", "0"))
            self._estilos_data.append(fid in _FORMATOS_DATA or personal.get(fid, False))

    def linhas(self, aba):
        """Gera (numero_linha, lista_de_textos). Células de data saem como AAAA-MM-DD[ HH:MM:SS]."""
        self._carregar_strings()
        self._carregar_estilos()
        alvo = None
        for nome, caminho in self._abas:
            if nome == aba:
                alvo = caminho
        if alvo is None:
            raise KeyError("aba não encontrada: %s" % aba)
        from . import util
        with self.z.open(alvo) as f:
            proxima = 1
            for ev, el in ET.iterparse(f, events=("end",)):
                if el.tag != _NS + "row":
                    continue
                num = int(el.get("r") or proxima)
                proxima = num + 1
                valores = {}
                seq = 0
                for c in el.findall(_NS + "c"):
                    ref = c.get("r")
                    col = _col_indice(ref) if ref else seq
                    seq = col + 1
                    t = c.get("t", "n")
                    v = c.find(_NS + "v")
                    texto = v.text if v is not None and v.text is not None else ""
                    if t == "s":
                        try:
                            texto = self._strings[int(texto)]
                        except (ValueError, IndexError):
                            pass
                    elif t == "inlineStr":
                        texto = "".join((x.text or "") for x in c.iter(_NS + "t"))
                    elif t == "b":
                        texto = "VERDADEIRO" if texto == "1" else "FALSO"
                    elif t == "n" and texto:
                        s = int(c.get("s", "0"))
                        eh_data = s < len(self._estilos_data) and self._estilos_data[s]
                        if eh_data:
                            d = util.parse_data(texto, "excel")
                            texto = d["data"] + (" " + d["hora"] if d["hora"] else "") if d["data"] else texto
                        else:
                            texto = _numero_para_texto(texto)
                    valores[col] = texto
                el.clear()
                if valores:
                    linha = [""] * (max(valores) + 1)
                    for k, val in valores.items():
                        linha[k] = val
                    yield num, linha


def _numero_para_texto(v):
    """Número de célula XLSX (ponto decimal) em texto com vírgula decimal e sem milhar."""
    try:
        d = Decimal(v)
    except InvalidOperation:
        return v
    if d == d.to_integral_value():
        return str(int(d))
    q = d.quantize(Decimal("0.01"))
    if abs(q - d) < Decimal("0.0000001"):
        d = q
    s = format(d, "f")
    return s.replace(".", ",")


# ---------------------------------------------------------------- PDF (texto)

class _Nome(str):
    pass


class _Ref(tuple):
    pass


_WS = b" \t\r\n\f\x00"
_DELIM = b"()<>[]{}/%"


class _Parser:
    def __init__(self, dados, pos=0):
        self.d = dados
        self.p = pos

    def pular(self):
        d = self.d
        while self.p < len(d):
            c = d[self.p:self.p + 1]
            if c in (b" ", b"\t", b"\r", b"\n", b"\f", b"\x00"):
                self.p += 1
            elif c == b"%":
                while self.p < len(d) and d[self.p:self.p + 1] not in (b"\r", b"\n"):
                    self.p += 1
            else:
                break

    def token_bruto(self):
        self.pular()
        ini = self.p
        while self.p < len(self.d) and self.d[self.p] not in _WS and self.d[self.p] not in _DELIM:
            self.p += 1
        return self.d[ini:self.p]

    def literal(self):
        self.p += 1
        prof, out = 1, bytearray()
        d = self.d
        while self.p < len(d):
            c = d[self.p]
            if c == 0x5C:
                self.p += 1
                if self.p >= len(d):
                    break
                e = d[self.p]
                mapa = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}
                if e in mapa:
                    out.append(mapa[e])
                elif 0x30 <= e <= 0x37:
                    oct_s = bytes([e])
                    for _ in range(2):
                        if self.p + 1 < len(d) and 0x30 <= d[self.p + 1] <= 0x37:
                            self.p += 1
                            oct_s += bytes([d[self.p]])
                    out.append(int(oct_s, 8) & 0xFF)
                elif e in (13, 10):
                    if e == 13 and self.p + 1 < len(d) and d[self.p + 1] == 10:
                        self.p += 1
                else:
                    out.append(e)
            elif c == 0x28:
                prof += 1
                out.append(c)
            elif c == 0x29:
                prof -= 1
                if prof == 0:
                    self.p += 1
                    return bytes(out)
                out.append(c)
            else:
                out.append(c)
            self.p += 1
        return bytes(out)

    def hexa(self):
        fim = self.d.index(b">", self.p)
        h = re.sub(rb"[^0-9A-Fa-f]", b"", self.d[self.p + 1:fim])
        if len(h) % 2:
            h += b"0"
        self.p = fim + 1
        return bytes.fromhex(h.decode())

    def objeto(self):
        self.pular()
        d = self.d
        if self.p >= len(d):
            return None
        c = d[self.p:self.p + 1]
        if c == b"<" and d[self.p:self.p + 2] == b"<<":
            self.p += 2
            res = {}
            while True:
                self.pular()
                if d[self.p:self.p + 2] == b">>":
                    self.p += 2
                    return res
                if self.p >= len(d):
                    return res
                k = self.objeto()
                v = self.objeto()
                if isinstance(k, _Nome):
                    res[str(k)] = v
        if c == b"<":
            return self.hexa()
        if c == b"(":
            return self.literal()
        if c == b"[":
            self.p += 1
            arr = []
            while True:
                self.pular()
                if d[self.p:self.p + 1] == b"]" or self.p >= len(d):
                    self.p += 1
                    return arr
                arr.append(self.objeto())
        if c == b"/":
            self.p += 1
            t = self.token_bruto()
            t = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), t)
            return _Nome(t.decode("latin-1"))
        if c in (b"]", b">", b")", b"}", b"{"):
            self.p += 1
            return None
        t = self.token_bruto()
        if not t:
            self.p += 1
            return None
        if re.fullmatch(rb"[+\-]?\d+", t):
            salvo = self.p
            t2 = self.token_bruto()
            if re.fullmatch(rb"\d+", t2 or b""):
                t3 = self.token_bruto()
                if t3 == b"R":
                    return _Ref((int(t), int(t2)))
            self.p = salvo
            return int(t)
        if re.fullmatch(rb"[+\-]?(\d+\.?\d*|\.\d+)", t):
            return float(t)
        if t == b"true":
            return True
        if t == b"false":
            return False
        if t == b"null":
            return None
        return _Nome("op:" + t.decode("latin-1"))


def _png_predictor(dados, colunas, cores=1, bits=8):
    bpp = max(1, cores * bits // 8)
    larg = colunas * bpp
    out = bytearray()
    ant = bytearray(larg)
    i = 0
    while i < len(dados):
        tipo = dados[i]
        linha = bytearray(dados[i + 1:i + 1 + larg])
        i += 1 + larg
        for x in range(len(linha)):
            a = linha[x - bpp] if x >= bpp else 0
            b = ant[x] if x < len(ant) else 0
            c = ant[x - bpp] if x >= bpp else 0
            if tipo == 1:
                linha[x] = (linha[x] + a) & 0xFF
            elif tipo == 2:
                linha[x] = (linha[x] + b) & 0xFF
            elif tipo == 3:
                linha[x] = (linha[x] + (a + b) // 2) & 0xFF
            elif tipo == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                linha[x] = (linha[x] + pr) & 0xFF
        out += linha
        ant = linha
    return bytes(out)


class LeitorPDF:
    """Extração simples de texto de PDF com texto selecionável. Não faz OCR."""

    def __init__(self, dados):
        self.d = dados
        self.objs = {}
        self.streams = {}
        self.avisos = []
        self._indexar()

    def _indexar(self):
        d = self.d
        for m in re.finditer(rb"(?<![\d])(\d+)\s+(\d+)\s+obj\b", d):
            num = int(m.group(1))
            p = _Parser(d, m.end())
            try:
                obj = p.objeto()
            except (ValueError, IndexError):
                continue
            self.objs[num] = obj
            p.pular()
            if isinstance(obj, dict) and d[p.p:p.p + 6] == b"stream":
                ini = p.p + 6
                if d[ini:ini + 2] == b"\r\n":
                    ini += 2
                elif d[ini:ini + 1] in (b"\n", b"\r"):
                    ini += 1
                tam = obj.get("Length")
                fim = None
                if isinstance(tam, int) and d[ini + tam:ini + tam + 20].lstrip().startswith(b"endstream"):
                    fim = ini + tam
                if fim is None:
                    fim = d.find(b"endstream", ini)
                    if fim < 0:
                        fim = len(d)
                    while fim > ini and d[fim - 1:fim] in (b"\r", b"\n"):
                        fim -= 1
                self.streams[num] = (obj, d[ini:fim])
        for num, (dic, _) in list(self.streams.items()):
            if dic.get("Type") == "ObjStm":
                try:
                    dados = self.decodificar(num)
                    n, primeiro = int(dic.get("N", 0)), int(dic.get("First", 0))
                    cab = _Parser(dados, 0)
                    pares = []
                    for _ in range(n):
                        pares.append((cab.objeto(), cab.objeto()))
                    for onum, off in pares:
                        if isinstance(onum, int) and isinstance(off, int) and onum not in self.objs:
                            self.objs[onum] = _Parser(dados, primeiro + off).objeto()
                except Exception as e:  # noqa: BLE001 - PDF malformado não deve interromper
                    self.avisos.append("fluxo de objetos %d ilegível: %s" % (num, e))

    def r(self, v):
        prof = 0
        while isinstance(v, _Ref) and prof < 20:
            v = self.objs.get(v[0])
            prof += 1
        return v

    def decodificar(self, num):
        dic, bruto = self.streams[num]
        filtros = self.r(dic.get("Filter"))
        if filtros is None:
            filtros = []
        elif not isinstance(filtros, list):
            filtros = [filtros]
        parms = self.r(dic.get("DecodeParms"))
        dados = bruto
        for i, f in enumerate(filtros):
            f = str(self.r(f))
            if f in ("FlateDecode", "Fl"):
                try:
                    dados = zlib.decompress(dados)
                except zlib.error:
                    dados = zlib.decompressobj().decompress(dados)
                p = parms[i] if isinstance(parms, list) and i < len(parms) else parms
                p = self.r(p)
                if isinstance(p, dict) and int(p.get("Predictor", 1) or 1) >= 10:
                    dados = _png_predictor(dados, int(p.get("Columns", 1)), int(p.get("Colors", 1)),
                                           int(p.get("BitsPerComponent", 8)))
            elif f in ("ASCIIHexDecode", "AHx"):
                dados = bytes.fromhex(re.sub(rb"[^0-9A-Fa-f]", b"", dados.split(b">")[0]).decode())
            else:
                raise ValueError("filtro não suportado: %s" % f)
        return dados

    def _num_de(self, ref):
        return ref[0] if isinstance(ref, _Ref) else None

    def paginas(self):
        raiz = None
        for num, o in self.objs.items():
            if isinstance(o, dict) and o.get("Type") == "Catalog":
                raiz = o
                break
        resultado = []
        if raiz is None:
            for num in sorted(self.objs):
                o = self.objs[num]
                if isinstance(o, dict) and o.get("Type") == "Page":
                    resultado.append((o, self.r(o.get("Resources")) or {}))
            return resultado

        def visitar(no, recursos, prof=0):
            no = self.r(no)
            if not isinstance(no, dict) or prof > 50:
                return
            rec = self.r(no.get("Resources")) or recursos
            if no.get("Type") == "Pages" or "Kids" in no:
                for k in self.r(no.get("Kids")) or []:
                    visitar(k, rec, prof + 1)
            else:
                resultado.append((no, rec))
        visitar(raiz.get("Pages"), {})
        return resultado

    def _cmap(self, fonte):
        fonte = self.r(fonte)
        if not isinstance(fonte, dict):
            return None, 1
        tu = fonte.get("ToUnicode")
        num = self._num_de(tu)
        largura = 2 if fonte.get("Subtype") == "Type0" else 1
        if num is None or num not in self.streams:
            return None, largura
        try:
            texto = self.decodificar(num)
        except Exception:  # noqa: BLE001
            return None, largura
        mapa = {}
        for bloco in re.findall(rb"beginbfchar(.*?)endbfchar", texto, re.S):
            for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", bloco):
                mapa[int(a, 16)] = bytes.fromhex(b.decode()).decode("utf-16-be", "replace")
                largura = len(a) // 2
        for bloco in re.findall(rb"beginbfrange(.*?)endbfrange", texto, re.S):
            for a, b, c in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]+>|\[[^\]]*\])", bloco):
                ini, fim = int(a, 16), int(b, 16)
                largura = len(a) // 2
                if c.startswith(b"["):
                    alvos = re.findall(rb"<([0-9A-Fa-f]+)>", c)
                    for i, alvo in enumerate(alvos):
                        mapa[ini + i] = bytes.fromhex(alvo.decode()).decode("utf-16-be", "replace")
                else:
                    base = int(c[1:-1], 16)
                    nbytes = (len(c) - 2) // 2
                    for i in range(min(fim - ini + 1, 65536)):
                        mapa[ini + i] = (base + i).to_bytes(max(2, nbytes), "big").decode("utf-16-be", "replace")
        return mapa, largura

    def texto_paginas(self):
        saida = []
        for pagina, recursos in self.paginas():
            fontes = self.r((recursos or {}).get("Font")) or {}
            cmaps = {}
            for nome, f in fontes.items():
                cmaps[nome] = self._cmap(f)
            conteudo = self.r(pagina.get("Contents"))
            refs = pagina.get("Contents")
            if isinstance(conteudo, list):
                refs = conteudo
            elif not isinstance(refs, list):
                refs = [refs]
            dados = b""
            for ref in refs:
                n = self._num_de(ref)
                if n is not None and n in self.streams:
                    try:
                        dados += self.decodificar(n) + b"\n"
                    except Exception as e:  # noqa: BLE001
                        self.avisos.append("conteúdo de página ilegível: %s" % e)
            saida.append(self._texto_conteudo(dados, cmaps))
        return saida

    def _texto_conteudo(self, dados, cmaps):
        p = _Parser(dados)
        pilha, out = [], []
        fonte_atual = (None, 1)

        def decod(s):
            mapa, larg = fonte_atual
            if mapa:
                res = []
                for i in range(0, len(s), larg):
                    cod = int.from_bytes(s[i:i + larg], "big")
                    res.append(mapa.get(cod, ""))
                return "".join(res)
            if larg == 2:
                return ""
            return s.decode("cp1252", "replace")

        while p.p < len(dados):
            ini = p.p
            o = p.objeto()
            if p.p == ini:
                p.p += 1
                continue
            if isinstance(o, _Nome) and o.startswith("op:"):
                op = o[3:]
                if op == "BI":
                    fim = dados.find(b"EI", p.p)
                    p.p = len(dados) if fim < 0 else fim + 2
                elif op == "Tf" and len(pilha) >= 2:
                    fonte_atual = cmaps.get(str(pilha[-2]), (None, 1))
                elif op == "Tj" and pilha and isinstance(pilha[-1], bytes):
                    out.append(decod(pilha[-1]))
                elif op in ("'", '"') and pilha and isinstance(pilha[-1], bytes):
                    out.append("\n" + decod(pilha[-1]))
                elif op == "TJ" and pilha and isinstance(pilha[-1], list):
                    for item in pilha[-1]:
                        if isinstance(item, bytes):
                            out.append(decod(item))
                        elif isinstance(item, (int, float)) and item < -200:
                            out.append(" ")
                elif op in ("Td", "TD") and len(pilha) >= 2:
                    if isinstance(pilha[-1], (int, float)) and pilha[-1] != 0:
                        out.append("\n")
                    elif isinstance(pilha[-2], (int, float)) and pilha[-2] > 0:
                        out.append(" ")
                elif op in ("T*", "ET"):
                    out.append("\n")
                elif op == "Tm":
                    out.append("\n")
                pilha = []
            else:
                pilha.append(o)
        texto = "".join(out)
        texto = re.sub(r"[ \t]+\n", "\n", texto)
        return re.sub(r"\n{3,}", "\n\n", texto).strip()


def texto_pdf(caminho):
    """Lista de textos por página. Usa pypdf se estiver instalado; senão o leitor interno."""
    with open(caminho, "rb") as f:
        dados = f.read()
    avisos = []
    try:
        import pypdf  # type: ignore
        leitor = pypdf.PdfReader(io.BytesIO(dados))
        return [(pg.extract_text() or "") for pg in leitor.pages], ["texto extraído com pypdf"]
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        avisos = ["pypdf falhou (%s); usado leitor interno" % e]
    leitor = LeitorPDF(dados)
    paginas = leitor.texto_paginas()
    return paginas, avisos + leitor.avisos
