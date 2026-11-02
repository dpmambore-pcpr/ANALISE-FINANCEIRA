"""Arquivos brutos do SIMBA (afastamento de sigilo bancário).

Leiaute 2010: Carta-Circular BCB 3.454/2010, itens 5 a 8 (conferido com o texto publicado em
normativos.bcb.gov.br). TXT sem cabeçalho, separador TAB, datas ddmmaaaa, valores em centavos.

Leiaute 2026: IN BCB 636/2025, Anexo I (vigência prevista para 01/12/2026). As posições abaixo
foram transcritas da norma, mas AINDA NÃO FORAM VALIDADAS com amostras reais anonimizadas; a
importação exige confirmação expressa do usuário e marca o leiaute como experimental.

CODIGO_CHAVE_EXTRATO é único apenas dentro do arquivo EXTRATO da remessa; por isso cada ZIP
deve conter uma única remessa e as chaves nunca são comparadas entre fontes diferentes.
"""

import io
import os
import zipfile

from . import util

EXTRATO_2010 = ["CODIGO_CHAVE_EXTRATO", "NUMERO_BANCO", "NUMERO_AGENCIA", "NUMERO_CONTA", "TIPO_CONTA",
                "DATA_LANCAMENTO", "NUMERO_DOCUMENTO", "DESCRICAO_LANCAMENTO", "TIPO_LANCAMENTO",
                "VALOR_LANCAMENTO", "NATUREZA_LANCAMENTO", "VALOR_SALDO", "NATUREZA_SALDO", "LOCAL_TRANSACAO"]
OD_2010 = ["CODIGO_CHAVE_OD", "CODIGO_CHAVE_EXTRATO", "VALOR_TRANSACAO", "NUMERO_DOCUMENTO_TRANSACAO",
           "NUMERO_BANCO_OD", "NUMERO_AGENCIA_OD", "NUMERO_CONTA_OD", "TIPO_CONTA_OD", "TIPO_PESSOA_OD",
           "CPF_CNPJ_OD", "NOME_PESSOA_OD", "NOME_DOC_IDENTIFICACAO_OD", "NUMERO_DOC_IDENTIFICACAO_OD",
           "CODIGO_DE_BARRAS", "NOME_ENDOSSANTE_CHEQUE", "DOC_ENDOSSANTE_CHEQUE", "SITUACAO_IDENTIFICACAO",
           "OBSERVACAO"]
TITULARES_2010 = ["NUMERO_BANCO", "NUMERO_AGENCIA", "NUMERO_CONTA", "TIPO_CONTA", "TIPO_TITULAR",
                  "PESSOA_INVESTIGADA", "TIPO_PESSOA_TITULAR", "CPF_CNPJ_TITULAR", "NOME_TITULAR",
                  "NOME_DOC_IDENTIFICACAO", "NUMERO_DOC_IDENTIFICACAO", "ENDERECO_LOGRADOURO", "ENDERECO_CIDADE",
                  "ENDERECO_UF", "ENDERECO_PAIS", "ENDERECO_CEP", "TELEFONE_PESSOA", "VALOR_RENDA",
                  "DATA_ATUALIZACAO_RENDA", "DATA_INICIO_RELACIONAMENTO_CONTA", "DATA_FIM_RELACIONAMENTO_CONTA"]

EXTRATO_2026 = ["CODIGO_CHAVE_EXTRATO", "COD_COMP_INSTITUICAO", "NUMERO_AGENCIA", "NUMERO_CONTA", "TIPO_CONTA",
                "DATA_LANCAMENTO", "NUMERO_DOCUMENTO", "DESCRICAO_LANCAMENTO", "CODIGO_TIPO_LANCAMENTO",
                "VALOR_LANCAMENTO", "NATUREZA_LANCAMENTO", "VALOR_SALDO", "NATUREZA_SALDO",
                "INFO_ADICIONAIS_LOCAL_TRANSACAO", "CNPJ_INSTITUICAO", "NOME_INSTITUICAO", "INTERFACE_TRANSACAO",
                "CODIGO_CIDADE_TRANSACAO", "CODIGO_UF_TRANSACAO", "IP_TRANSACAO", "PORTA_IP_HOME_BANKING",
                "MAC_ADDRESS_TRANSACAO", "HORARIO_LANCAMENTO", "TIPO_CHAVE_PIX_TRANSACAO", "CHAVE_PIX_TRANSACAO",
                "ID_TRANSACAO_PIX", "IDENTIFICADOR_SESSAO"]
OD_2026 = ["CODIGO_CHAVE_OD", "CODIGO_CHAVE_EXTRATO", "VALOR_TRANSACAO", "NUMERO_DOCUMENTO_TRANSACAO",
           "COD_COMP_INSTITUICAO_OD", "NUMERO_AGENCIA_OD", "NUMERO_CONTA_OD", "TIPO_CONTA_OD", "TIPO_PESSOA_OD",
           "CPF_CNPJ_OD", "NOME_PESSOA_OD", "NOME_DOC_IDENTIFICACAO_OD", "NUMERO_DOC_IDENTIFICACAO_OD",
           "CODIGO_DE_BARRAS", "NOME_ENDOSSANTE_CHEQUE", "DOC_ENDOSSANTE_CHEQUE", "SITUACAO_IDENTIFICACAO",
           "OBSERVACAO", "CNPJ_INSTITUICAO_OD", "BENEFICIARIO_BOLETO", "PAGADOR_BOLETO",
           "CNPJ_INSTITUICAO_EMISSORA_BOLETO", "NOME_INSTITUICAO_EMISSORA_BOLETO", "VALOR_NOMINAL_BOLETO",
           "TIPO_CHAVE_PIX_PESSOA_OD", "CHAVE_PIX_PESSOA_OD", "COMENTARIO_PIX", "ID_TRANSACAO_PIX"]
TITULARES_2026 = ["COD_COMP_INSTITUICAO", "NUMERO_AGENCIA", "NUMERO_CONTA", "TIPO_CONTA", "TIPO_TITULAR",
                  "PESSOA_INVESTIGADA", "TIPO_PESSOA_TITULAR", "CPF_CNPJ_TITULAR", "NOME_TITULAR",
                  "NOME_DOC_IDENTIFICACAO", "NUMERO_DOC_IDENTIFICACAO", "ENDERECO_LOGRADOURO", "CODIGO_CIDADE",
                  "CODIGO_UF", "ENDERECO_PAIS", "ENDERECO_CEP", "TELEFONE_PESSOA", "VALOR_RENDA",
                  "DATA_ATUALIZACAO_RENDA", "DATA_INICIO_RELACIONAMENTO_CONTA", "DATA_FIM_RELACIONAMENTO_CONTA",
                  "CNPJ_INSTITUICAO", "NOME_INSTITUICAO", "NOME_SOCIAL", "E_MAIL", "DISPOSITIVO_MOVEL_CADASTRADO",
                  "COMPUTADOR_CADASTRADO", "CONTRATO_CAMBIO"]

LEIAUTES = {
    "2010": {"EXTRATO": EXTRATO_2010, "ORIGEM_DESTINO": OD_2010, "TITULARES": TITULARES_2010,
             "nome": "SIMBA - Carta-Circular BCB 3.454/2010"},
    "2026": {"EXTRATO": EXTRATO_2026, "ORIGEM_DESTINO": OD_2026, "TITULARES": TITULARES_2026,
             "nome": "SIMBA - IN BCB 636/2025 (EXPERIMENTAL, validar com amostra anonimizada)"},
}

TIPO_CHAVE_PIX = {"1": "CPF/CNPJ", "2": "telefone", "3": "e-mail", "4": "aleatória"}
INTERFACE = {"1": "agência física", "2": "correspondente bancário", "3": "terminal de autoatendimento (ATM)",
             "4": "internet banking", "5": "mobile banking", "6": "ETV", "7": "casa lotérica",
             "8": "estabelecimento comercial", "9": "outros"}
VINCULO = {"T": "titular", "R": "representante", "L": "representante legal", "P": "procurador", "O": "outros"}


class ErroSimba(ValueError):
    pass


def _nome_base(caminho):
    n = os.path.basename(caminho).upper()
    n = os.path.splitext(n)[0].replace("-", "_").replace(" ", "_")
    return n


def localizar_arquivos(nomes):
    """Retorna {'EXTRATO': nome, 'ORIGEM_DESTINO': nome, 'TITULARES': nome?} ou erro."""
    achados = {}
    for nome in nomes:
        base = _nome_base(nome)
        for chave in ("EXTRATO", "ORIGEM_DESTINO", "TITULARES", "CONTAS", "AGENCIAS"):
            if base == chave or base.endswith("_" + chave) or base.startswith(chave + "_"):
                if chave == "EXTRATO" and "ORIGEM" in base:
                    continue
                achados.setdefault(chave, []).append(nome)
    for chave in ("EXTRATO", "ORIGEM_DESTINO", "TITULARES"):
        if len(achados.get(chave, [])) > 1:
            raise ErroSimba("O pacote tem mais de um arquivo %s (%s). Use um ZIP por banco/remessa para não misturar "
                            "chaves de remessas diferentes." % (chave, ", ".join(achados[chave])))
    if "EXTRATO" not in achados or "ORIGEM_DESTINO" not in achados:
        raise ErroSimba("O pacote precisa ter EXTRATO.txt e ORIGEM_DESTINO.txt da mesma remessa.")
    return {k: v[0] for k, v in achados.items()}


def _linhas(z, nome):
    with z.open(nome) as f:
        amostra = f.read(1024 * 1024)
    cod = "utf-8"
    try:
        amostra.decode("utf-8")
    except UnicodeDecodeError:
        cod = "cp1252"
    with z.open(nome) as bruto:
        texto = io.TextIOWrapper(bruto, encoding=cod, errors="replace", newline=None)
        for i, ln in enumerate(texto, start=1):
            ln = ln.rstrip("\n")
            if not ln.strip():
                continue
            yield i, ln.split("\t")


def detectar_leiaute(z, arquivos):
    for _, campos in _linhas(z, arquivos["EXTRATO"]):
        n = len(campos)
        if n == len(EXTRATO_2010):
            return "2010"
        if n == len(EXTRATO_2026):
            return "2026"
        raise ErroSimba("EXTRATO com %d campos: não corresponde ao leiaute 2010 (14) nem ao da IN 636/2025 (27). "
                        "Não foi feita inferência de posições." % n)
    raise ErroSimba("EXTRATO vazio")


def _registro(campos, nomes, arquivo, linha, erros):
    if len(campos) != len(nomes):
        erros.append("%s linha %d: %d campos (esperado %d)" % (arquivo, linha, len(campos), len(nomes)))
        return None
    return dict(zip(nomes, [c.strip() for c in campos]))


def inspecionar(caminho_zip):
    with zipfile.ZipFile(caminho_zip) as z:
        arquivos = localizar_arquivos([i.filename for i in z.infolist() if not i.is_dir()])
        leiaute = detectar_leiaute(z, arquivos)
    return {"arquivos": arquivos, "leiaute": leiaute, "descricao": LEIAUTES[leiaute]["nome"]}


def importar(imp, caminho_zip, opcoes):
    with zipfile.ZipFile(caminho_zip) as z:
        arquivos = localizar_arquivos([i.filename for i in z.infolist() if not i.is_dir()])
        leiaute = detectar_leiaute(z, arquivos)
        lay = LEIAUTES[leiaute]
        if leiaute == "2026":
            if not opcoes.get("confirmo_leiaute_in636"):
                raise ErroSimba("Leiaute da IN BCB 636/2025 detectado. Esta leitura é experimental: confira as posições "
                                "com a norma e com amostra anonimizada e marque a confirmação para prosseguir.")
            imp.aviso("Leiaute IN BCB 636/2025 importado em modo EXPERIMENTAL. Confira valores, datas, horários (UTC) e "
                      "campos PIX com o SIMBA/validador oficial antes de usar em relatório.")
        erros = []

        contas = {}
        if "TITULARES" in arquivos:
            for ln, campos in _linhas(z, arquivos["TITULARES"]):
                r = _registro(campos, lay["TITULARES"], arquivos["TITULARES"], ln, erros)
                if r is None:
                    continue
                banco = r.get("NUMERO_BANCO") or r.get("COD_COMP_INSTITUICAO")
                cidade = r.get("ENDERECO_CIDADE") or r.get("CODIGO_CIDADE")
                uf = r.get("ENDERECO_UF") or r.get("CODIGO_UF")
                t = {"local": arquivos["TITULARES"], "linha": ln, "banco": banco, "agencia": r["NUMERO_AGENCIA"],
                     "conta": r["NUMERO_CONTA"], "tipo_conta": r["TIPO_CONTA"], "tipo_vinculo": r["TIPO_TITULAR"],
                     "pessoa_investigada": r["PESSOA_INVESTIGADA"], "tipo_pessoa": r["TIPO_PESSOA_TITULAR"],
                     "doc": r["CPF_CNPJ_TITULAR"], "nome": r["NOME_TITULAR"], "endereco": r["ENDERECO_LOGRADOURO"],
                     "cidade": cidade, "uf": uf, "cep": r["ENDERECO_CEP"], "telefone": r["TELEFONE_PESSOA"],
                     "email": r.get("E_MAIL"),
                     "dispositivo": "; ".join(x for x in (r.get("DISPOSITIVO_MOVEL_CADASTRADO"), r.get("COMPUTADOR_CADASTRADO")) if x) or None,
                     "data_inicio": util.parse_data(r["DATA_INICIO_RELACIONAMENTO_CONTA"], "ddmmaaaa")["data"],
                     "data_fim": util.parse_data(r["DATA_FIM_RELACIONAMENTO_CONTA"], "ddmmaaaa")["data"],
                     "bruto": r}
                imp.titular(t)
                chave = (util.so_digitos(banco).lstrip("0"), util.so_digitos(r["NUMERO_AGENCIA"]).lstrip("0"),
                         r["NUMERO_CONTA"].strip().lstrip("0"))
                contas.setdefault(chave, []).append(t)
        else:
            imp.aviso("Pacote sem TITULARES.txt: titular das contas não identificado.")

        ods = {}
        chaves_od = set()
        for ln, campos in _linhas(z, arquivos["ORIGEM_DESTINO"]):
            r = _registro(campos, lay["ORIGEM_DESTINO"], arquivos["ORIGEM_DESTINO"], ln, erros)
            if r is None:
                continue
            if r["CODIGO_CHAVE_OD"] in chaves_od:
                erros.append("%s linha %d: CODIGO_CHAVE_OD repetido %s" % (arquivos["ORIGEM_DESTINO"], ln, r["CODIGO_CHAVE_OD"]))
            chaves_od.add(r["CODIGO_CHAVE_OD"])
            ods.setdefault(r["CODIGO_CHAVE_EXTRATO"], []).append((ln, r))

        extratos = []
        chaves_ext = set()
        for ln, campos in _linhas(z, arquivos["EXTRATO"]):
            r = _registro(campos, lay["EXTRATO"], arquivos["EXTRATO"], ln, erros)
            if r is None:
                continue
            if r["CODIGO_CHAVE_EXTRATO"] in chaves_ext:
                erros.append("%s linha %d: CODIGO_CHAVE_EXTRATO repetido %s" % (arquivos["EXTRATO"], ln, r["CODIGO_CHAVE_EXTRATO"]))
            chaves_ext.add(r["CODIGO_CHAVE_EXTRATO"])
            extratos.append((ln, r))

        orfas_od = sorted(set(ods) - chaves_ext)
        sem_od = sorted(chaves_ext - set(ods))
        if orfas_od:
            erros.append("ORIGEM_DESTINO com CODIGO_CHAVE_EXTRATO sem lançamento correspondente: %s" % ", ".join(orfas_od[:20]))
        if sem_od and not opcoes.get("permitir_extrato_sem_od"):
            erros.append("Lançamentos sem ORIGEM_DESTINO correspondente (a norma prevê ao menos um): %s. Marque a opção "
                         "própria para importar mesmo assim." % ", ".join(sem_od[:20]))
        if erros:
            raise ErroSimba("Importação bloqueada para não gerar totais incorretos:\n- " + "\n- ".join(erros[:50]))
        if sem_od:
            imp.aviso("%d lançamento(s) sem ORIGEM_DESTINO importado(s) por opção do usuário." % len(sem_od))

        for ln, r in extratos:
            banco = r.get("NUMERO_BANCO") or r.get("COD_COMP_INSTITUICAO")
            dt = util.parse_data(r["DATA_LANCAMENTO"], "ddmmaaaa")
            valor = util.parse_centavos_sem_separador(r["VALOR_LANCAMENTO"])
            nat = r["NATUREZA_LANCAMENTO"].upper()
            motivos = []
            if not dt["data"]:
                motivos.append(dt["motivo"])
            if valor is None:
                motivos.append("VALOR_LANCAMENTO inválido: %r" % r["VALOR_LANCAMENTO"])
            if nat == "*":
                motivos.append("natureza '*' (outros: bloqueios, provisões, lançamentos futuros) fora dos totais")
            elif nat not in ("C", "D"):
                motivos.append("natureza inválida: %r" % nat)
            chave_conta = (util.so_digitos(banco).lstrip("0"), util.so_digitos(r["NUMERO_AGENCIA"]).lstrip("0"),
                           r["NUMERO_CONTA"].strip().lstrip("0"))
            tits = contas.get(chave_conta, [])
            principais = [t for t in tits if (t["tipo_vinculo"] or "").upper() == "T" or (t["tipo_vinculo"] or "").isdigit()]
            outros = [t for t in tits if t not in principais]
            d = {"local": arquivos["EXTRATO"], "linha": ln, "chave_local": r["CODIGO_CHAVE_EXTRATO"],
                 "data": dt["data"], "data_original": r["DATA_LANCAMENTO"], "valor_centavos": valor,
                 "valor_original": r["VALOR_LANCAMENTO"], "natureza": nat if nat in ("C", "D") else None,
                 "natureza_original": r["NATUREZA_LANCAMENTO"], "banco": r.get("NOME_INSTITUICAO") or banco,
                 "agencia": r["NUMERO_AGENCIA"], "conta": r["NUMERO_CONTA"], "documento": r["NUMERO_DOCUMENTO"],
                 "descricao": r["DESCRICAO_LANCAMENTO"],
                 "tipo_operacao": r.get("TIPO_LANCAMENTO") or r.get("CODIGO_TIPO_LANCAMENTO"),
                 "situacao": "pendente" if motivos else "aceito", "motivo": "; ".join(motivos), "bruto": r,
                 "conta_qtd_titulares": len(principais) or None}
            if len(principais) == 1:
                d["titular_nome"], d["titular_doc"] = principais[0]["nome"], principais[0]["doc"]
            elif len(principais) > 1:
                d["titular_nome"] = "CONTA CONJUNTA: " + "; ".join(t["nome"] or "?" for t in principais)
                d["titular_obs"] = "Conta com %d titulares/cotitulares: %s" % (
                    len(principais), "; ".join("%s (%s, vínculo %s)" % (t["nome"], t["doc"], t["tipo_vinculo"]) for t in principais))
            if outros:
                d["titular_obs"] = ((d.get("titular_obs") or "") + " Representantes/procuradores (não são titulares): " +
                                    "; ".join("%s (%s, %s)" % (t["nome"], t["doc"], VINCULO.get(t["tipo_vinculo"], t["tipo_vinculo"]))
                                              for t in outros)).strip()
            if leiaute == "2026":
                hora = r["HORARIO_LANCAMENTO"]
                if hora:
                    d["hora"] = util.parse_hora(hora)
                    d["fuso"] = "UTC (IN BCB 636/2025, art. 3º, VI)"
                    if not d["hora"]:
                        d["situacao"] = "pendente"
                        d["motivo"] = (d["motivo"] + "; " if d["motivo"] else "") + "HORARIO_LANCAMENTO inválido: %r" % hora
                d["ip"] = r["IP_TRANSACAO"] or None
                d["porta"] = r["PORTA_IP_HOME_BANKING"] or None
                d["mac"] = r["MAC_ADDRESS_TRANSACAO"] or None
                d["cidade"] = r["CODIGO_CIDADE_TRANSACAO"] or None
                d["uf"] = r["CODIGO_UF_TRANSACAO"] or None
                d["interface"] = INTERFACE.get(r["INTERFACE_TRANSACAO"], r["INTERFACE_TRANSACAO"]) or None
                d["pix_chave"] = r["CHAVE_PIX_TRANSACAO"] or None
                d["pix_tipo"] = TIPO_CHAVE_PIX.get(r["TIPO_CHAVE_PIX_TRANSACAO"], r["TIPO_CHAVE_PIX_TRANSACAO"]) or None
                d["pix_id"] = r["ID_TRANSACAO_PIX"] or None
            partes = []
            for oln, o in ods.get(r["CODIGO_CHAVE_EXTRATO"], []):
                pv = util.parse_centavos_sem_separador(o["VALOR_TRANSACAO"])
                p = {"chave_od": o["CODIGO_CHAVE_OD"], "valor_centavos": pv, "valor_original": o["VALOR_TRANSACAO"],
                     "banco": o.get("NUMERO_BANCO_OD") or o.get("COD_COMP_INSTITUICAO_OD") or None,
                     "agencia": o["NUMERO_AGENCIA_OD"] or None, "conta": o["NUMERO_CONTA_OD"] or None,
                     "tipo_conta": o["TIPO_CONTA_OD"] or None, "tipo_pessoa": o["TIPO_PESSOA_OD"],
                     "doc": o["CPF_CNPJ_OD"] or None, "nome": o["NOME_PESSOA_OD"] or None,
                     "observacao": o["OBSERVACAO"] or None, "local": arquivos["ORIGEM_DESTINO"], "linha": oln, "bruto": o}
                if leiaute == "2026":
                    p["pix_chave"] = o["CHAVE_PIX_PESSOA_OD"] or None
                    p["pix_tipo"] = TIPO_CHAVE_PIX.get(o["TIPO_CHAVE_PIX_PESSOA_OD"], o["TIPO_CHAVE_PIX_PESSOA_OD"]) or None
                    p["pix_id"] = o["ID_TRANSACAO_PIX"] or None
                    p["comentario"] = o["COMENTARIO_PIX"] or None
                partes.append(p)
            lid = imp.lancamento(d, partes)
            if leiaute == "2026" and (d.get("ip") or d.get("mac")):
                imp.acesso({"local": arquivos["EXTRATO"], "linha": ln, "data": d["data"], "hora": d.get("hora"),
                            "fuso": d.get("fuso"), "data_original": r["DATA_LANCAMENTO"] + " " + r["HORARIO_LANCAMENTO"],
                            "ip": d.get("ip"), "porta": d.get("porta"), "dispositivo": d.get("mac"),
                            "cidade": d.get("cidade"), "uf": d.get("uf"), "evento": "lançamento SIMBA (interface: %s)" % (d.get("interface") or "?"),
                            "nome": d.get("titular_nome"), "doc": d.get("titular_doc"), "banco": d.get("banco"),
                            "conta": d.get("conta"), "bruto": {"lancamento_id": lid, "CODIGO_CHAVE_EXTRATO": r["CODIGO_CHAVE_EXTRATO"]}})
            for _, o in ods.get(r["CODIGO_CHAVE_EXTRATO"], []):
                if o.get("OBSERVACAO"):
                    imp.ident_texto(o["OBSERVACAO"], "lancamentos", lid, arquivos["ORIGEM_DESTINO"], ln, "observacao")
    return leiaute
