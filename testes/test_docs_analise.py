# -*- coding: utf-8 -*-
import os
import shutil
import unittest

from base import CasoTeste, exemplo
from financeira import analise, ia, servico


class TestDocsAnalise(CasoTeste):
    def _txt(self, nome, texto):
        p = os.path.join(self.tmp, nome)
        with open(p, "w", encoding="utf-8") as f:
            f.write(texto)
        return p

    def test_txt_boletim_vira_pagina_e_papel(self):
        p = self._txt("BO_FICTICIO.txt",
                      "BOLETIM DE OCORRÊNCIA FICTÍCIO\nVítima: MARIA FICTICIA\nInvestigado: JOAO FICTICIO\n")
        r = self.app.receber_documento_analise(self.caso, p, "BO_FICTICIO.txt", "boletim", self.usuario)
        self.assertEqual(r["fonte"]["papel"], "boletim")
        self.assertEqual(r["relatorio"]["paginas"], 1)
        blocos = analise._docs_texto(self.app.b, self.caso)
        self.assertTrue(any("MARIA FICTICIA" in (b.get("texto") or "") for b in blocos), blocos)
        vit, inv = analise._pessoas_dos_docs(blocos)
        self.assertTrue(any("MARIA" in (x.get("nome") or "").upper() for x in vit), vit)
        self.assertTrue(any("JOAO" in (x.get("nome") or "").upper() for x in inv), inv)
        fs = self.app.listar_fontes(self.caso)
        self.assertEqual(fs[0]["n_paginas"], 1)

    def test_pdf_documento(self):
        dest = os.path.join(self.tmp, "oficio_ficticio.pdf")
        shutil.copy(exemplo("EXEMPLO_FICTICIO_documento.pdf"), dest)
        r = self.app.receber_documento_analise(self.caso, dest, "oficio_ficticio.pdf", "documento", self.usuario)
        self.assertEqual(r["fonte"]["papel"], "documento")
        self.assertGreaterEqual(r["relatorio"]["paginas"], 1)
        self.assertFalse(r["duplicada"])

    def test_duplicata_so_marca_papel(self):
        corpo = "RELATORIO FICTICIO DE INVESTIGACAO\n"
        a = self._txt("rel_a.txt", corpo)
        b = self._txt("rel_b.txt", corpo)
        r1 = self.app.receber_documento_analise(self.caso, a, "rel.txt", "documento", self.usuario)
        r2 = self.app.receber_documento_analise(self.caso, b, "rel2.txt", "relatorio_investigacao", self.usuario)
        self.assertTrue(r2["duplicada"])
        self.assertEqual(r2["fonte"]["id"], r1["fonte"]["id"])
        self.assertEqual(r2["fonte"]["papel"], "relatorio_investigacao")
        self.assertTrue(r2["relatorio"].get("ja_existia"))

    def test_extensao_e_papel_recusados(self):
        p = os.path.join(self.tmp, "planilha.xlsx")
        with open(p, "wb") as f:
            f.write(b"x")
        with self.assertRaises(ValueError):
            self.app.receber_documento_analise(self.caso, p, "planilha.xlsx", "boletim", self.usuario)
        t = self._txt("ok.txt", "texto ficticio")
        with self.assertRaises(ValueError):
            self.app.receber_documento_analise(self.caso, t, "ok.txt", "extrato", self.usuario)

    def test_texto_entra_no_contexto_da_ia(self):
        p = self._txt("bo.txt", "BO FICTICIO numero 999\n")
        self.app.receber_documento_analise(self.caso, p, "bo.txt", "boletim", self.usuario)
        txt, alc = ia._texto_docs_caso(self.app.b, self.caso)
        self.assertIn("BO FICTICIO", txt)
        self.assertGreaterEqual(alc["documentos"], 1)

    def test_extensoes_aceitas(self):
        self.assertEqual(servico.EXT_DOC_ANALISE, (".pdf", ".txt", ".md"))


if __name__ == "__main__":
    unittest.main()
