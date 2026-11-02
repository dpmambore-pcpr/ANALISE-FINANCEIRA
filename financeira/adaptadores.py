"""Adaptadores de planilhas/CSV com mapeamento visual de colunas.

Extratos (movimentação), registros de acesso/IP/geolocalização e dados cadastrais ficam
em tabelas diferentes: dados cadastrais e geolocalização NUNCA viram transação financeira.
"""

import glob
import json
import os

from . import leitores, util

CAMPOS = {
    "extrato": [
        ("data", "Data"), ("hora", "Hora"), ("fuso", "Fuso horário"), ("valor", "Valor da transação"),
        ("credito", "Coluna de crédito"), ("debito", "Coluna de débito"), ("natureza", "Natureza (C/D)"),
        ("descricao", "Descrição / histórico"), ("tipo_operacao", "Tipo de operação"), ("documento", "Nº documento"),
        ("titular_nome", "Titular - nome"), ("titular_doc", "Titular - CPF/CNPJ"), ("banco", "Banco / instituição"),
        ("agencia", "Agência"), ("conta", "Conta"),
        ("cp_nome", "Contraparte - nome"), ("cp_doc", "Contraparte - CPF/CNPJ"), ("cp_banco", "Contraparte - banco"),
        ("cp_agencia", "Contraparte - agência"), ("cp_conta", "Contraparte - conta"),
        ("cp_valor", "Contraparte - valor da parcela"), ("pix_chave", "Chave PIX"), ("pix_id", "ID PIX (E2E)"),
        ("situacao", "Situação / status no banco"), ("estorno", "Valor de estorno"), ("ip", "IP"),
        ("cidade", "Cidade"), ("uf", "UF"), ("chave_lancamento", "Código do lançamento (agrupa linhas)"),
    ],
    "acessos": [
        ("data", "Data (ou data e hora)"), ("hora", "Hora"), ("fuso", "Fuso horário"), ("ip", "IP"), ("porta", "Porta"),
        ("latitude", "Latitude"), ("longitude", "Longitude"), ("coordenadas", "Coordenadas 'lat,long'"),
        ("precisao", "Precisão"), ("cidade", "Cidade"), ("uf", "UF"), ("pais", "País"), ("endereco", "Endereço"),
        ("dispositivo", "Dispositivo / modelo / MAC"), ("sistema", "Sistema / app"), ("evento", "Evento / operação"),
        ("nome", "Nome"), ("doc", "CPF/CNPJ"), ("telefone", "Telefone"), ("email", "E-mail"), ("banco", "Banco"),
        ("conta", "Conta"),
    ],
    "cadastro": [
        ("nome", "Nome"), ("doc", "CPF/CNPJ"), ("tipo_vinculo", "Vínculo (titular, cotitular, procurador...)"),
        ("banco", "Banco"), ("agencia", "Agência"), ("conta", "Conta"), ("endereco", "Endereço"), ("cidade", "Cidade"),
        ("uf", "UF"), ("cep", "CEP"), ("telefone", "Telefone"), ("email", "E-mail"), ("dispositivo", "Dispositivo"),
        ("data_inicio", "Início do vínculo / abertura"), ("data_fim", "Fim do vínculo / encerramento"),
    ],
}

SINONIMOS = {
    "data": ["DATA", "DATA_LANCAMENTO", "DATA_MOVIMENTO", "DATA_MOVIMENTACAO", "DT", "DT_LANCAMENTO", "DATA_TRANSACAO",
             "DATA_DA_TRANSACAO", "DATA_OPERACAO", "DATE", "DATA_HORA", "DATAHORA", "DATE_CREATED", "DATA_CRIACAO",
             "DATA_DO_ACESSO", "DATA_ACESSO", "DATA_HORA_ACESSO", "TIMESTAMP"],
    "hora": ["HORA", "HORARIO", "HORA_LANCAMENTO", "HORARIO_LANCAMENTO", "HORA_TRANSACAO", "TIME", "HORA_ACESSO"],
    "fuso": ["FUSO", "FUSO_HORARIO", "TIMEZONE", "TZ", "UTC_OFFSET"],
    "valor": ["VALOR", "VALOR_TRANSACAO", "VALOR_LANCAMENTO", "VALOR_DA_TRANSACAO", "VLR", "VALOR_R", "AMOUNT", "MONTANTE",
              "TRANSACTION_AMOUNT", "VALOR_OPERACAO"],
    "credito": ["CREDITO", "CREDITOS", "ENTRADA", "ENTRADAS", "VALOR_CREDITO"],
    "debito": ["DEBITO", "DEBITOS", "SAIDA", "SAIDAS", "VALOR_DEBITO"],
    "natureza": ["NATUREZA", "NATUREZA_LANCAMENTO", "D_C", "DC", "C_D", "CD", "TIPO_LANCAMENTO_CD", "SENTIDO", "NATUREZA_OPERACAO"],
    "descricao": ["DESCRICAO", "HISTORICO", "DESCRICAO_LANCAMENTO", "DESCRICAO_DO_LANCAMENTO", "LANCAMENTO", "DESCRIPTION", "MEMO"],
    "tipo_operacao": ["TIPO", "TIPO_OPERACAO", "TIPO_TRANSACAO", "TIPO_DE_TRANSACAO", "OPERACAO", "PAYOUT_TYPE", "TRANSACTION_TYPE"],
    "documento": ["DOCUMENTO", "NUMERO_DOCUMENTO", "NR_DOCUMENTO", "DOC", "NUM_DOC", "ID", "IDENTIFICADOR"],
    "titular_nome": ["TITULAR", "NOME_TITULAR", "CORRENTISTA", "NOME_CORRENTISTA", "CLIENTE", "NOME_CLIENTE"],
    "titular_doc": ["CPF_CNPJ_TITULAR", "CPF_TITULAR", "CNPJ_TITULAR", "DOC_TITULAR", "CPF_CNPJ_CLIENTE", "CPF_CLIENTE"],
    "banco": ["BANCO", "INSTITUICAO", "NOME_INSTITUICAO", "NUMERO_BANCO", "COD_COMP_INSTITUICAO", "INSTITUICAO_FINANCEIRA"],
    "agencia": ["AGENCIA", "NUMERO_AGENCIA", "AG"],
    "conta": ["CONTA", "NUMERO_CONTA", "CONTA_CORRENTE", "NR_CONTA"],
    "cp_nome": ["NOME_PESSOA_OD", "NOME_CONTRAPARTE", "CONTRAPARTE", "FAVORECIDO", "REMETENTE", "BENEFICIARIO", "NOME_OD",
                "ORIGEM_DESTINO", "NOME_ORIGEM_DESTINO", "COUNTERPART_NAME", "PAGADOR", "RECEBEDOR"],
    "cp_doc": ["CPF_CNPJ_OD", "CPF_CNPJ_CONTRAPARTE", "DOC_CONTRAPARTE", "CPF_CNPJ_FAVORECIDO", "CPF_CNPJ_REMETENTE",
               "CPF_CNPJ_ORIGEM_DESTINO", "COUNTERPART_DOCUMENT"],
    "cp_banco": ["NUMERO_BANCO_OD", "BANCO_OD", "BANCO_CONTRAPARTE", "COD_COMP_INSTITUICAO_OD", "BANCO_FAVORECIDO"],
    "cp_agencia": ["NUMERO_AGENCIA_OD", "AGENCIA_OD", "AGENCIA_CONTRAPARTE"],
    "cp_conta": ["NUMERO_CONTA_OD", "CONTA_OD", "CONTA_CONTRAPARTE"],
    "cp_valor": ["VALOR_TRANSACAO_OD", "VALOR_PARCELA", "VALOR_OD"],
    "pix_chave": ["CHAVE_PIX", "CHAVE_PIX_TRANSACAO", "CHAVE_PIX_PESSOA_OD", "PIX_KEY"],
    "pix_id": ["ID_TRANSACAO_PIX", "END_TO_END", "E2E", "ENDTOENDID", "END_TO_END_ID", "ID_PIX"],
    "situacao": ["STATUS", "SITUACAO", "PYN_STATUS", "PAYOUT_STATUS", "ESTADO"],
    "estorno": ["ESTORNO", "VALOR_ESTORNO", "REFUNDED_AMOUNT", "VALOR_DEVOLVIDO"],
    "ip": ["IP", "ENDERECO_IP", "IP_TRANSACAO", "IP_ACESSO", "IP_ORIGEM", "IP_ADDRESS", "IPV4", "IPV6"],
    "porta": ["PORTA", "PORTA_IP", "PORTA_LOGICA", "PORT", "PORTA_IP_HOME_BANKING"],
    "latitude": ["LATITUDE", "LAT"],
    "longitude": ["LONGITUDE", "LONG", "LNG", "LON"],
    "coordenadas": ["COORDENADAS", "GEOLOCALIZACAO", "GEOLOCATION", "LOCALIZACAO", "LAT_LONG", "LATLONG"],
    "precisao": ["PRECISAO", "ACCURACY", "RAIO"],
    "cidade": ["CIDADE", "MUNICIPIO", "CITY", "CIDADE_TRANSACAO"],
    "uf": ["UF", "ESTADO_UF", "STATE"],
    "pais": ["PAIS", "COUNTRY"],
    "endereco": ["ENDERECO", "LOGRADOURO", "ENDERECO_LOGRADOURO", "ADDRESS"],
    "dispositivo": ["DISPOSITIVO", "MODELO", "DEVICE", "APARELHO", "MAC", "MAC_ADDRESS", "DEVICE_ID", "ID_DISPOSITIVO"],
    "sistema": ["SISTEMA", "SISTEMA_OPERACIONAL", "OS", "APP", "USER_AGENT", "NAVEGADOR", "CANAL"],
    "evento": ["EVENTO", "ACAO", "OPERACAO", "TIPO_ACESSO", "EVENT"],
    "nome": ["NOME", "NOME_TITULAR", "NOME_CLIENTE", "NOME_COMPLETO", "RAZAO_SOCIAL"],
    "doc": ["CPF", "CNPJ", "CPF_CNPJ", "DOCUMENTO", "CPF_CNPJ_TITULAR", "DOC"],
    "telefone": ["TELEFONE", "CELULAR", "FONE", "PHONE", "TELEFONE_PESSOA"],
    "email": ["EMAIL", "E_MAIL", "MAIL"],
    "tipo_vinculo": ["TIPO_TITULAR", "VINCULO", "TIPO_VINCULO", "RELACIONAMENTO"],
    "cep": ["CEP", "ENDERECO_CEP"],
    "data_inicio": ["DATA_ABERTURA", "DATA_INICIO", "DATA_INICIO_RELACIONAMENTO_CONTA", "DATA_ABERTURA_CONTA"],
    "data_fim": ["DATA_ENCERRAMENTO", "DATA_FIM", "DATA_FIM_RELACIONAMENTO_CONTA", "DATA_ENCERRAMENTO_CONTA"],
}

CODIGOS_NATUREZA = {
    "C": ["C", "CR", "CRED", "CREDITO", "CREDITOS", "ENTRADA", "RECEBIDO", "RECEBIMENTO", "IN", "CREDIT"],
    "D": ["D", "DB", "DEB", "DEBITO", "DEBITOS", "SAIDA", "ENVIADO", "PAGAMENTO", "OUT", "DEBIT"],
}

SITUACOES_CONCLUIDAS = ["APPROVED", "APROVADO", "APROVADA", "CONCLUIDO", "CONCLUIDA", "COMPLETED", "SUCCESS",
                        "SUCESSO", "REALIZADO", "REALIZADA", "PAID", "PAGO", "EFETIVADO", "EFETIVADA", "SETTLED",
                        "LIQUIDADO", "LIQUIDADA"]

PASTA_PERFIS = os.path.join(os.path.dirname(__file__), "perfis_bancos")


def ler_tabela(caminho, tipo, aba=None):
    """(abas, gerador de (linha, campos), local)."""
    if tipo == "xlsx":
        lx = leitores.LeitorXLSX(caminho)
        abas = lx.abas()
        aba = aba or abas[0]
        return abas, lx.linhas(aba), aba
    return [], leitores.linhas_delimitado(caminho), None


def detectar_cabecalho(linhas):
    contagens = [(n, sum(1 for c in cs if str(c).strip())) for n, cs in linhas]
    if not contagens:
        return None
    maximo = max(c for _, c in contagens)
    for n, c in contagens:
        if c >= max(2, int(maximo * 0.6)):
            return n
    return contagens[0][0]


def assinatura(cabecalho):
    return "|".join(util.normalizar_cabecalho(c) for c in cabecalho)


def sugerir_mapeamento(cabecalho, tipo_dados):
    campos = [c for c, _ in CAMPOS[tipo_dados]]
    norm = [util.normalizar_cabecalho(c) for c in cabecalho]
    mapa = {}
    usados = set()
    for campo in campos:
        for sin in SINONIMOS.get(campo, []):
            for i, h in enumerate(norm):
                if i not in usados and h == sin:
                    mapa[campo] = cabecalho[i]
                    usados.add(i)
                    break
            if campo in mapa:
                break
    return mapa


def adivinhar_tipo(cabecalho):
    norm = set(util.normalizar_cabecalho(c) for c in cabecalho)
    if norm & {"IDCOMUNICACAO", "ID_COMUNICACAO", "INDEXADOR"}:
        return "rif"
    tem_valor = bool(norm & set(SINONIMOS["valor"] + SINONIMOS["credito"] + SINONIMOS["debito"]))
    tem_geo = bool(norm & set(SINONIMOS["ip"] + SINONIMOS["latitude"] + SINONIMOS["coordenadas"]))
    if tem_geo and not tem_valor:
        return "acessos"
    if not tem_valor and norm & {"NOME", "CPF", "CPF_CNPJ", "NOME_TITULAR", "TIPO_TITULAR"}:
        return "cadastro"
    return "extrato"


def perfis_embutidos():
    out = []
    for arq in sorted(glob.glob(os.path.join(PASTA_PERFIS, "*.json"))):
        with open(arq, encoding="utf-8") as f:
            p = json.load(f)
        p["origem"] = "embutido:" + os.path.basename(arq)
        out.append(p)
    return out


def localizar_perfil(b, cabecalho):
    ass = assinatura(cabecalho)
    p = b.q1("SELECT * FROM perfis_mapeamento WHERE assinatura=? ORDER BY usos DESC, id DESC LIMIT 1", (ass,))
    if p:
        return {"id": p["id"], "nome": p["nome"], "instituicao": p["instituicao"], "adaptador": p["adaptador"],
                "mapeamento": json.loads(p["mapeamento_json"]), "opcoes": json.loads(p["opcoes_json"] or "{}"),
                "origem": "aprendido (usado %d vezes)" % p["usos"]}
    norm = set(util.normalizar_cabecalho(c) for c in cabecalho)
    for p in perfis_embutidos():
        exigidas = set(util.normalizar_cabecalho(c) for c in p.get("colunas_obrigatorias", []))
        qualquer = set(util.normalizar_cabecalho(c) for c in p.get("colunas_qualquer", []))
        if (exigidas or qualquer) and exigidas <= norm and (not qualquer or qualquer & norm):
            return p
    return None


def salvar_perfil(b, nome, instituicao, cabecalho, adaptador, mapeamento, opcoes, usuario):
    ass = assinatura(cabecalho)
    ex = b.q1("SELECT id FROM perfis_mapeamento WHERE assinatura=? AND adaptador=?", (ass, adaptador))
    if ex:
        b.x("UPDATE perfis_mapeamento SET nome=?, instituicao=?, mapeamento_json=?, opcoes_json=?, usos=usos+1 WHERE id=?",
            (nome, instituicao, util.json_dump(mapeamento), util.json_dump(opcoes), ex["id"]))
        return ex["id"]
    return b.x("INSERT INTO perfis_mapeamento(nome, instituicao, assinatura, adaptador, mapeamento_json, opcoes_json, usos, "
               "criado_em, criado_por) VALUES (?,?,?,?,?,?,1,?,?)",
               (nome, instituicao, ass, adaptador, util.json_dump(mapeamento), util.json_dump(opcoes), util.agora_iso(), usuario))


def previa(b, caminho, tipo, aba=None, linha_cabecalho=None, n=25):
    abas, gen, local = ler_tabela(caminho, tipo, aba)
    inicio = []
    for item in gen:
        inicio.append(item)
        if len(inicio) >= 60 + (linha_cabecalho or 0):
            break
    if linha_cabecalho is None:
        linha_cabecalho = detectar_cabecalho(inicio[:30])
    cab, amostra = [], []
    for num, campos in inicio:
        if num == linha_cabecalho:
            cab = [str(c).strip() for c in campos]
        elif linha_cabecalho is not None and num > linha_cabecalho and len(amostra) < n:
            amostra.append({"linha": num, "campos": campos})
    cab = [c if c else "COLUNA_%d" % (i + 1) for i, c in enumerate(cab)]
    perfil = localizar_perfil(b, cab) if cab else None
    tipo_dados = (perfil or {}).get("adaptador") or adivinhar_tipo(cab)
    sugestoes = {t: sugerir_mapeamento(cab, t) for t in CAMPOS}
    if perfil:
        sugestoes[perfil["adaptador"]] = dict(sugestoes.get(perfil["adaptador"], {}),
                                              **{k: v for k, v in perfil["mapeamento"].items() if v in cab})
    return {"abas": abas, "aba": local, "linha_cabecalho": linha_cabecalho, "cabecalho": cab, "amostra": amostra,
            "tipo_sugerido": tipo_dados, "sugestoes": sugestoes, "perfil": perfil,
            "campos": {t: [{"campo": c, "rotulo": r} for c, r in v] for t, v in CAMPOS.items()}}


# ---------------------------------------------------------------- conversão das linhas

def _natureza(texto, codigos):
    t = util.normalizar_cabecalho(texto)
    for nat in ("C", "D"):
        if t in [util.normalizar_cabecalho(x) for x in codigos.get(nat, [])]:
            return nat
    return None


def _linhas_dados(caminho, tipo, aba, linha_cabecalho):
    abas, gen, local = ler_tabela(caminho, tipo, aba)
    cab = None
    for num, campos in gen:
        if cab is None:
            if linha_cabecalho is None or num == linha_cabecalho:
                cab = [str(c).strip() or "COLUNA_%d" % (i + 1) for i, c in enumerate(campos)]
            continue
        if not any(str(c).strip() for c in campos):
            continue
        reg = {}
        for i, h in enumerate(cab):
            reg[h] = campos[i] if i < len(campos) else ""
        if len(campos) > len(cab):
            for j in range(len(cab), len(campos)):
                if str(campos[j]).strip():
                    reg["COLUNA_EXTRA_%d" % (j + 1)] = campos[j]
        yield local, num, reg, cab


def importar_extrato(imp, caminho, tipo, mapeamento, opcoes):
    """mapeamento: campo -> nome da coluna. opcoes: aba, linha_cabecalho, natureza_fixa, sinal_credito,
    codigos_natureza, filtrar_situacao, situacoes_concluidas, instituicao."""
    m = {k: v for k, v in (mapeamento or {}).items() if v}
    tem_valor = "valor" in m
    tem_cd = "credito" in m or "debito" in m
    if not (tem_valor or tem_cd):
        raise ValueError("Mapeie 'Valor da transação' ou as colunas de Crédito/Débito.")
    if tem_valor and tem_cd:
        raise ValueError("Use Valor da transação OU colunas de Crédito/Débito, não ambos.")
    if "data" not in m:
        raise ValueError("Mapeie a coluna de data.")
    codigos = opcoes.get("codigos_natureza") or CODIGOS_NATUREZA
    nat_fixa = opcoes.get("natureza_fixa") or None
    sinal_credito = bool(opcoes.get("sinal_credito"))
    filtrar_sit = "situacao" in m
    concluidas = set(util.normalizar_cabecalho(s) for s in (opcoes.get("situacoes_concluidas") or SITUACOES_CONCLUIDAS))
    if nat_fixa:
        imp.aviso("Natureza fixa %s aplicada a todas as linhas, conforme confirmação do usuário." % nat_fixa)
    if sinal_credito:
        imp.aviso("Sinal do valor usado como natureza (positivo = crédito), conforme confirmação do usuário.")
    agrupar = "chave_lancamento" in m
    grupos = {}
    ordem = []

    def g(reg, campo):
        col = m.get(campo)
        return str(reg.get(col, "")).strip() if col else ""

    for local, num, reg, cab in _linhas_dados(caminho, tipo, opcoes.get("aba"), opcoes.get("linha_cabecalho")):
        d = {"local": local, "linha": num, "bruto": reg, "situacao": "aceito", "motivo": ""}
        dt = util.parse_data(g(reg, "data"))
        d["data_original"] = g(reg, "data")
        d["data"], d["hora"], d["fuso"] = dt["data"], dt["hora"], dt["fuso"]
        if g(reg, "hora"):
            d["hora"] = util.parse_hora(g(reg, "hora")) or d["hora"]
        if g(reg, "fuso"):
            d["fuso"] = g(reg, "fuso")
        motivos = []
        if not d["data"]:
            motivos.append(dt["motivo"] or "data não reconhecida")
        sinal = 0
        if tem_valor:
            d["valor_original"] = g(reg, "valor")
            pv = util.parse_valor(d["valor_original"])
            d["valor_centavos"], sinal = pv["centavos"], pv["sinal"]
            if pv["centavos"] is None:
                motivos.append(pv["motivo"] or "valor não reconhecido")
        else:
            vc, vd = g(reg, "credito"), g(reg, "debito")
            pc, pd = util.parse_valor(vc), util.parse_valor(vd)
            c_ok = pc["centavos"] not in (None, 0)
            d_ok = pd["centavos"] not in (None, 0)
            if c_ok and d_ok:
                motivos.append("valores nas colunas de crédito e de débito na mesma linha")
                d["valor_centavos"], d["valor_original"] = None, "C=%s D=%s" % (vc, vd)
            elif c_ok:
                d["valor_centavos"], d["valor_original"], d["natureza"] = pc["centavos"], vc, "C"
                d["natureza_original"] = "coluna crédito"
            elif d_ok:
                d["valor_centavos"], d["valor_original"], d["natureza"] = pd["centavos"], vd, "D"
                d["natureza_original"] = "coluna débito"
            else:
                motivos.append("sem valor em crédito nem débito")
                d["valor_centavos"], d["valor_original"] = None, (vc or vd)
        if tem_valor:
            nat_txt = g(reg, "natureza")
            d["natureza_original"] = nat_txt or None
            if nat_fixa:
                d["natureza"] = nat_fixa
            elif nat_txt:
                d["natureza"] = _natureza(nat_txt, codigos)
                if d["natureza"] is None:
                    motivos.append("natureza não reconhecida: %r" % nat_txt)
            elif sinal_credito and sinal != 0:
                d["natureza"] = "C" if sinal > 0 else "D"
            elif sinal_credito and sinal == 0:
                d["natureza"] = "C"
            else:
                motivos.append("sem natureza (sinal do valor não é usado sem confirmação)")
        for campo in ("descricao", "tipo_operacao", "documento", "titular_nome", "titular_doc", "agencia", "conta",
                      "pix_chave", "pix_id", "ip", "cidade", "uf"):
            d[campo] = g(reg, campo) or None
        d["banco"] = g(reg, "banco") or opcoes.get("instituicao") or None
        if filtrar_sit:
            st = g(reg, "situacao")
            d["status_origem"] = st
            if util.normalizar_cabecalho(st) not in concluidas:
                motivos.append("situação %r não reconhecida como concluída" % (st or "(vazia)"))
        est = g(reg, "estorno")
        if est:
            pe = util.parse_valor(est)
            if pe["centavos"] not in (None, 0):
                motivos.append("valor de estorno informado (%s) exige revisão" % est)
        if not d["data"] and d.get("valor_centavos") is None:
            d["situacao"] = "rejeitado"
        elif motivos:
            d["situacao"] = "pendente"
        d["motivo"] = "; ".join(motivos)
        parte = None
        if any(g(reg, c) for c in ("cp_nome", "cp_doc", "cp_banco", "cp_conta")):
            parte = {"nome": g(reg, "cp_nome") or None, "doc": g(reg, "cp_doc") or None,
                     "banco": g(reg, "cp_banco") or None, "agencia": g(reg, "cp_agencia") or None,
                     "conta": g(reg, "cp_conta") or None, "local": local, "linha": num, "bruto": reg}
            if g(reg, "cp_valor"):
                pv = util.parse_valor(g(reg, "cp_valor"))
                parte["valor_centavos"], parte["valor_original"] = pv["centavos"], g(reg, "cp_valor")
        if agrupar and g(reg, "chave_lancamento"):
            ch = g(reg, "chave_lancamento")
            if ch not in grupos:
                d["chave_local"] = ch
                grupos[ch] = (d, [], [num])
                ordem.append(ch)
            else:
                base = grupos[ch][0]
                grupos[ch][2].append(num)
                if (base.get("valor_centavos"), base.get("natureza"), base.get("data")) != (
                        d.get("valor_centavos"), d.get("natureza"), d.get("data")):
                    base["situacao"] = "pendente"
                    base["motivo"] = (base["motivo"] + "; " if base["motivo"] else "") + \
                        "linhas do mesmo código de lançamento com valor/natureza/data diferentes (linha %d)" % num
            if parte:
                grupos[ch][1].append(parte)
        else:
            imp.lancamento(d, [parte] if parte else [])
    for ch in ordem:
        d, partes, linhas = grupos[ch]
        if len(linhas) > 1:
            d["bruto"] = {"linhas_do_grupo": linhas, "primeira_linha": d["bruto"]}
            if partes and all(p.get("valor_centavos") is None for p in partes) and len(partes) > 1:
                imp.aviso("Código de lançamento com várias linhas sem valor de parcela mapeado: o valor do lançamento "
                          "foi contado uma vez e não foi distribuído entre as contrapartes.")
        imp.lancamento(d, partes)


def importar_acessos(imp, caminho, tipo, mapeamento, opcoes):
    m = {k: v for k, v in (mapeamento or {}).items() if v}
    if not any(k in m for k in ("ip", "latitude", "coordenadas", "cidade", "dispositivo", "endereco")):
        raise ValueError("Mapeie ao menos IP, coordenadas, cidade, endereço ou dispositivo.")
    imp.aviso("Registros de acesso, IP e geolocalização são guardados separadamente e não entram em totais financeiros.")

    def g(reg, campo):
        col = m.get(campo)
        return str(reg.get(col, "")).strip() if col else ""

    for local, num, reg, cab in _linhas_dados(caminho, tipo, opcoes.get("aba"), opcoes.get("linha_cabecalho")):
        d = {"local": local, "linha": num, "bruto": reg}
        dt = util.parse_data(g(reg, "data"))
        d["data_original"] = g(reg, "data")
        d["data"], d["hora"], d["fuso"] = dt["data"], dt["hora"], dt["fuso"]
        if g(reg, "hora"):
            d["hora"] = util.parse_hora(g(reg, "hora")) or d["hora"]
        if g(reg, "fuso"):
            d["fuso"] = g(reg, "fuso")
        for c in ("ip", "porta", "precisao", "cidade", "uf", "pais", "endereco", "dispositivo", "sistema", "evento",
                  "nome", "doc", "telefone", "email", "banco", "conta"):
            d[c] = g(reg, c) or None
        lat, lon = g(reg, "latitude"), g(reg, "longitude")
        if not lat and g(reg, "coordenadas"):
            partes = [p.strip() for p in g(reg, "coordenadas").replace(";", ",").split(",")]
            if len(partes) == 2:
                lat, lon = partes
        d["latitude"], d["longitude"] = lat or None, lon or None
        imp.acesso(d)


def importar_cadastro(imp, caminho, tipo, mapeamento, opcoes):
    m = {k: v for k, v in (mapeamento or {}).items() if v}
    if "nome" not in m and "doc" not in m:
        raise ValueError("Mapeie ao menos nome ou CPF/CNPJ.")
    imp.aviso("Dados cadastrais são guardados como cadastro e não entram em totais financeiros.")

    def g(reg, campo):
        col = m.get(campo)
        return str(reg.get(col, "")).strip() if col else ""

    for local, num, reg, cab in _linhas_dados(caminho, tipo, opcoes.get("aba"), opcoes.get("linha_cabecalho")):
        d = {"local": local, "linha": num, "bruto": reg}
        for c, _ in CAMPOS["cadastro"]:
            d[c] = g(reg, c) or None
        for c in ("data_inicio", "data_fim"):
            if d[c]:
                d[c] = util.parse_data(d[c])["data"] or d[c]
        imp.titular(d)
