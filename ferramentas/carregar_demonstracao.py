"""Cria o caso "DEMONSTRAÇÃO FICTÍCIA" com todos os arquivos de exemplos/ importados.

Uso: python ferramentas/carregar_demonstracao.py [--dados PASTA] [--usuario NOME]
"""

import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from financeira import servico  # noqa: E402

EX = os.path.join(RAIZ, "exemplos")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", default=os.path.join(RAIZ, "dados"))
    ap.add_argument("--usuario", default="demonstracao")
    a = ap.parse_args(argv)
    app = servico.App(a.dados)
    u = a.usuario
    caso = app.criar_caso("DEMONSTRAÇÃO FICTÍCIA", "Exemplos fictícios para treinamento", u)

    def tabela(nome, adaptador, ajuste=None, opcoes=None, aba=None):
        f = app.receber_arquivo(caso, os.path.join(EX, nome), nome, u)
        p = app.previa(f["id"], aba=aba)
        mapa = dict(p["sugestoes"][adaptador], **(ajuste or {}))
        op = dict({"linha_cabecalho": p["linha_cabecalho"], "aba": p["aba"]}, **(opcoes or {}))
        rel = app.importar(f["id"], adaptador, mapa, op, u)
        print("%-45s %-9s aceitos=%d pendentes=%d acessos=%d titulares=%d" % (
            nome + (" [%s]" % aba if aba else ""), adaptador, rel["aceitos"], rel["pendentes"], rel["acessos"], rel["titulares"]))
        return f

    tabela("EXEMPLO_FICTICIO_extrato.csv", "extrato", opcoes={"controle": {"creditos": "1.000,00", "debitos": "450,00"}})
    tabela("EXEMPLO_FICTICIO_extrato_conta_beta.csv", "extrato",
           {"credito": "Credito", "debito": "Debito", "cp_nome": "Favorecido", "cp_doc": "CPF_CNPJ_Favorecido", "descricao": "Historico"})
    f = tabela("EXEMPLO_FICTICIO_mercadopago.xlsx", "extrato", opcoes={"natureza_fixa": "C"}, aba="PIX recebidos")
    p = app.previa(f["id"], aba="PIX realizados")
    app.importar(f["id"], "extrato", p["sugestoes"]["extrato"], {"aba": "PIX realizados", "linha_cabecalho": 1, "natureza_fixa": "D"}, u)
    tabela("EXEMPLO_FICTICIO_acessos_ip_geo.csv", "acessos", {"data": "Data/Hora"})
    tabela("EXEMPLO_FICTICIO_cadastro.csv", "cadastro")
    for nome, op in (("EXEMPLO_FICTICIO_simba_2010.zip", {}), ("EXEMPLO_FICTICIO_simba_in636.zip", {"confirmo_leiaute_in636": True})):
        f = app.receber_arquivo(caso, os.path.join(EX, nome), nome, u)
        rel = app.importar(f["id"], "simba", None, op, u)
        print("%-45s simba     aceitos=%d" % (nome, rel["aceitos"]))
    f = app.receber_arquivo(caso, os.path.join(EX, "EXEMPLO_FICTICIO_rif.zip"), "EXEMPLO_FICTICIO_rif.zip", u)
    app.importar(f["id"], "rif", None, {"numero_rif": "RIF FICTÍCIO 1", "coluna_valor": "CampoA"}, u)
    f = app.receber_arquivo(caso, os.path.join(EX, "EXEMPLO_FICTICIO_documento.pdf"), "EXEMPLO_FICTICIO_documento.pdf", u)
    app.importar(f["id"], "pdf_texto", None, {}, u)
    print("Caso de demonstração criado (id %d) em %s" % (caso, os.path.abspath(a.dados)))


if __name__ == "__main__":
    main()
