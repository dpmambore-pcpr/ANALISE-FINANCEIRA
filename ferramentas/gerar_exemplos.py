"""Gera os arquivos FICTÍCIOS da pasta exemplos/. Nenhum dado real.

CPFs/CNPJs seguem o padrão 000.000.00X-XX (dígitos verificadores válidos, números fictícios),
IPs usam faixas reservadas para documentação (RFC 5737/3849) e e-mails usam o domínio .invalid.
Uso: python ferramentas/gerar_exemplos.py
"""

import io
import os
import sys
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from financeira import escritores, util  # noqa: E402

PASTA = os.path.join(RAIZ, "exemplos")


def cpf(n, fmt=True):
    d = util.gerar_cpf_ficticio(n)
    return util.formatar_documento(d) if fmt else d


def cnpj(n, fmt=True):
    d = util.gerar_cnpj_ficticio(n)
    return util.formatar_documento(d) if fmt else d


FULANO, ALFA, GAMA, BETA, DELTA, EPSILON = cpf(1), cpf(2), cpf(3), cpf(4), cpf(5), cpf(6)


def _zip(nome, arquivos):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, conteudo in arquivos:
            info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, conteudo)
    with open(os.path.join(PASTA, nome), "wb") as f:
        f.write(buf.getvalue())


def _txt(nome, texto, cod="utf-8"):
    with open(os.path.join(PASTA, nome), "w", encoding=cod, newline="") as f:
        f.write(texto)


def extrato_csv():
    cab = "Data;Hora;Descricao;Valor;Natureza;Titular;CPF_CNPJ_Titular;Banco;Agencia;Conta;Contraparte;CPF_CNPJ_Contraparte;Chave_PIX\r\n"
    base = ";FULANO FICTICIO DA SILVA;%s;BANCO FICTICIO;0001;12345-6;" % FULANO
    linhas = [
        "01/03/2026;09:10;PIX RECEBIDO;600,00;C" + base + "PESSOA ALFA;%s;alfa@exemplo.invalid" % ALFA,
        "05/03/2026;14:22;PIX RECEBIDO;400,00;C" + base + "PESSOA GAMA;%s;" % GAMA,
        "06/03/2026;10:05;PIX ENVIADO;300,00;D" + base + "PESSOA BETA;%s;%s" % (BETA, util.so_digitos(BETA)),
        "08/03/2026;16:40;PIX ENVIADO;150,00;D" + base + "PESSOA BETA;%s;%s" % (BETA, util.so_digitos(BETA)),
        "09/03/2026;08:00;TARIFA PACOTE;40,00;" + base + ";;",
    ]
    _txt("EXEMPLO_FICTICIO_extrato.csv", cab + "\r\n".join(linhas) + "\r\n")


def extrato_beta_csv():
    cab = "Data;Historico;Credito;Debito;Titular;CPF_CNPJ_Titular;Banco;Agencia;Conta;Favorecido;CPF_CNPJ_Favorecido\r\n"
    base = ";PESSOA BETA;%s;BANCO EXEMPLO;0002;99887-0;" % BETA
    linhas = [
        "06/03/2026;PIX RECEBIDO;300,00;" + base + "FULANO FICTICIO DA SILVA;%s" % FULANO,
        "07/03/2026;PIX ENVIADO;;280,00" + base + "PESSOA DELTA;%s" % DELTA,
        "08/03/2026;PIX RECEBIDO;150,00;" + base + "FULANO FICTICIO DA SILVA;%s" % FULANO,
        "10/03/2026;SAQUE;;100,00" + base + ";",
    ]
    _txt("EXEMPLO_FICTICIO_extrato_conta_beta.csv", cab + "\r\n".join(linhas) + "\r\n", "cp1252")


def simba_2010():
    t = "\t"
    titulares = t.join(["001", "1234", "567890", "1", "T", "1", "1", util.so_digitos(FULANO), "FULANO FICTICIO DA SILVA", "RG",
                        "0000000 SSP/XX", "RUA FICTICIA 1", "MAMBORE", "PR", "BRASIL", "87000000", "0000000000", "100000",
                        "01012025", "01012020", ""])
    extrato = t.join(["000000000000000001", "001", "1234", "567890", "1", "02032026", "DOC1", "TED RECEBIDA", "209",
                      "10000", "C", "10000", "C", "AGENCIA"])
    od = [t.join(["000000000000000011", "000000000000000001", "3000", "", "237", "0001", "11111", "1", "1",
                  util.so_digitos(ALFA), "PESSOA ALFA", "", "", "", "", "", "0", "distribuição de depósito"]),
          t.join(["000000000000000012", "000000000000000001", "7000", "", "341", "0002", "22222", "1", "1",
                  util.so_digitos(GAMA), "PESSOA GAMA", "", "", "", "", "", "0", ""])]
    _zip("EXEMPLO_FICTICIO_simba_2010.zip", [("TITULARES.txt", titulares + "\r\n"), ("EXTRATO.txt", extrato + "\r\n"),
                                             ("ORIGEM_DESTINO.txt", "\r\n".join(od) + "\r\n")])


def simba_in636():
    t = "\t"

    def tit(tipo, doc, nome):
        return t.join(["260", "1", "000777", "1", tipo, "1", "1", util.so_digitos(doc), nome, "", "", "RUA FICTICIA 2",
                       "4114203", "PR", "BRASIL", "87000000", "", "", "", "01012024", "", cnpj(9, False),
                       "INSTITUICAO FICTICIA SA", "", "conjunta@exemplo.invalid", "APARELHO FICTICIO X1", "", "0"])

    titulares = [tit("T", EPSILON, "PESSOA EPSILON"), tit("1", DELTA, "PESSOA DELTA"), tit("P", ALFA, "PESSOA ALFA")]

    def ext(chave, data, desc, cod, valor, nat, hora, ip, chave_pix, tipo_pix, idpix):
        return t.join([chave, "260", "1", "000777", "1", data, "D" + chave[-2:], desc, cod, valor, nat, "0", "C", "APP",
                       cnpj(9, False), "INSTITUICAO FICTICIA SA", "5", "4114203", "PR", ip, "443", "", hora, tipo_pix,
                       chave_pix, idpix, "123"])

    extrato = [ext("000000000000000101", "11032026", "PIX RECEBIDO", "261", "25000", "C", "131500", "203.0.113.10",
                   "", "", "E00000000202603111315FICTICIO001"),
               ext("000000000000000102", "12032026", "PIX ENVIADO", "135", "12000", "D", "020501", "2001:db8::25",
                   "beta@exemplo.invalid", "3", "E00000000202603120205FICTICIO002")]

    def od(chave_od, chave_ext, valor, doc, nome, pix, tipo_pix, coment, idpix):
        return t.join([chave_od, chave_ext, valor, "", "999", "1", "5555", "1", "1", util.so_digitos(doc), nome, "", "", "", "",
                       "", "0", "", cnpj(8, False), "", "", "", "", "", tipo_pix, pix, coment, idpix])

    ods = [od("000000000000000201", "000000000000000101", "25000", FULANO, "FULANO FICTICIO DA SILVA", util.so_digitos(FULANO), "1",
              "comentario ficticio", "E00000000202603111315FICTICIO001"),
           od("000000000000000202", "000000000000000102", "12000", BETA, "PESSOA BETA", "beta@exemplo.invalid", "3", "",
              "E00000000202603120205FICTICIO002")]
    _zip("EXEMPLO_FICTICIO_simba_in636.zip", [("TITULARES.txt", "\r\n".join(titulares) + "\r\n"),
                                              ("EXTRATO.txt", "\r\n".join(extrato) + "\r\n"),
                                              ("ORIGEM_DESTINO.txt", "\r\n".join(ods) + "\r\n")])


def mercadopago():
    recebidos = [["DATE_CREATED", "TRANSACTION_AMOUNT", "PYN_STATUS", "COUNTERPART_NAME", "COUNTERPART_DOCUMENT", "REFUNDED_AMOUNT"],
                 ["2026-04-01 10:00:00", 50.0, "approved", "PESSOA ALFA", ALFA, ""],
                 ["2026-04-02 11:30:00", 70.5, "rejected", "PESSOA GAMA", GAMA, ""],
                 ["2026-04-03 09:15:00", 20.0, "refunded", "PESSOA GAMA", GAMA, "20,00"],
                 ["2026-04-04 18:45:00", 30.0, "", "PESSOA BETA", BETA, ""]]
    realizados = [["DATE_CREATED", "TRANSACTION_AMOUNT", "PAYOUT_STATUS", "PAYOUT_TYPE", "COUNTERPART_NAME", "COUNTERPART_DOCUMENT"],
                  ["2026-04-05 08:00:00", 40.0, "approved", "pix", "PESSOA DELTA", DELTA],
                  ["2026-04-06 12:00:00", 25.0, "approved", "atm", "", ""]]
    with open(os.path.join(PASTA, "EXEMPLO_FICTICIO_mercadopago.xlsx"), "wb") as f:
        f.write(escritores.gerar_xlsx([("PIX recebidos", recebidos), ("PIX realizados", realizados)]))


def acessos():
    cab = "Data/Hora;Fuso;IP;Porta;Latitude;Longitude;Cidade;UF;Dispositivo;Evento;CPF\r\n"
    linhas = [
        "01/03/2026 09:08:11;UTC-03:00;203.0.113.10;51234;-24.3010;-52.5270;MAMBORE;PR;APARELHO FICTICIO X1;login;%s" % FULANO,
        "05/03/2026 14:20:00;UTC-03:00;198.51.100.7;40001;-24.0450;-52.3780;CAMPO MOURAO;PR;APARELHO FICTICIO X1;login;%s" % FULANO,
        "06/03/2026 10:03:42;UTC-03:00;203.0.113.10;51240;-24.3012;-52.5268;MAMBORE;PR;NAVEGADOR FICTICIO;transferencia;%s" % FULANO,
        "07/03/2026 07:00:00;UTC;2001:db8::25;443;;;;;APARELHO FICTICIO Z9;login;%s" % BETA,
    ]
    _txt("EXEMPLO_FICTICIO_acessos_ip_geo.csv", cab + "\r\n".join(linhas) + "\r\n")


def cadastro():
    cab = "Nome;CPF;Tipo_Titular;Banco;Agencia;Conta;Endereco;Cidade;UF;Telefone;Email;Data_Abertura\r\n"
    linhas = ["FULANO FICTICIO DA SILVA;%s;T;BANCO FICTICIO;0001;12345-6;RUA FICTICIA 1;MAMBORE;PR;(00) 90000-0001;fulano@exemplo.invalid;10/01/2020" % FULANO,
              "PESSOA ALFA;%s;P;BANCO FICTICIO;0001;12345-6;RUA FICTICIA 3;MAMBORE;PR;(00) 90000-0002;alfa@exemplo.invalid;10/01/2021" % ALFA]
    _txt("EXEMPLO_FICTICIO_cadastro.csv", cab + "\r\n".join(linhas) + "\r\n")


def rif_zip():
    com = ("Indexador;idComunicacao;NumeroOcorrenciaBC;Data_do_Recebimento;Data_da_operacao;DataFimFato;cpfCnpjComunicante;"
           "nomeComunicante;CidadeAgencia;UFAgencia;NomeAgencia;NumeroAgencia;informacoesAdicionais;CampoA;CampoB;CampoC;CampoD;CampoE;CodigoSegmento\r\n"
           "1;900001;OC-1;10/03/2026;01/03/2026;09/03/2026;%s;INSTITUICAO FICTICIA SA;MAMBORE;PR;AG CENTRO;0001;"
           "Movimentacao atipica ficticia envolvendo %s e chave alfa@exemplo.invalid;1.000,00;;;;;41\r\n") % (cnpj(9), FULANO)
    env = ("Indexador;idComunicacao;cpfCnpjEnvolvido;nomeEnvolvido;tipoEnvolvido;agenciaEnvolvido;contaEnvolvido;DataAberturaConta;DataAtualizacaoConta\r\n"
           "1;900001;%s;FULANO FICTICIO DA SILVA;Titular;0001;12345-6;10/01/2020;01/01/2026\r\n"
           "1;900001;%s;PESSOA ALFA;Remetente;;;;\r\n") % (FULANO, ALFA)
    oco = "Indexador;idComunicacao;Ocorrencia\r\n1;900001;Ocorrencia ficticia de teste - nao representa fato real\r\n"
    _zip("EXEMPLO_FICTICIO_rif.zip", [("RIF_FICTICIO_Comunicacoes.csv", com), ("RIF_FICTICIO_Envolvidos.csv", env),
                                      ("RIF_FICTICIO_Ocorrencias.csv", oco)])


def documento_pdf():
    pdf = escritores.PDF()
    pdf.titulo("OFICIO FICTICIO DE RESPOSTA - EXEMPLO", 13)
    pdf.texto("Documento fictício para teste. Nenhuma informação real.")
    pdf.texto("Cliente: FULANO FICTICIO DA SILVA, CPF %s, chave PIX alfa@exemplo.invalid." % FULANO)
    pdf.texto("Acesso registrado do IP 203.0.113.10 em 06/03/2026, coordenadas -24.3012, -52.5268.")
    pdf.texto("Contraparte: PESSOA BETA, CPF %s, conta 99887-0." % BETA)
    pdf.texto("Página 1 de 1 - exemplo")
    with open(os.path.join(PASTA, "EXEMPLO_FICTICIO_documento.pdf"), "wb") as f:
        f.write(pdf.gerar())


def main():
    os.makedirs(PASTA, exist_ok=True)
    extrato_csv()
    extrato_beta_csv()
    simba_2010()
    simba_in636()
    mercadopago()
    acessos()
    cadastro()
    rif_zip()
    documento_pdf()
    print("Exemplos fictícios gerados em", PASTA)


if __name__ == "__main__":
    main()
