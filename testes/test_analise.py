import os
import unittest
import zipfile
import io

from base import CasoTeste, cpf, exemplo
from financeira import auditoria, conciliacao, grafo, pesquisa, relatorio, rif, util


def importar_dois_extratos(t):
    t.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"))
    t.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato_conta_beta.csv"),
                      ajuste={"credito": "Credito", "debito": "Debito", "cp_nome": "Favorecido", "cp_doc": "CPF_CNPJ_Favorecido",
                              "descricao": "Historico"})


class TestPesquisa(CasoTeste):
    def test_facetas_listam_todas_as_opcoes(self):
        importar_dois_extratos(self)
        facs = {f["chave"]: f for f in pesquisa.facetas(self.app.b, self.caso, {})}
        docs = {v["valor"] for v in facs["pessoa_doc"]["valores"]}
        self.assertEqual(docs, {cpf(1), cpf(2), cpf(3), cpf(4), cpf(5)})
        nomes = {v["rotulo"] for v in facs["cp_nome"]["valores"]}
        self.assertIn("PESSOA BETA", nomes)
        self.assertEqual({v["valor"] for v in facs["banco"]["valores"]}, {"BANCO FICTICIO", "BANCO EXEMPLO"})
        self.assertIn("alfa@exemplo.invalid", {v["valor"] for v in facs["pix"]["valores"]})
        self.assertEqual({v["valor"] for v in facs["mes"]["valores"]}, {"2026-03"})

    def test_selecao_multipla_e_contagens(self):
        importar_dois_extratos(self)
        f = {"cp_doc": [cpf(2), cpf(3)]}
        t = pesquisa.totais(self.app.b, self.caso, f)
        self.assertEqual((t["creditos"], t["n_creditos"]), (100000, 2))
        f = {"pessoa_doc": [cpf(4)], "natureza": ["D"]}
        t = pesquisa.totais(self.app.b, self.caso, f)
        self.assertEqual(t["debitos"], 45000 + 38000)
        facs = {x["chave"]: x for x in pesquisa.facetas(self.app.b, self.caso, {"natureza": ["C"]})}
        self.assertEqual({v["valor"]: v["n"] for v in facs["natureza"]["valores"]}["D"], 4, "faceta ignora o próprio filtro")

    def test_filtro_texto_periodo_valor(self):
        importar_dois_extratos(self)
        t = pesquisa.totais(self.app.b, self.caso, {"data_ini": "2026-03-06", "data_fim": "2026-03-06"})
        self.assertEqual((t["creditos"], t["debitos"]), (30000, 30000))
        t = pesquisa.totais(self.app.b, self.caso, {"valor_min": "300,00"})
        self.assertEqual(t["n_registros"], 4)
        r = pesquisa.registros(self.app.b, self.caso, {"texto": "gama"})
        self.assertEqual(r["total"], 1)

    def test_exportacao_csv(self):
        importar_dois_extratos(self)
        csv = pesquisa.exportar_csv(self.app.b, self.caso, {"natureza": ["D"]})
        self.assertIn("sha256", csv.splitlines()[0])
        self.assertEqual(len(csv.strip().splitlines()), 1 + 4)

    def test_pesquisa_geral_todos_documentos(self):
        importar_dois_extratos(self)
        self.importar_tabela(exemplo("EXEMPLO_FICTICIO_acessos_ip_geo.csv"), "acessos", ajuste={"data": "Data/Hora"})
        f = self.fonte(exemplo("EXEMPLO_FICTICIO_documento.pdf"))
        self.app.importar(f["id"], "pdf_texto", None, {}, self.usuario)
        facs = {x["tipo"]: x for x in pesquisa.facetas_identificadores(self.app.b, self.caso)}
        for tipo in ("cpf", "nome", "banco", "conta", "pix", "ip", "coordenada", "cidade", "dispositivo", "email", "data"):
            self.assertIn(tipo, facs, tipo)
        ip = [v for v in facs["ip"]["valores"] if v["v"] == "203.0.113.10"][0]
        self.assertEqual(ip["nf"], 2, "IP aparece no registro de acesso e no PDF")
        oc = pesquisa.ocorrencias(self.app.b, self.caso, [{"tipo": "cpf", "valor": cpf(1)}])
        origens = {o["origem"] for o in oc}
        self.assertTrue({"Extrato (lançamento)", "Extrato (origem/destino)", "Acesso / IP / geolocalização", "Texto de PDF"} <= origens, origens)


class TestGrafoESequencias(CasoTeste):
    def test_grafo(self):
        importar_dois_extratos(self)
        g = grafo.grafo(self.app.b, self.caso, {})
        self.assertIn("Não comprovam", g["aviso"])
        tipos = {n["tipo"] for n in g["nos"]}
        self.assertTrue({"conta", "contraparte"} <= tipos)
        self.assertTrue(any(l["tipo"].startswith("mesmo CPF") for l in g["ligacoes"]))

    def test_sequencia_com_hipotese(self):
        importar_dois_extratos(self)
        r = grafo.sequencias(self.app.b, self.caso, cpf(1), janela_dias=3)
        cadeias = [c for c in r["cadeias"] if len(c["elos"]) == 2]
        self.assertTrue(cadeias, r)
        c = cadeias[0]
        self.assertEqual([e["valor"] for e in c["elos"]], [30000, 28000])
        self.assertIn("POSSIBILIDADE", c["qualificacao"])
        self.assertIsNotNone(c["elos"][0]["registro_espelho_na_conta_destino"])
        r = grafo.sequencias(self.app.b, self.caso, cpf(1), janela_dias=0)
        self.assertFalse([c for c in r["cadeias"] if len(c["elos"]) == 2])


class TestConciliacao(CasoTeste):
    def test_decisao_exige_revisor_e_justificativa(self):
        self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"))
        with open(exemplo("EXEMPLO_FICTICIO_extrato.csv"), "rb") as fh:
            csv2 = fh.read().replace(b"TARIFA PACOTE", b"TARIFA")
        f = self.fonte_bytes("copia_aba.csv", csv2)
        p = self.app.previa(f["id"])
        self.app.importar(f["id"], "extrato", p["sugestoes"]["extrato"], {"linha_cabecalho": 1}, self.usuario)
        dups = conciliacao.listar(self.app.b, self.caso, "pendente")
        self.assertTrue(dups)
        alvo = [d for d in dups if d["criterio"] == "conteudo_identico"][0]
        auditoria.definir_permissao(self.app.b, self.caso, self.usuario, "leitor.x", "leitor")
        with self.assertRaises(auditoria.SemPermissao):
            conciliacao.decidir(self.app.b, alvo["id"], "mesma_operacao", "x", "leitor.x")
        with self.assertRaises(ValueError):
            conciliacao.decidir(self.app.b, alvo["id"], "mesma_operacao", "", self.usuario)
        antes = pesquisa.totais(self.app.b, self.caso, {})["creditos"]
        conciliacao.decidir(self.app.b, alvo["id"], "mesma_operacao", "mesmo arquivo exportado duas vezes", self.usuario)
        depois = pesquisa.totais(self.app.b, self.caso, {})["creditos"]
        self.assertEqual(antes - depois, alvo["b"]["valor_centavos"])
        conciliacao.decidir(self.app.b, alvo["id"], "distintas", "revisto", self.usuario)
        self.assertEqual(pesquisa.totais(self.app.b, self.caso, {})["creditos"], antes)
        acoes = [a["acao"] for a in self.app.b.q("SELECT acao FROM auditoria WHERE caso_id=?", (self.caso,))]
        self.assertEqual(acoes.count("duplicata_decisao"), 2)

    def test_dois_lados_nao_consolida(self):
        importar_dois_extratos(self)
        d = self.app.b.q1("SELECT id FROM duplicatas WHERE criterio='dois_lados'")
        with self.assertRaises(ValueError):
            conciliacao.decidir(self.app.b, d["id"], "mesma_operacao", "x", self.usuario)


class TestRif(CasoTeste):
    def test_rif_separado_de_extrato(self):
        f = self.fonte(exemplo("EXEMPLO_FICTICIO_rif.zip"))
        rel = self.app.importar(f["id"], "rif", None, {"numero_rif": "RIF-TESTE", "coluna_valor": "CampoA"}, self.usuario)
        self.assertEqual(rel["aceitos"], 0)
        self.assertTrue(rel.get("rif_id"))
        self.assertEqual(self.app.b.q1("SELECT COUNT(*) n FROM lancamentos")["n"], 0)
        r = rif.resumo(self.app.b, self.caso)[0]
        self.assertEqual((len(r["comunicacoes"]), len(r["envolvidos"]), len(r["ocorrencias"])), (1, 2, 1))
        self.assertEqual(r["comunicacoes"][0]["valor_centavos"], 100000)
        self.assertIn("não", r["restricao"].lower())

    def test_rif_varios_arquivos_mesmo_relatorio(self):
        rid = None
        with zipfile.ZipFile(exemplo("EXEMPLO_FICTICIO_rif.zip")) as z:
            for nome in z.namelist():
                f = self.fonte_bytes(os.path.basename(nome), z.read(nome))
                op = {"numero_rif": "RIF-PEDACOS", "coluna_valor": "CampoA"}
                if rid:
                    op["rif_id"] = rid
                rel = self.app.importar(f["id"], "rif", None, op, self.usuario)
                self.assertEqual(rel["aceitos"], 0)
                rid = rel["rif_id"]
                self.assertTrue(rid)
        rifs = rif.resumo(self.app.b, self.caso)
        self.assertEqual(len(rifs), 1)
        r = rifs[0]
        self.assertEqual((len(r["comunicacoes"]), len(r["envolvidos"]), len(r["ocorrencias"])), (1, 2, 1))
        self.assertEqual(r["comunicacoes"][0]["valor_centavos"], 100000)

    def test_rif_anexar_ao_ultimo(self):
        with zipfile.ZipFile(exemplo("EXEMPLO_FICTICIO_rif.zip")) as z:
            arquivos = [(os.path.basename(n), z.read(n)) for n in z.namelist()]
        f1 = self.fonte_bytes(arquivos[0][0], arquivos[0][1])
        rel1 = self.app.importar(f1["id"], "rif", None, {"numero_rif": "RIF-A"}, self.usuario)
        f2 = self.fonte_bytes(arquivos[1][0], arquivos[1][1])
        rel2 = self.app.importar(f2["id"], "rif", None, {"anexar_ao_ultimo": True}, self.usuario)
        self.assertEqual(rel1["rif_id"], rel2["rif_id"])
        self.assertEqual(len(rif.resumo(self.app.b, self.caso)), 1)
        self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"))
        r = rif.resumo(self.app.b, self.caso)[0]
        self.assertIn(cpf(1), [x["doc"] for x in r["envolvidos_com_movimentacao"]])
        oc = pesquisa.ocorrencias(self.app.b, self.caso, [{"tipo": "cpf", "valor": cpf(2)}])
        self.assertIn("RIF - envolvido", {o["origem"] for o in oc})


class TestRelatorio(CasoTeste):
    def test_formatos_e_memoria(self):
        importar_dois_extratos(self)
        filtros = {"natureza": ["C"]}
        html, _, _ = relatorio.gerar(self.app.b, self.caso, "html", filtros, "Observação fictícia", [], self.usuario, self.app.pasta)
        texto = html.decode()
        self.assertIn("reproduz", texto)
        self.assertIn(util.sha256_arquivo(exemplo("EXEMPLO_FICTICIO_extrato.csv")), texto)
        self.assertIn("Natureza: C", texto)
        docx, _, _ = relatorio.gerar(self.app.b, self.caso, "docx", filtros, "", [], self.usuario, self.app.pasta)
        with zipfile.ZipFile(io.BytesIO(docx)) as z:
            self.assertIn("Memória de cálculo", z.read("word/document.xml").decode())
        pdf, _, _ = relatorio.gerar(self.app.b, self.caso, "pdf", filtros, "", [], self.usuario, self.app.pasta)
        self.assertTrue(pdf.startswith(b"%PDF"))
        from financeira import leitores
        import os
        caminho = os.path.join(self.tmp, "r.pdf")
        with open(caminho, "wb") as fh:
            fh.write(pdf)
        paginas, _ = leitores.texto_pdf(caminho)
        self.assertIn("Créditos aceitos", "\n".join(paginas))


if __name__ == "__main__":
    unittest.main()
