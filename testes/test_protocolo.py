# -*- coding: utf-8 -*-
import unittest

from base import CasoTeste, exemplo
from financeira import protocolo, pesquisa


class TestLerNomeArquivo(unittest.TestCase):
    def test_so_protocolo_vira_caso_677(self):
        r = protocolo.ler_nome("056-PCPR-000677-20.pdf")
        self.assertEqual(r["protocolo"], "056-PCPR-000677-20")
        self.assertEqual(r["numero"], 677)
        self.assertIsNone(r["inscricao"])
        self.assertEqual(r["nome_sugerido"], "Caso 677")

    def test_extrato_detalhado_nao_entra_no_nome(self):
        r = protocolo.ler_nome("EXTRATO DETALHADO 056-PCPR-000677-20.pdf")
        self.assertEqual(r["numero"], 677)
        self.assertIsNone(r["inscricao"])
        self.assertEqual(r["nome_sugerido"], "Caso 677")
        r2 = protocolo.ler_nome("056-PCPR-000677-20_extrato_detalhado.xlsx")
        self.assertEqual(r2["nome_sugerido"], "Caso 677")

    def test_inscricao_elon_musk(self):
        r = protocolo.ler_nome("056-PCPR-000677-20 elon musk.pdf")
        self.assertEqual(r["inscricao"], "elon musk")
        self.assertEqual(r["nome_sugerido"], "Caso 677 elon musk")

    def test_inscricao_casa_mambore(self):
        r = protocolo.ler_nome("056-PCPR-000677-20_casa_mambore.csv")
        self.assertEqual(r["nome_sugerido"], "Caso 677 casa mambore")

    def test_inscricao_gordo(self):
        r = protocolo.ler_nome("056-PCPR-000677-20-gordo.zip")
        self.assertEqual(r["nome_sugerido"], "Caso 677 gordo")

    def test_sem_protocolo_usa_nome_do_arquivo(self):
        r = protocolo.ler_nome("planilha_do_banco.csv")
        self.assertIsNone(r["numero"])
        self.assertTrue(r["nome_sugerido"])

    def test_pecas_do_rif_nao_viram_apelido(self):
        r = protocolo.ler_nome("RIF_FICTICIO_Comunicacoes.csv")
        self.assertNotIn("Comunicacoes", r["nome_sugerido"])
        r2 = protocolo.ler_nome("056-PCPR-000677-20_ENVOLVIDOS.csv")
        self.assertEqual(r2["nome_sugerido"], "Caso 677")


class TestCasoProtocoloEConjunto(CasoTeste):
    def test_criar_com_protocolo_e_encontrar(self):
        cid = self.app.criar_caso("Caso 677", "", self.usuario, protocolo="056-PCPR-000677-20",
                                  numero=677, inscricao=None)
        r = self.app.reconhecer_arquivo("056-PCPR-000677-20 elon musk.pdf", self.usuario)
        self.assertEqual(r["numero"], 677)
        self.assertEqual(r["existentes"][0]["id"], cid)

    def test_integrar_dois_casos_na_pesquisa(self):
        a = self.app.criar_caso("Caso 677 elon musk", "", self.usuario, numero=677, inscricao="elon musk")
        b = self.app.criar_caso("Caso 677 gordo", "", self.usuario, numero=677, inscricao="gordo")
        j = self.app.integrar_casos([a, b], self.usuario)
        self.assertEqual(sorted(protocolo.ids_abrangidos(self.app.b, j)), sorted([a, b]))
        ids = protocolo.ids_abrangidos(self.app.b, j)
        t = pesquisa.totais(self.app.b, ids, {})
        self.assertEqual(t["n_registros"], 0)

    def test_integrar_soma_lancamentos(self):
        a = self.app.criar_caso("Caso 677 elon musk", "", self.usuario, numero=677, inscricao="elon musk")
        b = self.app.criar_caso("Caso 677 gordo", "", self.usuario, numero=677, inscricao="gordo")
        self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"), caso=a,
                             nome="056-PCPR-000677-20_elon_musk.csv")
        self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato_conta_beta.csv"), caso=b,
                             nome="056-PCPR-000677-20_gordo.csv")
        ta = pesquisa.totais(self.app.b, a, {})
        tb = pesquisa.totais(self.app.b, b, {})
        self.assertGreater(ta["n_registros"], 0)
        self.assertGreater(tb["n_registros"], 0)
        j = self.app.integrar_casos([a, b], self.usuario)
        tj = pesquisa.totais(self.app.b, j, {})
        self.assertEqual(tj["n_registros"], ta["n_registros"] + tb["n_registros"])
        rec = self.app.reconhecer_arquivo("056-PCPR-000677-20 elon musk.pdf", self.usuario)
        self.assertTrue(any(c["id"] == a and c.get("mesmo_apelido") for c in rec["existentes"]))


if __name__ == "__main__":
    unittest.main()
