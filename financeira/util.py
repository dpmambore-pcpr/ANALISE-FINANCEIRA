"""Funções determinísticas de conversão. Nada aqui usa ponto flutuante para dinheiro."""

import datetime as _dt
import hashlib
import json
import re
import unicodedata

_RE_ESPACOS = re.compile(r"\s+")


def agora_iso():
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_bytes(dados):
    return hashlib.sha256(dados).hexdigest()


def sha256_arquivo(caminho, bloco=1024 * 1024):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while True:
            b = f.read(bloco)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def json_dump(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def so_digitos(texto):
    return "".join(ch for ch in str(texto or "") if ch.isdigit())


def sem_acentos(texto):
    n = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(ch for ch in n if not unicodedata.combining(ch))


def normalizar_nome(texto):
    """Chave de agrupamento. Não substitui a grafia original, que é sempre preservada."""
    t = sem_acentos(texto).upper().strip()
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    return _RE_ESPACOS.sub(" ", t).strip()


def normalizar_cabecalho(texto):
    return normalizar_nome(texto).replace(" ", "_")


# ---------------------------------------------------------------- valores

def parse_valor(texto):
    """Converte texto monetário em centavos inteiros.

    Retorna dict: centavos (int >= 0 ou None), sinal (+1, -1 ou 0 quando não há sinal),
    ambiguo (bool), motivo (str).
    Regras: com ponto e vírgula, o último separador é o decimal; só vírgula = decimal;
    só ponto com exatamente 3 dígitos depois é ambíguo (pode ser milhar) e fica pendente.
    """
    bruto = "" if texto is None else str(texto).strip()
    res = {"centavos": None, "sinal": 0, "ambiguo": False, "motivo": ""}
    if not bruto:
        res["motivo"] = "valor vazio"
        return res
    t = bruto.replace("R$", "").replace("\u00a0", " ").replace(" ", "")
    sinal = 0
    if t.startswith("(") and t.endswith(")"):
        sinal, t = -1, t[1:-1]
    if t.endswith("-"):
        sinal, t = -1, t[:-1]
    if t.startswith("-"):
        sinal, t = -1, t[1:]
    elif t.startswith("+"):
        sinal, t = 1, t[1:]
    t_up = t.upper()
    if t_up.endswith("D") and t_up[:-1].replace(".", "").replace(",", "").isdigit():
        res["motivo"] = "sufixo D/C no valor; mapeie a natureza separadamente"
        res["ambiguo"] = True
        t = t[:-1]
    elif t_up.endswith("C") and t_up[:-1].replace(".", "").replace(",", "").isdigit():
        res["motivo"] = "sufixo D/C no valor; mapeie a natureza separadamente"
        res["ambiguo"] = True
        t = t[:-1]
    if not re.fullmatch(r"[0-9.,]+", t or "x"):
        res["motivo"] = "valor não numérico: %r" % bruto
        return res
    tem_ponto, tem_virgula = "." in t, "," in t
    if tem_ponto and tem_virgula:
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        mil = "." if dec == "," else ","
        inteiro, _, frac = t.replace(mil, "").partition(dec)
    elif tem_virgula:
        if t.count(",") > 1:
            inteiro, frac = t.replace(",", ""), ""
            partes = t.split(",")
            if not all(len(p) == 3 for p in partes[1:]):
                res["motivo"] = "separadores inconsistentes: %r" % bruto
                return res
        else:
            inteiro, _, frac = t.partition(",")
    elif tem_ponto:
        partes = t.split(".")
        if len(partes) > 2:
            if not all(len(p) == 3 for p in partes[1:]):
                res["motivo"] = "separadores inconsistentes: %r" % bruto
                return res
            inteiro, frac = "".join(partes), ""
        else:
            inteiro, frac = partes
            if len(frac) == 3:
                res["ambiguo"] = True
                res["motivo"] = "ponto seguido de 3 dígitos pode ser milhar ou decimal: %r" % bruto
                return res
    else:
        inteiro, frac = t, ""
    if len(frac) > 2:
        if frac[2:].strip("0"):
            res["motivo"] = "mais de 2 casas decimais: %r" % bruto
            res["ambiguo"] = True
            return res
        frac = frac[:2]
    inteiro = inteiro or "0"
    if not inteiro.isdigit() or (frac and not frac.isdigit()):
        res["motivo"] = "valor não numérico: %r" % bruto
        return res
    res["centavos"] = int(inteiro) * 100 + int((frac + "00")[:2])
    res["sinal"] = sinal
    return res


def parse_centavos_sem_separador(texto):
    """Campo numérico SIMBA: '10000' = R$ 100,00."""
    t = str(texto or "").strip()
    if not t:
        return None
    if t.startswith("-"):
        return None
    if not t.isdigit():
        return None
    return int(t)


def formatar_centavos(c):
    if c is None:
        return ""
    neg = c < 0
    c = abs(int(c))
    inteiro, frac = divmod(c, 100)
    s = "{:,}".format(inteiro).replace(",", ".")
    return ("-" if neg else "") + "R$ %s,%02d" % (s, frac)


# ---------------------------------------------------------------- datas

_RE_DATA_BR = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?(?:[.,]\d+)?)?\s*(.*)$")
_RE_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?)?\s*(Z|[+\-]\d{2}:?\d{2}|UTC|GMT[+\-]?\d*)?\s*$", re.I)
_RE_DDMMAAAA = re.compile(r"^(\d{2})(\d{2})(\d{4})$")
_RE_HORA = re.compile(r"^(\d{1,2}):?(\d{2}):?(\d{2})?$")


def _valida(a, m, d):
    try:
        _dt.date(a, m, d)
        return True
    except ValueError:
        return False


def parse_data(texto, formato=None):
    """Retorna dict data (AAAA-MM-DD), hora (HH:MM:SS ou None), fuso (texto original ou None), motivo.

    Não converte fuso horário: o fuso informado é preservado como texto.
    formato: None (auto), 'ddmmaaaa' (SIMBA), 'excel' (número serial).
    """
    bruto = "" if texto is None else str(texto).strip()
    res = {"data": None, "hora": None, "fuso": None, "motivo": ""}
    if not bruto:
        res["motivo"] = "data vazia"
        return res
    if formato == "ddmmaaaa" or _RE_DDMMAAAA.match(bruto):
        m = _RE_DDMMAAAA.match(bruto)
        if m:
            d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if _valida(a, mes, d):
                res["data"] = "%04d-%02d-%02d" % (a, mes, d)
                return res
        res["motivo"] = "data inválida (ddmmaaaa): %r" % bruto
        return res
    if formato == "excel":
        try:
            serial = float(bruto)
            base = _dt.datetime(1899, 12, 30)
            dtv = base + _dt.timedelta(days=serial)
            dtv = dtv.replace(microsecond=0)
            res["data"] = dtv.strftime("%Y-%m-%d")
            if abs(serial - int(serial)) > 1e-9:
                res["hora"] = dtv.strftime("%H:%M:%S")
            return res
        except ValueError:
            pass
    m = _RE_DATA_ISO.match(bruto)
    if m:
        a, mes, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not _valida(a, mes, d):
            res["motivo"] = "data inválida: %r" % bruto
            return res
        res["data"] = "%04d-%02d-%02d" % (a, mes, d)
        if m.group(4):
            res["hora"] = "%02d:%02d:%02d" % (int(m.group(4)), int(m.group(5)), int(m.group(6) or 0))
        if m.group(7):
            res["fuso"] = m.group(7).upper()
        return res
    m = _RE_DATA_BR.match(bruto)
    if m:
        d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a < 100:
            res["motivo"] = "ano com 2 dígitos: %r (confira o século)" % bruto
            return res
        if not _valida(a, mes, d):
            res["motivo"] = "data inválida (dia/mês/ano): %r" % bruto
            return res
        res["data"] = "%04d-%02d-%02d" % (a, mes, d)
        if m.group(4):
            res["hora"] = "%02d:%02d:%02d" % (int(m.group(4)), int(m.group(5)), int(m.group(6) or 0))
        resto = (m.group(7) or "").strip()
        if resto:
            res["fuso"] = resto
        return res
    res["motivo"] = "formato de data não reconhecido: %r" % bruto
    return res


def parse_hora(texto):
    t = str(texto or "").strip()
    m = _RE_HORA.match(t)
    if not m:
        return None
    h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if h > 23 or mi > 59 or s > 59:
        return None
    return "%02d:%02d:%02d" % (h, mi, s)


# ---------------------------------------------------------------- CPF / CNPJ

def _dv_cpf(base9):
    s = sum(int(base9[i]) * (10 - i) for i in range(9))
    d1 = (s * 10 % 11) % 10
    s = sum(int((base9 + str(d1))[i]) * (11 - i) for i in range(10))
    d2 = (s * 10 % 11) % 10
    return "%d%d" % (d1, d2)


def cpf_valido(d):
    d = so_digitos(d)
    if len(d) != 11 or d == d[0] * 11:
        return False
    return _dv_cpf(d[:9]) == d[9:]


def _dv_cnpj(base12):
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s = sum(int(base12[i]) * p1[i] for i in range(12))
    d1 = 0 if s % 11 < 2 else 11 - s % 11
    p2 = [6] + p1
    b = base12 + str(d1)
    s = sum(int(b[i]) * p2[i] for i in range(13))
    d2 = 0 if s % 11 < 2 else 11 - s % 11
    return "%d%d" % (d1, d2)


def cnpj_valido(d):
    d = so_digitos(d)
    if len(d) != 14 or d == d[0] * 14:
        return False
    return _dv_cnpj(d[:12]) == d[12:]


def classificar_documento(texto, tipo_pessoa=None):
    """Classifica CPF/CNPJ sem descartar o original.

    Retorna (tipo, normalizado). tipo: cpf, cnpj, cpf_dv_invalido, cnpj_dv_invalido,
    parcial (com máscara/asteriscos ou dígitos faltando), vazio ou outro.
    tipo_pessoa: '1' natural, '2' jurídica (SIMBA), usado para completar zeros à esquerda.
    """
    bruto = str(texto or "").strip()
    if not bruto:
        return "vazio", ""
    if any(ch in bruto for ch in "*xX#•"):
        return "parcial", bruto
    d = so_digitos(bruto)
    if not d:
        return "outro", bruto
    if tipo_pessoa == "1" and len(d) < 11:
        d = d.zfill(11)
    elif tipo_pessoa == "2" and len(d) < 14:
        d = d.zfill(14)
    if len(d) == 11:
        return ("cpf" if cpf_valido(d) else "cpf_dv_invalido"), d
    if len(d) == 14:
        return ("cnpj" if cnpj_valido(d) else "cnpj_dv_invalido"), d
    return "parcial", d


def formatar_documento(d):
    d = so_digitos(d)
    if len(d) == 11:
        return "%s.%s.%s-%s" % (d[:3], d[3:6], d[6:9], d[9:])
    if len(d) == 14:
        return "%s.%s.%s/%s-%s" % (d[:2], d[2:5], d[5:8], d[8:12], d[12:])
    return d


def gerar_cpf_ficticio(n):
    base = "%09d" % n
    return base + _dv_cpf(base)


def gerar_cnpj_ficticio(n):
    base = "%08d0001" % n
    return base + _dv_cnpj(base)


def norm_doc(texto):
    """Chave de agrupamento de CPF/CNPJ: só dígitos quando completo; senão o texto original."""
    if texto is None or str(texto).strip() == "":
        return None
    d = so_digitos(texto)
    if len(d) in (11, 14) and not any(ch in str(texto) for ch in "*xX#"):
        return d
    return str(texto).strip()
