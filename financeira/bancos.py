"""Código COMPE (número do banco) → nome usual, para filtros e listas.

O extrato muitas vezes traz só o número (260, 001). O filtro e a tabela mostram
também o nome (260 Nubank). O valor gravado no caso não muda.
"""

import re

from . import util

# Códigos COMPE de 3 dígitos (Bacen). Nomes curtos, como o analista fala no dia a dia.
BANCOS_COMPE = {
    "001": "Banco do Brasil",
    "003": "Banco da Amazônia",
    "004": "Banco do Nordeste",
    "007": "BNDES",
    "010": "CREDICOAMO",
    "012": "Inbursa",
    "021": "Banestes",
    "024": "Banco Bandepe",
    "025": "Banco Alfa",
    "029": "Itaú Consignado",
    "033": "Santander",
    "037": "Banpará",
    "041": "Banrisul",
    "047": "Banese",
    "062": "Hipercard",
    "063": "Bradescard",
    "064": "Goldman Sachs",
    "065": "Andbank",
    "069": "Banco Crefisa",
    "070": "BRB",
    "074": "Banco J. Safra",
    "075": "Banco ABN AMRO",
    "077": "Banco Inter",
    "079": "Banco Original do Agronegócio",
    "081": "BancoSeguro",
    "082": "Banco Topázio",
    "083": "Banco da China Brasil",
    "084": "Uniprime Norte do Paraná",
    "085": "Ailos (Cecred)",
    "089": "CREDISAN",
    "093": "Pólocred",
    "094": "Banco Finaxis",
    "095": "Travelex Banco",
    "096": "Banco B3",
    "097": "Credisis",
    "102": "XP Investimentos",
    "104": "Caixa Econômica",
    "107": "Banco Bocom BBM",
    "119": "Banco Western Union",
    "120": "Banco Rodobens",
    "121": "Agibank",
    "122": "Banco Bradesco BERJ",
    "124": "Banco Woori Bank",
    "125": "Banco Genial",
    "128": "MS Bank",
    "129": "UBS Brasil",
    "130": "Caruana",
    "133": "Cresol",
    "136": "Unicred",
    "169": "Banco Olé Bonsucesso",
    "173": "BRL Trust",
    "174": "Pefisa",
    "177": "Guide",
    "184": "Banco Itaú BBA",
    "188": "Ativa Investimentos",
    "189": "HS Financeira",
    "190": "Servicoop",
    "191": "Nova Futura",
    "194": "Parmetal",
    "196": "Fair Corretora",
    "197": "Stone",
    "208": "BTG Pactual",
    "212": "Banco Original",
    "213": "Banco Arbi",
    "217": "Banco John Deere",
    "218": "Banco BS2",
    "222": "Credit Agricole",
    "224": "Banco Fibra",
    "233": "Banco Cifra",
    "237": "Bradesco",
    "241": "Banco Clássico",
    "243": "Banco Máxima",
    "246": "Banco ABC Brasil",
    "249": "Banco Investcred Unibanco",
    "250": "BCV",
    "253": "Bexs",
    "254": "Paraná Banco",
    "259": "Moneycorp",
    "260": "Nubank",
    "265": "Banco Fator",
    "266": "Banco Cédula",
    "268": "Barigui",
    "269": "HSBC Brasil",
    "270": "Sagitur",
    "271": "IB Corretora",
    "273": "CCR de São Miguel do Oeste",
    "274": "Money Plus",
    "276": "Senff",
    "278": "Genial Investimentos",
    "279": "CCR de Primavera do Leste",
    "280": "Avista",
    "281": "Cooperativa de Crédito",
    "283": "RB Investimentos",
    "285": "Frente Corretora",
    "286": "CCR de Ouro",
    "288": "Carol",
    "290": "PagSeguro",
    "292": "BS2",
    "293": "Lastro RDV",
    "296": "Vision",
    "298": "Vip's",
    "299": "Sorocred",
    "300": "Banco de la Nación Argentina",
    "301": "BPP",
    "306": "Portopar",
    "307": "Terra Investimentos",
    "309": "CAMBIONET",
    "310": "Vortx",
    "318": "Banco BMG",
    "320": "Banco CCB Brasil",
    "323": "Mercado Pago",
    "326": "Parati",
    "329": "QI Sociedade de Crédito",
    "330": "Banco Bari",
    "331": "Fram Capital",
    "332": "Acesso Soluções",
    "335": "Banco Digio",
    "336": "C6 Bank",
    "340": "Super Pagamentos",
    "341": "Itaú Unibanco",
    "342": "Creditas",
    "348": "Banco XP",
    "349": "AL5 S.A.",
    "352": "Toro CTVM",
    "355": "Órama",
    "362": "Cielo",
    "364": "Egerie (Gerencianet)",
    "365": "Solidus",
    "366": "Banco Société Générale",
    "370": "Banco Mizuho",
    "374": "Realize",
    "376": "Banco J.P. Morgan",
    "380": "PicPay",
    "383": "Juno / Boleto Bancário",
    "384": "Global SCM",
    "387": "Banco Toyota",
    "389": "Banco Mercantil do Brasil",
    "394": "Banco Bradesco Financiamentos",
    "399": "Kirton Bank",
    "403": "Cora",
    "404": "SumUp",
    "408": "Bônuscred",
    "412": "Banco Capital",
    "422": "Banco Safra",
    "456": "Banco MUFG Brasil",
    "464": "Banco Sumitomo Mitsui",
    "473": "Banco Caixa Geral Brasil",
    "477": "Citibank",
    "479": "Bank of America",
    "487": "Deutsche Bank",
    "488": "JPMorgan Chase",
    "492": "ING Bank",
    "495": "Banco de La Provincia de Buenos Aires",
    "505": "Credit Suisse",
    "545": "Senso",
    "600": "Banco Luso Brasileiro",
    "604": "Banco Industrial do Brasil",
    "610": "Banco VR",
    "611": "Banco Paulista",
    "612": "Banco Guanabara",
    "613": "Omni Banco",
    "623": "Banco Pan",
    "626": "Banco Ficsa / C6 CFI",
    "630": "Banco Smartbank",
    "633": "Banco Rendimento",
    "634": "Banco Triângulo",
    "637": "Banco Sofisa",
    "643": "Banco Pine",
    "652": "Itaú Unibanco Holding",
    "653": "Banco Voiter",
    "654": "Banco Digimais",
    "655": "Banco Votorantim",
    "707": "Banco Daycoval",
    "712": "Banco Ourinvest",
    "739": "Banco Cetelem",
    "741": "Banco Ribeirão Preto",
    "743": "Banco Semear",
    "745": "Banco Citibank",
    "746": "Banco Modal",
    "747": "Banco Rabobank",
    "748": "Sicredi",
    "751": "Scotiabank Brasil",
    "752": "Banco BNP Paribas",
    "753": "Novo Banco Continental",
    "754": "Banco Sistema",
    "755": "Bank of America Merrill Lynch",
    "756": "Sicoob",
    "757": "Banco KEB Hana",
}

_RE_SO_NUMERO = re.compile(r"^\d+$")


def codigo_compe(valor):
    """Devolve o código COMPE de 3 dígitos, ou None se não for um número de banco."""
    d = util.so_digitos(valor or "")
    if not d:
        return None
    d = d.lstrip("0") or "0"
    if len(d) > 3:
        return None
    return d.zfill(3)


def nome_banco(valor):
    cod = codigo_compe(valor)
    return BANCOS_COMPE.get(cod) if cod else None


def rotulo_banco(valor):
    """'260' → '260 Nubank'. Nome já escrito no extrato permanece."""
    s = (valor or "").strip()
    if not s:
        return s
    if s in ("?", "(não informado)", "(vazio)"):
        return s
    nome = nome_banco(s)
    if not nome:
        return s
    if _RE_SO_NUMERO.fullmatch(s):
        return "%s %s" % (codigo_compe(s), nome)
    if nome.lower() in s.lower():
        return s
    return "%s · %s" % (s, nome)


def rotulo_conta(valor):
    """'260 | ag 0001 | conta 123' → '260 Nubank | ag 0001 | conta 123'."""
    s = valor or ""
    if " | ag " in s:
        banco, resto = s.split(" | ag ", 1)
        return "%s | ag %s" % (rotulo_banco(banco), resto)
    if "|" in s and " | " not in s:
        partes = s.split("|")
        partes[0] = rotulo_banco(partes[0])
        return "|".join(partes)
    return rotulo_banco(s)


def rotulo_conta_partes(banco, agencia, conta):
    return "%s | ag %s | conta %s" % (rotulo_banco(banco or "?"), agencia or "?", conta or "?")
