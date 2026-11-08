"""Número COMPE vira nome do banco nos rótulos."""

import unittest

from base import CasoTeste, exemplo
from financeira import bancos, pesquisa


class TestRotuloBanco(unittest.TestCase):
    def test_numero_ganha_nome(self):
        self.assertEqual(bancos.rotulo_banco("260"), "260 Nubank")
        self.assertEqual(bancos.rotulo_banco("0260"), "260 Nubank")
        self.assertEqual(bancos.rotulo_banco("001"), "001 Banco do Brasil")
        self.assertEqual(bancos.rotulo_banco("341"), "341 Itaú Unibanco")

    def test_nome_ja_escrito_permanece(self):
        self.assertEqual(bancos.rotulo_banco("BANCO FICTICIO"), "BANCO FICTICIO")
        self.assertEqual(bancos.rotulo_banco("Nubank"), "Nubank")

    def test_conta_com_numero(self):
        self.assertEqual(bancos.rotulo_conta("260 | ag 0001 | conta 123"), "260 Nubank | ag 0001 | conta 123")


class TestFacetaBancoSimba(CasoTeste):
    def test_simba_mostra_nome_do_banco(self):
        f = self.fonte(exemplo("EXEMPLO_FICTICIO_simba_2010.zip"))
        self.app.importar(f["id"], "simba", None, {}, self.usuario)
        facs = {x["chave"]: x for x in pesquisa.facetas(self.app.b, self.caso, {})}
        rotulos = {v["rotulo"] for v in facs["banco"]["valores"]}
        self.assertTrue(any("Banco do Brasil" in r for r in rotulos), rotulos)
        enviou = {v["rotulo"] for v in facs["origem_banco"]["valores"]}
        self.assertTrue(enviou, "crédito SIMBA deve listar o banco de quem enviou")
        self.assertTrue(any(v["valor"] != v["rotulo"] for v in facs["origem_banco"]["valores"]), enviou)
