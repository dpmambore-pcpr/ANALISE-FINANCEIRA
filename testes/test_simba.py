import unittest

from base import CasoTeste, cpf, exemplo, zip_bytes
from financeira import pesquisa, simba

T = "\t"


def ext2010(chave, valor, nat="C", conta="567890", data="02032026"):
    return T.join([chave, "001", "1234", conta, "1", data, "D1", "TED", "209", valor, nat, "0", "C", "AG"])


def od2010(chave_od, chave, valor, doc, nome):
    return T.join([chave_od, chave, valor, "", "237", "1", "1", "1", "1", doc, nome, "", "", "", "", "", "0", ""])


def tit2010(tipo, doc, nome, conta="567890"):
    return T.join(["001", "1234", conta, "1", tipo, "1", "1", doc, nome, "", "", "", "", "", "", "", "", "", "", "", ""])


class TestSimba2010(CasoTeste):
    def importar_zip(self, arquivos, nome="s.zip", opcoes=None, remessa=None):
        f = self.fonte_bytes(nome, zip_bytes(arquivos), remessa)
        return f, self.app.importar(f["id"], "simba", None, opcoes or {}, self.usuario)

    def test_exemplo_parcelas_sem_multiplicar(self):
        f = self.fonte(exemplo("EXEMPLO_FICTICIO_simba_2010.zip"))
        rel = self.app.importar(f["id"], "simba", None, {}, self.usuario)
        self.assertEqual(rel["aceitos"], 1)
        self.assertEqual(rel["parcelas"]["conferidas"], 1)
        t = pesquisa.totais(self.app.b, self.caso, {})
        self.assertEqual(t["creditos"], 10000, "R$ 100,00 e não R$ 200,00")
        origens = {i["nome"]: i["soma"] for i in t["origens"]["itens"]}
        self.assertEqual(origens, {"PESSOA ALFA": 3000, "PESSOA GAMA": 7000})
        l = self.app.b.q1("SELECT * FROM lancamentos")
        self.assertEqual((l["titular_nome"], l["local"], l["linha"], l["chave_local"]),
                         ("FULANO FICTICIO DA SILVA", "EXTRATO.txt", 1, "000000000000000001"))
        p = self.app.b.q("SELECT * FROM partes ORDER BY ordem")
        self.assertEqual([(x["local"], x["linha"]) for x in p], [("ORIGEM_DESTINO.txt", 1), ("ORIGEM_DESTINO.txt", 2)])

    def test_parcelas_divergentes_nao_distribuidas(self):
        self.importar_zip({"EXTRATO.txt": ext2010("1", "10000"),
                           "ORIGEM_DESTINO.txt": "\n".join([od2010("11", "1", "3000", cpf(2), "A"), od2010("12", "1", "6000", cpf(3), "B")])})
        t = pesquisa.totais(self.app.b, self.caso, {})
        self.assertEqual(t["creditos"], 10000)
        self.assertEqual(t["origens"]["itens"], [])
        self.assertEqual(t["origens"]["nao_distribuido"]["soma"], 10000)

    def test_chave_orfa_bloqueia(self):
        with self.assertRaises(simba.ErroSimba):
            self.importar_zip({"EXTRATO.txt": ext2010("1", "10000"), "ORIGEM_DESTINO.txt": od2010("11", "2", "10000", cpf(2), "A")})
        self.assertEqual(self.app.b.q1("SELECT COUNT(*) n FROM lancamentos")["n"], 0)
        self.assertEqual(self.app.b.q1("SELECT estado FROM importacoes")["estado"], "desfeita")

    def test_mesma_chave_em_remessas_diferentes_nao_mistura(self):
        r1 = self.app.criar_remessa(self.caso, "Banco A", "A", "", self.usuario)
        r2 = self.app.criar_remessa(self.caso, "Banco B", "B", "", self.usuario)
        self.importar_zip({"EXTRATO.txt": ext2010("1", "10000"), "ORIGEM_DESTINO.txt": od2010("11", "1", "10000", cpf(2), "A")}, "a.zip", remessa=r1)
        self.importar_zip({"EXTRATO.txt": ext2010("1", "5000", "D"), "ORIGEM_DESTINO.txt": od2010("11", "1", "5000", cpf(3), "B")}, "b.zip", remessa=r2)
        linhas = self.app.b.q("SELECT l.valor_centavos, l.remessa_id, p.nome FROM lancamentos l JOIN partes p ON p.lancamento_id=l.id ORDER BY l.id")
        self.assertEqual([(x["valor_centavos"], x["remessa_id"], x["nome"]) for x in linhas], [(10000, r1, "A"), (5000, r2, "B")])

    def test_dois_extratos_no_mesmo_zip_recusado(self):
        with self.assertRaises(simba.ErroSimba):
            self.importar_zip({"a/EXTRATO.txt": ext2010("1", "1"), "b/EXTRATO.txt": ext2010("1", "1"),
                               "ORIGEM_DESTINO.txt": od2010("11", "1", "1", cpf(2), "A")})

    def test_conta_conjunta_e_representante(self):
        self.importar_zip({"TITULARES.txt": "\n".join([tit2010("T", cpf(1), "TITULAR UM"), tit2010("1", cpf(4), "COTITULAR DOIS"),
                                                       tit2010("P", cpf(5), "PROCURADOR TRES")]),
                           "EXTRATO.txt": ext2010("1", "10000"), "ORIGEM_DESTINO.txt": od2010("11", "1", "10000", cpf(2), "A")})
        l = self.app.b.q1("SELECT * FROM lancamentos")
        self.assertTrue(l["titular_nome"].startswith("CONTA CONJUNTA"))
        self.assertIsNone(l["titular_doc"])
        self.assertEqual(l["conta_qtd_titulares"], 2)
        self.assertIn("PROCURADOR TRES", l["titular_obs"])

    def test_natureza_asterisco_pendente(self):
        _, rel = self.importar_zip({"EXTRATO.txt": ext2010("1", "10000", "*"), "ORIGEM_DESTINO.txt": od2010("11", "1", "10000", cpf(2), "A")})
        self.assertEqual(rel["pendentes"], 1)

    def test_campos_errados_nao_inferidos(self):
        with self.assertRaises(simba.ErroSimba):
            self.importar_zip({"EXTRATO.txt": T.join(["x"] * 15), "ORIGEM_DESTINO.txt": od2010("11", "1", "1", cpf(2), "A")})


class TestSimbaIN636(CasoTeste):
    def test_exige_confirmacao(self):
        f = self.fonte(exemplo("EXEMPLO_FICTICIO_simba_in636.zip"))
        with self.assertRaises(simba.ErroSimba):
            self.app.importar(f["id"], "simba", None, {}, self.usuario)

    def test_extras_pix_hora_utc_ip(self):
        f = self.fonte(exemplo("EXEMPLO_FICTICIO_simba_in636.zip"))
        rel = self.app.importar(f["id"], "simba", None, {"confirmo_leiaute_in636": True}, self.usuario)
        self.assertEqual(rel["totais_aceitos"], {"C": 25000, "D": 12000})
        self.assertTrue(any("EXPERIMENTAL" in a for a in rel["avisos"]))
        l = self.app.b.q1("SELECT * FROM lancamentos WHERE natureza='D'")
        self.assertEqual((l["hora"], l["ip"], l["pix_chave"]), ("02:05:01", "2001:db8::25", "beta@exemplo.invalid"))
        self.assertTrue(l["fuso"].startswith("UTC"))
        self.assertEqual(l["data"], "2026-03-12", "data e hora UTC preservadas sem conversão")
        p = self.app.b.q1("SELECT * FROM partes WHERE lancamento_id=?", (l["id"],))
        self.assertEqual((p["pix_chave"], p["pix_tipo"]), ("beta@exemplo.invalid", "e-mail"))
        self.assertIn("COMENTARIO_PIX", p["bruto_json"])
        self.assertTrue(l["titular_nome"].startswith("CONTA CONJUNTA"))
        self.assertEqual(self.app.b.q1("SELECT COUNT(*) n FROM acessos")["n"], 2)


if __name__ == "__main__":
    unittest.main()
