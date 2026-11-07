# -*- coding: utf-8 -*-
import unittest

from base import CasoTeste, cpf
from financeira import analise, grafo, ia, util


CAB = "Data;Hora;Descricao;Valor;Natureza;Titular;CPF_CNPJ_Titular;Banco;Agencia;Conta;Contraparte;CPF_CNPJ_Contraparte;Chave_PIX\n"


def linha(data, hora, desc, valor, nat, titular, doc_t, banco, ag, conta, cp, doc_cp):
    return "%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;\n" % (
        data, hora, desc, valor, nat, titular, doc_t, banco, ag, conta, cp, doc_cp)


class TestAnaliseAutomatica(CasoTeste):
    def _importar_csv(self, nome, corpo):
        f = self.fonte_bytes(nome, corpo.encode("utf-8"))
        p = self.app.previa(f["id"])
        return self.app.importar(f["id"], "extrato", p["sugestoes"]["extrato"], {"linha_cabecalho": 1}, self.usuario)

    def test_classificar_historico(self):
        self.assertEqual(analise.classificar_historico("PIX RECEBIDO"), "pix")
        self.assertEqual(analise.classificar_historico("SAQUE EM ESPÉCIE"), "saque")
        self.assertEqual(analise.classificar_historico("COMPRA CARTÃO MASTERCARD"), "cartao")
        self.assertEqual(analise.classificar_historico("TARIFA PACOTE"), "tarifa")

    def test_trafico_valores_semelhantes_e_passagem(self):
        inv, dinv = "INVESTIGADO FICTICIO", util.formatar_documento(cpf(11))
        linhas = [CAB]
        # muitos créditos de R$ 200,00 de remetentes distintos (padrão operacional a verificar)
        for i, dia in enumerate(("01", "02", "03", "04", "05", "06")):
            cp = "REMETENTE %s" % (i + 1)
            linhas.append(linha("%s/03/2026" % dia, "10:0%d" % i, "PIX RECEBIDO",
                                "200,00", "C", inv, dinv, "BANCO FICTICIO", "0001", "9999-0", cp,
                                util.formatar_documento(cpf(20 + i))))
            linhas.append(linha("%s/03/2026" % dia, "10:3%d" % i, "PIX ENVIADO", "200,00", "D", inv, dinv,
                                "BANCO FICTICIO", "0001", "9999-0", "LARANJA FICTICIO",
                                util.formatar_documento(cpf(30))))
        self._importar_csv("trafico_ficticio.csv", "".join(linhas))
        r = analise.analisar(self.app.b, self.caso, self.usuario, {}, "trafico", "", "")
        self.assertEqual(r["hipotese_crime"], "trafico")
        tipos = {a["tipo"] for a in r["achados"]}
        self.assertIn("valores_semelhantes", tipos)
        self.assertIn("lavagem_in_out", tipos)
        self.assertTrue(any("passagem" in a["tipo"] or "passagem" in a.get("texto", "") for a in r["achados"]))
        cl = r["valores_semelhantes"][0]
        self.assertGreaterEqual(cl["n"], 4)
        self.assertGreaterEqual(cl["n_contrapartes"], 3)
        self.assertIn("200", cl["valor_fmt"])
        local = analise.responder_local(r, "há valores semelhantes de tráfico?")
        self.assertIn("200", local)

    def test_estelionato_destino_da_vitima_e_saque(self):
        inv, dinv = "INVESTIGADO GOLPE", util.formatar_documento(cpf(12))
        vit, dvit = "VITIMA FICTICIA", util.formatar_documento(cpf(13))
        corpo = CAB + "".join([
            linha("10/04/2026", "09:00", "PIX RECEBIDO", "4.500,00", "C", inv, dinv, "BANCO FICTICIO", "0001",
                  "8888-0", vit, dvit),
            linha("10/04/2026", "09:40", "SAQUE EM ESPECIE", "1.500,00", "D", inv, dinv, "BANCO FICTICIO", "0001",
                  "8888-0", "", ""),
            linha("10/04/2026", "10:05", "PIX ENVIADO", "3.000,00", "D", inv, dinv, "BANCO FICTICIO", "0001",
                  "8888-0", "TERCEIRO FICTICIO", util.formatar_documento(cpf(14))),
            linha("11/04/2026", "08:00", "TARIFA PACOTE", "20,00", "D", inv, dinv, "BANCO FICTICIO", "0001",
                  "8888-0", "", ""),
        ])
        self._importar_csv("golpe_ficticio.csv", corpo)
        r = analise.analisar(self.app.b, self.caso, self.usuario, {}, "estelionato",
                             "%s %s" % (vit, dvit), "%s %s" % (inv, dinv))
        self.assertEqual(r["hipotese_crime"], "estelionato")
        dest = [a for a in r["achados"] if a["tipo"] == "destino_vitima"]
        self.assertTrue(dest, r["achados"])
        self.assertGreaterEqual(dest[0]["metricas"]["n_entradas"], 1)
        self.assertGreaterEqual(dest[0]["metricas"]["n_saidas"], 1)
        cats = {d["categoria"] for d in r["rastreio_vitimas"][0]["destinos"]}
        self.assertIn("saque", cats)
        self.assertIn("pix", cats)
        uso = r["uso_contas"][0]
        self.assertGreaterEqual(uso["n_saques"], 1)
        texto = analise.responder_local(r, "para onde foi o dinheiro da vítima?")
        self.assertTrue("VITIMA" in texto.upper() or "vítima" in texto.lower() or "saque" in texto.lower())

    def test_uso_efetivo_cartao_e_compras(self):
        t, d = "TITULAR COMUM", util.formatar_documento(cpf(15))
        corpo = CAB + "".join([
            linha("01/05/2026", "08:00", "PIX RECEBIDO", "800,00", "C", t, d, "BANCO FICTICIO", "0001", "7777-0",
                  "SALARIO FICTICIO", util.formatar_documento(cpf(16))),
            linha("02/05/2026", "12:00", "COMPRA CARTAO MASTERCARD SUPERMERCADO", "120,00", "D", t, d,
                  "BANCO FICTICIO", "0001", "7777-0", "", ""),
            linha("03/05/2026", "18:00", "PAGAMENTO BOLETO CONTA DE LUZ", "90,00", "D", t, d, "BANCO FICTICIO",
                  "0001", "7777-0", "", ""),
            linha("04/05/2026", "09:00", "SAQUE ATM", "50,00", "D", t, d, "BANCO FICTICIO", "0001", "7777-0", "", ""),
        ])
        self._importar_csv("uso_ficticio.csv", corpo)
        r = analise.analisar(self.app.b, self.caso, self.usuario, {}, "outro", "", t)
        uso = r["uso_contas"][0]
        self.assertIn("uso efetivo", uso["perfil"])
        self.assertGreaterEqual(uso["n_cartao"] + uso["n_saques"], 2)
        tipos = {a["tipo"] for a in r["achados"]}
        self.assertIn("uso_conta", tipos)

    def test_bo_detecta_estelionato_e_vitima(self):
        t, d = "ALVO FICTICIO", util.formatar_documento(cpf(17))
        vit, dv = "OFENDIDA FICTICIA", util.formatar_documento(cpf(18))
        corpo = CAB + linha("20/06/2026", "11:00", "PIX RECEBIDO", "900,00", "C", t, d, "BANCO FICTICIO", "0001",
                            "6666-0", vit, dv)
        self._importar_csv("bo_extrato.csv", corpo)
        fid = self.app.b.x(
            "INSERT INTO fontes(caso_id, nome_original, arquivo_guardado, sha256, tamanho, tipo, papel, criado_em, criado_por) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (self.caso, "BO_FICTICIO.pdf", "x", "ab" * 32, 10, "pdf", "boletim", util.agora_iso(), self.usuario))
        texto = ("BOLETIM DE OCORRÊNCIA\nNatureza: ESTELIONATO\nVítima: %s\nCPF da vítima: %s\n"
                 "Investigado: %s" % (vit, dv, t))
        self.app.b.x("INSERT INTO paginas(caso_id, fonte_id, pagina, texto, metodo) VALUES (?,?,1,?,'texto')",
                     (self.caso, fid, texto))
        r = analise.analisar(self.app.b, self.caso, self.usuario, {}, "auto", "", "")
        self.assertIn("estelionato", r["hipoteses_detectadas"])
        self.assertTrue(any(v.get("doc_norm") == cpf(18) or (v.get("nome_norm") or "").find("OFENDIDA") >= 0
                            for v in r["vitimas"]), r["vitimas"])
        dest = [a for a in r["achados"] if a["tipo"] == "destino_vitima"]
        self.assertTrue(dest)

    def test_chat_local_sem_ollama(self):
        self._importar_csv("chat.csv", CAB + linha(
            "01/07/2026", "10:00", "PIX RECEBIDO", "100,00", "C", "A FICTICIO", util.formatar_documento(cpf(19)),
            "BANCO FICTICIO", "0001", "1111-0", "B FICTICIO", util.formatar_documento(cpf(21))))
        r = ia.conversar(self.app.b, self.caso, self.usuario, "faça a análise preliminar", modelo=None)
        self.assertEqual(r["modo"], "local")
        self.assertIn("preliminar", r["resposta"].lower())
        self.assertTrue(r["conversa_id"])
        self.assertGreaterEqual(len(r["historico"]), 2)
        ctx = analise.contexto(self.app.b, self.caso)
        self.assertTrue(ctx["analise"])

    def test_grafo_filtros_max_nos_e_volume(self):
        inv, dinv = "NO GRAFO", util.formatar_documento(cpf(22))
        corpo = CAB + "".join([
            linha("01/08/2026", "10:00", "PIX RECEBIDO", "50,00", "C", inv, dinv, "BANCO FICTICIO", "0001", "2222-0",
                  "PEQUENO", util.formatar_documento(cpf(23))),
            linha("02/08/2026", "10:00", "PIX RECEBIDO", "5.000,00", "C", inv, dinv, "BANCO FICTICIO", "0001", "2222-0",
                  "GRANDE", util.formatar_documento(cpf(24))),
        ])
        self._importar_csv("grafo.csv", corpo)
        g = grafo.grafo(self.app.b, self.caso, {}, max_nos=80, min_volume=100000)
        self.assertTrue(g["arestas"])
        self.assertTrue(all(a["valor"] >= 100000 for a in g["arestas"]))
        g2 = grafo.grafo(self.app.b, self.caso, {"texto": "grande"}, max_nos=10)
        self.assertTrue(g2["nos"])

    def test_modelos_sem_ollama_nao_quebra(self):
        import os
        os.environ["ANALISE_OLLAMA_PORTA"] = "9"
        try:
            m = ia.modelos()
            self.assertEqual(m["modelos"], [])
            self.assertFalse(m.get("disponivel"))
            self.assertTrue(m.get("erro"))
        finally:
            os.environ.pop("ANALISE_OLLAMA_PORTA", None)

    def test_papel_da_fonte(self):
        f = self.fonte_bytes("doc.txt", b"x")
        r = analise.definir_papel_fonte(self.app.b, f["id"], "boletim", self.usuario)
        self.assertEqual(r["papel"], "boletim")
        with self.assertRaises(ValueError):
            analise.definir_papel_fonte(self.app.b, f["id"], "invalido", self.usuario)


if __name__ == "__main__":
    unittest.main()
