import unittest

from base import CasoTeste, cpf, exemplo
from financeira import escritores, pesquisa, util


class TestExtratoCSV(CasoTeste):
    def test_valores_de_controle_do_exemplo(self):
        _, rel = self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"),
                                      opcoes={"controle": {"creditos": "1.000,00", "debitos": "450,00", "quantidade": "5"}})
        self.assertEqual((rel["aceitos"], rel["pendentes"], rel["rejeitados"]), (4, 1, 0))
        self.assertTrue(rel["controle"]["ok"], rel["controle"])
        t = pesquisa.totais(self.app.b, self.caso, {})
        self.assertEqual((t["creditos"], t["debitos"], t["pendentes"]), (100000, 45000, 4000))
        top = t["destinos"]["itens"][0]
        self.assertEqual((top["nome"], top["n"], top["soma"]), ("PESSOA BETA", 2, 45000))

    def test_controle_divergente_e_reportado(self):
        _, rel = self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"), opcoes={"controle": {"creditos": "999,00"}})
        self.assertFalse(rel["controle"]["ok"])

    def test_rastreabilidade_e_original(self):
        f, _ = self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"))
        self.assertEqual(f["sha256"], util.sha256_arquivo(exemplo("EXEMPLO_FICTICIO_extrato.csv")))
        l = self.app.b.q1("SELECT * FROM lancamentos WHERE valor_centavos=60000")
        self.assertEqual(l["linha"], 2)
        self.assertIn("PIX RECEBIDO", l["bruto_json"])
        self.assertTrue(self.app.conferir_fontes(self.caso)[0]["ok"])

    def test_arquivo_identico_bloqueado(self):
        self.fonte(exemplo("EXEMPLO_FICTICIO_extrato.csv"))
        with self.assertRaises(Exception):
            self.fonte(exemplo("EXEMPLO_FICTICIO_extrato.csv"))

    def test_sinal_so_com_confirmacao(self):
        csv = "Data;Valor;Descricao\n01/01/2026;100,00;A\n02/01/2026;-30,00;B\n".encode()
        f = self.fonte_bytes("sinal.csv", csv)
        p = self.app.previa(f["id"])
        rel = self.app.importar(f["id"], "extrato", p["sugestoes"]["extrato"], {"linha_cabecalho": 1}, self.usuario)
        self.assertEqual(rel["pendentes"], 2)
        self.app.desfazer_importacao(rel["importacao_id"], self.usuario)
        rel = self.app.importar(f["id"], "extrato", p["sugestoes"]["extrato"], {"linha_cabecalho": 1, "sinal_credito": True}, self.usuario)
        self.assertEqual(rel["totais_aceitos"], {"C": 10000, "D": 3000})

    def test_colunas_credito_debito_e_dois_lados(self):
        self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"))
        _, rel = self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato_conta_beta.csv"),
                                      ajuste={"credito": "Credito", "debito": "Debito", "cp_nome": "Favorecido",
                                              "cp_doc": "CPF_CNPJ_Favorecido", "descricao": "Historico"})
        self.assertEqual(rel["totais_aceitos"], {"C": 45000, "D": 38000})
        dups = self.app.b.q("SELECT * FROM duplicatas WHERE criterio='dois_lados'")
        self.assertEqual(len(dups), 2)
        t = pesquisa.totais(self.app.b, self.caso, {})
        self.assertEqual(t["creditos"], 100000 + 45000, "dois lados não são somados nem descartados automaticamente")
        self.assertTrue(any("débito em uma e crédito em outra" in a for a in t["avisos"]))

    def test_desfazer(self):
        _, rel = self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"))
        self.app.desfazer_importacao(rel["importacao_id"], self.usuario)
        self.assertEqual(self.app.b.q1("SELECT COUNT(*) n FROM lancamentos")["n"], 0)
        self.assertEqual(self.app.b.q1("SELECT COUNT(*) n FROM ocorrencias_ident")["n"], 0)


class TestMercadoPagoXLSX(CasoTeste):
    def test_situacoes_e_estornos(self):
        f = self.fonte(exemplo("EXEMPLO_FICTICIO_mercadopago.xlsx"))
        p = self.app.previa(f["id"], aba="PIX recebidos")
        self.assertIn("Mercado Pago", p["perfil"]["nome"])
        mapa = p["sugestoes"]["extrato"]
        self.assertEqual(mapa["situacao"], "PYN_STATUS")
        rel = self.app.importar(f["id"], "extrato", mapa, {"aba": "PIX recebidos", "linha_cabecalho": 1, "natureza_fixa": "C"}, self.usuario)
        self.assertEqual(rel["aceitos"], 1)
        self.assertEqual(rel["pendentes"], 3)
        self.assertEqual(rel["totais_aceitos"]["C"], 5000)
        p2 = self.app.previa(f["id"], aba="PIX realizados")
        rel2 = self.app.importar(f["id"], "extrato", p2["sugestoes"]["extrato"],
                                 {"aba": "PIX realizados", "linha_cabecalho": 1, "natureza_fixa": "D"}, self.usuario)
        self.assertEqual(rel2["totais_aceitos"]["D"], 6500)
        saque = self.app.b.q1("SELECT * FROM lancamentos WHERE tipo_operacao='atm'")
        self.assertEqual(saque["local"], "PIX realizados")


class TestAcessosCadastro(CasoTeste):
    def test_acessos_nao_viram_transacao(self):
        _, rel = self.importar_tabela(exemplo("EXEMPLO_FICTICIO_acessos_ip_geo.csv"), "acessos",
                                      ajuste={"data": "Data/Hora"})
        self.assertEqual(rel["acessos"], 4)
        self.assertEqual(self.app.b.q1("SELECT COUNT(*) n FROM lancamentos")["n"], 0)
        a = self.app.b.q1("SELECT * FROM acessos WHERE linha=2")
        self.assertEqual((a["ip"], a["latitude"], a["fuso"], a["hora"]), ("203.0.113.10", "-24.3010", "UTC-03:00", "09:08:11"))
        ips = {o["valor_norm"] for o in self.app.b.q("SELECT valor_norm FROM ocorrencias_ident WHERE tipo='ip'")}
        self.assertIn("2001:db8::25", ips)

    def test_cadastro(self):
        _, rel = self.importar_tabela(exemplo("EXEMPLO_FICTICIO_cadastro.csv"), "cadastro")
        self.assertEqual(rel["titulares"], 2)
        self.assertEqual(self.app.b.q1("SELECT COUNT(*) n FROM lancamentos")["n"], 0)


class TestPerfisEArquivosGrandes(CasoTeste):
    def test_perfil_aprendido(self):
        csv = "DT MOV;HIST;VLR;D/C\n01/01/2026;X;10,00;C\n".encode()
        f = self.fonte_bytes("banco_novo.csv", csv)
        mapa = {"data": "DT MOV", "descricao": "HIST", "valor": "VLR", "natureza": "D/C"}
        self.app.importar(f["id"], "extrato", mapa, {"linha_cabecalho": 1, "salvar_perfil": True, "nome_perfil": "Banco Novo"}, self.usuario)
        f2 = self.fonte_bytes("banco_novo_2.csv", csv.replace(b"10,00", b"20,00"))
        p = self.app.previa(f2["id"])
        self.assertEqual(p["perfil"]["nome"], "Banco Novo")
        self.assertEqual(p["sugestoes"]["extrato"]["natureza"], "D/C")

    def test_arquivo_grande_em_lotes(self):
        linhas = ["Data;Valor;Natureza;Contraparte;CPF"]
        for i in range(12000):
            linhas.append("01/01/2026;1,00;%s;P%d;%s" % ("C" if i % 2 else "D", i % 7, util.formatar_documento(cpf(10 + i % 7))))
        f = self.fonte_bytes("grande.csv", ("\n".join(linhas) + "\n").encode())
        p = self.app.previa(f["id"])
        rel = self.app.importar(f["id"], "extrato", p["sugestoes"]["extrato"] | {"cp_nome": "Contraparte", "cp_doc": "CPF"},
                                {"linha_cabecalho": 1}, self.usuario)
        self.assertEqual(rel["aceitos"], 12000)
        self.assertEqual(rel["totais_aceitos"], {"C": 600000, "D": 600000})

    def test_xlsx_numeros_e_datas(self):
        dados = escritores.gerar_xlsx([("Plan1", [["Data", "Valor", "Natureza"], ["2026-01-05", 1234.5, "C"], ["2026-01-06", 0.1, "D"]])])
        f = self.fonte_bytes("n.xlsx", dados)
        p = self.app.previa(f["id"])
        rel = self.app.importar(f["id"], "extrato", p["sugestoes"]["extrato"], {"linha_cabecalho": 1, "aba": "Plan1"}, self.usuario)
        self.assertEqual(rel["totais_aceitos"], {"C": 123450, "D": 10})


if __name__ == "__main__":
    unittest.main()
