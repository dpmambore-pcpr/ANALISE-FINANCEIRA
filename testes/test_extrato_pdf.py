import unittest

from base import CasoTeste, exemplo
from financeira import escritores, extrato_pdf, pesquisa


def pdf_texto(linhas):
    pdf = escritores.PDF()
    for ln in linhas:
        pdf.texto(ln, 6)
    return pdf.gerar()


CAB = ["EXTRATO DETALHADO - CASO FICTICIO", "Titular: PESSOA TESTE (investigado) CPF: 000.000.001-91 Início Rel.: 01/01/2026 Fim Rel.: 31/03/2026",
       "Banco: BANCO FICTICIO Nº Banco: 999", "Ag: 1 Inicio Mov.: 01/03/2026 Extrato (créditos): R$ %s Extrato (débitos): R$ 0,00",
       "C/C.: 55 Fim Mov.: 31/03/2026", "Tipo: Saldo Inicial: R$ 0,00", "Abert.: 01/01/2020 Saldo Final: R$ 100,00",
       "Data Histórico CNAB Doc. Valor (R$) D/C CPF/CNPJ Nome Benef/Depos Bco Ag Conta Observações"]


class TestExtratoPDF(CasoTeste):
    def test_importa_extrato_detalhado_fictício(self):
        f = self.fonte(exemplo("EXEMPLO_FICTICIO_extrato_detalhado.pdf"))
        prev = self.app.previa(f["id"])
        self.assertEqual(prev["extrato_detalhado"]["lancamentos"], 7)
        self.assertEqual(len(prev["extrato_detalhado"]["contas"]), 2)
        rel = self.app.importar(f["id"], "pdf_extrato", None, {}, self.usuario)
        self.assertEqual((rel["aceitos"], rel["pendentes"], rel["rejeitados"]), (7, 0, 0))
        self.assertEqual(rel["totais_aceitos"], {"C": 86000, "D": 33000})
        self.assertTrue(rel["controle"]["ok"], rel["controle"])
        self.assertTrue(any("zeros à esquerda" in a for a in rel["avisos"]))
        self.assertTrue(any("não é o documento original" in a for a in rel["avisos"]))
        self.assertEqual(rel["titulares"], 2)

        r = self.app.b.q("SELECT l.*, p.doc AS pdoc, p.nome AS pnome, p.observacao AS pobs FROM lancamentos l "
                         "LEFT JOIN partes p ON p.lancamento_id=l.id WHERE l.documento='1001'")[0]
        self.assertEqual((r["natureza"], r["valor_centavos"], r["data"], r["local"]), ("C", 60000, "2026-03-01", "página 1"))
        self.assertEqual(r["pdoc"], "00000000272")
        self.assertIn("zeros à esquerda restaurados", r["pobs"])
        self.assertIn("PIX RECEBIDO", r["bruto_json"])
        self.assertEqual(self.app.b.q1("SELECT cidade, uf FROM lancamentos WHERE documento='1006'")["uf"], "PR")
        self.assertEqual(self.app.b.q1("SELECT interface FROM lancamentos WHERE documento='1003'")["interface"], "INTERNET")
        nao_id = self.app.b.q1("SELECT COUNT(*) AS n FROM partes WHERE doc IS NULL AND nome IS NULL")
        self.assertEqual(nao_id["n"], 0)
        t = pesquisa.totais(self.app.b, self.caso, {})
        self.assertEqual(t["creditos_fmt"], "R$ 860,00")

    def test_total_divergente_do_relatorio_e_sinalizado(self):
        dados = pdf_texto([c % "999,00" if "%s" in c else c for c in CAB] +
                          ["01/03/2026 PIX RECEBIDO 209 1 100,00 C 000000191 FULANO 999 1 7"])
        f = self.fonte_bytes("divergente.pdf", dados)
        rel = self.app.importar(f["id"], "pdf_extrato", None, {}, self.usuario)
        self.assertEqual(rel["aceitos"], 1)
        self.assertFalse(rel["controle"]["ok"])
        self.assertTrue(any("não confere" in a for a in rel["avisos"]))

    def test_linha_com_data_fora_do_padrao_fica_pendente(self):
        dados = pdf_texto([c % "100,00" if "%s" in c else c for c in CAB] +
                          ["01/03/2026 PIX RECEBIDO 209 1 100,00 C", "02/03/2026 LINHA QUEBRADA SEM COLUNAS"])
        f = self.fonte_bytes("quebrada.pdf", dados)
        rel = self.app.importar(f["id"], "pdf_extrato", None, {}, self.usuario)
        self.assertEqual((rel["aceitos"], rel["pendentes"]), (1, 1))

    def test_outro_pdf_e_recusado_sem_gravar(self):
        f = self.fonte(exemplo("EXEMPLO_FICTICIO_documento.pdf"))
        self.assertNotIn("extrato_detalhado", self.app.previa(f["id"]))
        with self.assertRaises(ValueError):
            self.app.importar(f["id"], "pdf_extrato", None, {}, self.usuario)
        self.assertEqual(self.app.b.q1("SELECT COUNT(*) AS n FROM lancamentos")["n"], 0)

    def test_interpretacao_das_colunas(self):
        i = extrato_pdf.interpretar_resto("PESSOA OMEGA FICTICIA 077 1 354739670 PIX devolvido para OMEGA")
        self.assertEqual((i["nome"], i["banco"], i["conta"], i["obs_texto"]), ("PESSOA OMEGA FICTICIA", "077", "354739670", "PIX devolvido para OMEGA"))
        self.assertIsNone(extrato_pdf.interpretar_resto("9999 99999999999999999999 NAO-CORRENTISTA")["doc"])
        self.assertEqual(extrato_pdf.interpretar_resto("CONFORME CIRCULAR 3978/2020 AS INF")["texto_livre"], "CONFORME CIRCULAR 3978/2020 AS INF")


if __name__ == "__main__":
    unittest.main()
