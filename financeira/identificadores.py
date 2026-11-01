"""Extração de identificadores de texto livre (PDF, observações, RIF).

Os resultados são candidatos a revisão: um número com formato de CPF não prova a
identidade de ninguém. A grafia original é preservada junto ao valor normalizado.
"""

import ipaddress
import re

from . import util

TIPOS = {
    "cpf": "CPF",
    "cnpj": "CNPJ",
    "doc_parcial": "CPF/CNPJ incompleto ou mascarado",
    "nome": "Nome",
    "banco": "Banco / instituição",
    "conta": "Agência / conta",
    "pix": "Chave PIX",
    "pix_id": "ID de transação PIX",
    "email": "E-mail",
    "telefone": "Telefone",
    "ip": "Endereço IP",
    "coordenada": "Coordenada (lat, long)",
    "cidade": "Cidade / UF",
    "dispositivo": "Dispositivo / MAC",
    "data": "Data",
}

_RE_CPF_FMT = re.compile(r"(?<![\d.])(\d{3}\.\d{3}\.\d{3}-\d{2})(?![\d])")
_RE_CNPJ_FMT = re.compile(r"(?<![\d.])(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})(?![\d])")
_RE_DOC_MASC = re.compile(r"(?<![\w*])([\d*xX]{3}\.[\d*xX]{3}\.[\d*xX]{3}-[\d*xX]{2})(?![\w*])")
_RE_DIGITOS = re.compile(r"(?<![\d])(\d{11}|\d{14})(?![\d])")
_RE_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_RE_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_RE_E2E = re.compile(r"\bE\d{8}\d{12}[0-9A-Za-z]{11}\b")
_RE_TEL = re.compile(r"(?<![\d])(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[\s\-]?\d{4}(?![\d])")
_RE_IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
_RE_IPV6 = re.compile(r"(?<![:\w])((?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:(?:[0-9a-fA-F]{1,4})?)(?![:\w])")
_RE_COORD = re.compile(r"(?<![\d.])(-?\d{1,2}\.\d{3,8})\s*[,;]\s*(-?\d{1,3}\.\d{3,8})(?![\d.])")
_RE_DATA = re.compile(r"(?<![\d/])(\d{2}/\d{2}/\d{4})(?![\d/])")


def normalizar(tipo, valor):
    v = str(valor or "").strip()
    if tipo in ("cpf", "cnpj"):
        return util.so_digitos(v)
    if tipo == "nome":
        return util.normalizar_nome(v)
    if tipo == "email":
        return v.lower()
    if tipo == "telefone":
        return util.so_digitos(v)
    if tipo == "pix":
        if "@" in v:
            return v.lower()
        if _RE_UUID.fullmatch(v):
            return v.lower()
        d = util.so_digitos(v)
        if d and len(d) >= 10 and not re.search(r"[A-Za-z]", v):
            return d
        return v
    if tipo == "ip":
        try:
            return str(ipaddress.ip_address(v))
        except ValueError:
            return v
    if tipo in ("banco", "cidade", "conta", "dispositivo"):
        return util.normalizar_nome(v)
    return v


def tipo_documento(valor, tipo_pessoa=None):
    t, n = util.classificar_documento(valor, tipo_pessoa)
    if t in ("cpf", "cpf_dv_invalido"):
        return "cpf", n
    if t in ("cnpj", "cnpj_dv_invalido"):
        return "cnpj", n
    if t == "parcial":
        return "doc_parcial", n
    return None, n


def extrair(texto):
    """Lista de (tipo, original, normalizado). Sem deduplicação."""
    out = []
    if not texto:
        return out
    usados = []

    def marcar(m):
        usados.append((m.start(), m.end()))

    def livre(m):
        return not any(a < m.end() and m.start() < b for a, b in usados)

    for m in _RE_CNPJ_FMT.finditer(texto):
        out.append(("cnpj", m.group(1), util.so_digitos(m.group(1))))
        marcar(m)
    for m in _RE_CPF_FMT.finditer(texto):
        if livre(m):
            out.append(("cpf", m.group(1), util.so_digitos(m.group(1))))
            marcar(m)
    for m in _RE_DOC_MASC.finditer(texto):
        if livre(m) and re.search(r"[*xX]", m.group(1)):
            out.append(("doc_parcial", m.group(1), m.group(1)))
            marcar(m)
    for m in _RE_E2E.finditer(texto):
        out.append(("pix_id", m.group(0), m.group(0)))
        marcar(m)
    for m in _RE_UUID.finditer(texto):
        out.append(("pix", m.group(0), m.group(0).lower()))
        marcar(m)
    for m in _RE_EMAIL.finditer(texto):
        out.append(("email", m.group(0), m.group(0).lower()))
        marcar(m)
    for m in _RE_COORD.finditer(texto):
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            out.append(("coordenada", m.group(0), "%s,%s" % (m.group(1), m.group(2))))
            marcar(m)
    for m in _RE_IPV4.finditer(texto):
        if not livre(m):
            continue
        try:
            ipaddress.IPv4Address(m.group(1))
        except ValueError:
            continue
        out.append(("ip", m.group(1), m.group(1)))
        marcar(m)
    for m in _RE_IPV6.finditer(texto):
        if not livre(m):
            continue
        try:
            ip = ipaddress.IPv6Address(m.group(1))
        except ValueError:
            continue
        out.append(("ip", m.group(1), str(ip)))
        marcar(m)
    for m in _RE_DIGITOS.finditer(texto):
        if not livre(m):
            continue
        d = m.group(1)
        if len(d) == 11 and util.cpf_valido(d):
            out.append(("cpf", d, d))
            marcar(m)
        elif len(d) == 14 and util.cnpj_valido(d):
            out.append(("cnpj", d, d))
            marcar(m)
    for m in _RE_TEL.finditer(texto):
        if livre(m) and len(util.so_digitos(m.group(0))) >= 10:
            out.append(("telefone", m.group(0).strip(), util.so_digitos(m.group(0))))
            marcar(m)
    for m in _RE_DATA.finditer(texto):
        if livre(m):
            d = util.parse_data(m.group(1))
            if d["data"]:
                out.append(("data", m.group(1), d["data"]))
    return out
