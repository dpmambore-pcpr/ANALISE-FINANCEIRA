import unittest

import os

from base import RAIZ
from financeira import identificadores, util


class TestValores(unittest.TestCase):
    def test_raiz(self):
        self.assertTrue(os.path.isdir(os.path.join(RAIZ, "financeira")))

    def test_formatos(self):
        casos = {"1.234,56": 123456, "1,234.56": 123456, "1234,5": 123450, "R$ 1.000,00": 100000, "0,01": 1,
                 "1.234.567,89": 123456789, "100": 10000, "12.5": 1250, "-40,00": 4000, "(15,00)": 1500}
        for txt, esperado in casos.items():
            self.assertEqual(util.parse_valor(txt)["centavos"], esperado, txt)

    def test_sinal_preservado_sem_virar_natureza(self):
        self.assertEqual(util.parse_valor("-40,00")["sinal"], -1)
        self.assertEqual(util.parse_valor("40,00")["sinal"], 0)

    def test_ambiguos_ficam_pendentes(self):
        for txt in ("1.234", "12,345.6789", "abc", ""):
            self.assertIsNone(util.parse_valor(txt)["centavos"], txt)
        self.assertTrue(util.parse_valor("1.234")["ambiguo"])

    def test_simba_centavos(self):
        self.assertEqual(util.parse_centavos_sem_separador("10000"), 10000)
        self.assertEqual(util.parse_centavos_sem_separador("000"), 0)
        self.assertIsNone(util.parse_centavos_sem_separador("10,00"))

    def test_formatar(self):
        self.assertEqual(util.formatar_centavos(123456789), "R$ 1.234.567,89")


class TestDatas(unittest.TestCase):
    def test_formatos_e_fuso_preservado(self):
        d = util.parse_data("06/03/2026 10:03:42")
        self.assertEqual((d["data"], d["hora"], d["fuso"]), ("2026-03-06", "10:03:42", None))
        d = util.parse_data("2026-03-06T13:03:42Z")
        self.assertEqual((d["data"], d["hora"], d["fuso"]), ("2026-03-06", "13:03:42", "Z"))
        d = util.parse_data("2026-03-06 13:03:42-03:00")
        self.assertEqual(d["fuso"], "-03:00")
        self.assertEqual(util.parse_data("05022008", "ddmmaaaa")["data"], "2008-02-05")

    def test_invalidas(self):
        self.assertIsNone(util.parse_data("31/02/2026")["data"])
        self.assertIsNone(util.parse_data("01/02/26")["data"])


class TestDocumentos(unittest.TestCase):
    def test_cpf_cnpj(self):
        c = util.gerar_cpf_ficticio(1)
        self.assertEqual(util.classificar_documento(c)[0], "cpf")
        self.assertEqual(util.classificar_documento("***.000.001-**")[0], "parcial")
        self.assertEqual(util.classificar_documento("00000000100")[0], "cpf_dv_invalido")
        self.assertEqual(util.classificar_documento(util.gerar_cnpj_ficticio(9))[0], "cnpj")
        self.assertEqual(util.classificar_documento("191", "1"), ("cpf", "00000000191"))

    def test_extracao_texto(self):
        texto = ("CPF 000.000.001-91, e-mail alfa@exemplo.invalid, IP 203.0.113.10 e 2001:db8::25, "
                 "coordenadas -24.3012, -52.5268, chave 123e4567-e89b-12d3-a456-426614174000, em 06/03/2026")
        tipos = {t for t, _, _ in identificadores.extrair(texto)}
        self.assertTrue({"cpf", "email", "ip", "coordenada", "pix", "data"} <= tipos, tipos)


if __name__ == "__main__":
    unittest.main()
