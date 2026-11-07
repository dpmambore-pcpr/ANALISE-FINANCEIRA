import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from base import CasoTeste, exemplo
from financeira import conhecimento, ia, servidor


class FalsoOllama(BaseHTTPRequestHandler):
    recebido = []

    def log_message(self, *a):
        pass

    def _json(self, obj):
        corpo = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/api/tags":
            self._json({"models": [{"name": "local:1b"}, {"name": "gpt-oss:120b-cloud"}, {"name": "x", "remote_host": "https://ollama.com"}]})
        else:
            self._json({"version": "0.0-teste"})

    def do_POST(self):
        dados = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FalsoOllama.recebido.append(dados)
        self._json({"message": {"content": "resposta fictícia"}})


class TestIA(CasoTeste):
    def setUp(self):
        super().setUp()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), FalsoOllama)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        os.environ["ANALISE_OLLAMA_PORTA"] = str(self.srv.server_address[1])

    def tearDown(self):
        self.srv.shutdown()
        os.environ.pop("ANALISE_OLLAMA_PORTA", None)
        super().tearDown()

    def test_somente_localhost(self):
        for url in ("http://localhost:11434/api", "http://10.0.0.1:11434/", "https://127.0.0.1:11434/", "http://ollama.com/",
                    "http://user:x@127.0.0.1:1/"):
            with self.assertRaises(ia.ErroIA, msg=url):
                ia.validar_url(url)
        self.assertEqual(ia.validar_url("http://127.0.0.1:11434/api/tags"), "http://127.0.0.1:11434/api/tags")

    def test_modelos_nuvem_bloqueados(self):
        m = ia.modelos()
        self.assertEqual(m["modelos"], ["local:1b"])
        self.assertEqual(len(m["bloqueados_nuvem"]), 2)
        with self.assertRaises(ia.ErroIA):
            ia.perguntar(self.app.b, self.caso, self.usuario, "gpt-oss:120b-cloud", "x", {})

    def test_contexto_com_totais_fontes_e_conhecimento(self):
        self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"))
        conhecimento.adicionar(self.app.b, "Glossário fictício", "Tarifa pacote é cobrança mensal de serviços bancários.\n\nOutro parágrafo.",
                               usuario=self.usuario)
        conhecimento.adicionar_correcao(self.app.b, self.caso, "quais tarifas existem?", "Liste tarifas com fonte e linha.", "", self.usuario)
        FalsoOllama.recebido.clear()
        r = ia.perguntar(self.app.b, self.caso, self.usuario, "local:1b", "Quais tarifas existem?", {})
        self.assertEqual(r["resposta"], "resposta fictícia")
        enviado = FalsoOllama.recebido[0]["messages"][1]["content"]
        self.assertIn("créditos R$ 1.000,00", enviado)
        self.assertIn("EXEMPLO_FICTICIO_extrato.csv", enviado)
        self.assertIn("Glossário fictício", enviado)
        self.assertIn("Liste tarifas com fonte e linha.", enviado)
        self.assertEqual(r["referencias"][0]["titulo"], "Glossário fictício")
        self.assertEqual(FalsoOllama.recebido[0]["options"]["temperature"], 0.1)
        self.assertTrue(self.app.b.q1("SELECT * FROM auditoria WHERE acao='pergunta_ia'"))

    def test_modelfile(self):
        mf = conhecimento.modelfile("qwen3:4b", "regras")
        self.assertTrue(mf.startswith("FROM qwen3:4b"))
        with self.assertRaises(ValueError):
            conhecimento.modelfile("x; rm -rf /", "r")


class TestServidor(CasoTeste):
    def setUp(self):
        super().setUp()
        self.app.b.fechar()
        self.srv = servidor.criar_servidor(os.path.join(self.tmp, "dados"), 0)
        self.app = self.srv.app
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.srv.server_address[1]
        self.cookie = "sessao_%d=%s" % (self.srv.server_address[1], self.srv.chave)

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def req(self, caminho, corpo=None, cookie=True, host=None, xrw=True, cab=None, bruto=None):
        h = {"X-Usuario": self.usuario}
        if cookie:
            h["Cookie"] = self.cookie
        if host:
            h["Host"] = host
        if xrw:
            h["X-Requested-With"] = "analise"
        h.update(cab or {})
        dados = bruto if bruto is not None else (json.dumps(corpo).encode() if corpo is not None else None)
        r = urllib.request.Request(self.base + caminho, data=dados, headers=h, method="POST" if dados is not None else "GET")
        abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with abridor.open(r, timeout=20) as resp:
                return resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def test_seguranca(self):
        self.assertEqual(self.req("/api/casos", cookie=False)[0], 403)
        self.assertEqual(self.req("/api/casos", host="evil.example:80")[0], 403)
        self.assertEqual(self.req("/api/casos", {"nome": "x"}, xrw=False)[0], 403)
        st, _, cab = self.req("/")
        self.assertEqual(st, 200)
        self.assertIn("default-src 'self'", cab["Content-Security-Policy"])
        self.assertEqual(self.req("/../../etc/passwd")[0], 404)
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")
        st, corpo, cab = self.req("/?chave=chave-errada-de-outra-sessao")
        self.assertEqual(st, 403)
        self.assertIn(b"janela", corpo.lower())
        self.assertIn("text/html", cab["Content-Type"])

    def test_chave_de_sessao_sobrevive_a_reabrir(self):
        pasta = os.path.join(self.tmp, "dados")
        a = servidor.criar_servidor(pasta, 0)
        b = servidor.criar_servidor(pasta, 0)
        try:
            self.assertEqual(a.chave, b.chave)
            self.assertTrue(os.path.isfile(os.path.join(pasta, "sessao.json")))
        finally:
            a.server_close()
            b.server_close()

    def test_fluxo_completo_por_http(self):
        with open(exemplo("EXEMPLO_FICTICIO_extrato.csv"), "rb") as f:
            st, corpo, _ = self.req("/api/casos/%d/upload" % self.caso, bruto=f.read(), cab={"X-Nome-Arquivo": "extrato.csv"})
        self.assertEqual(st, 200, corpo)
        fonte = json.loads(corpo)
        st, corpo, _ = self.req("/api/fontes/%d/previa" % fonte["id"], {})
        p = json.loads(corpo)
        st, corpo, _ = self.req("/api/fontes/%d/importar" % fonte["id"], {"adaptador": "extrato", "mapeamento": p["sugestoes"]["extrato"],
                                                                          "opcoes": {"linha_cabecalho": 1}})
        tid = json.loads(corpo)["tarefa"]
        for _ in range(100):
            t = json.loads(self.req("/api/tarefas/" + tid)[1])
            if t["estado"] != "executando":
                break
            threading.Event().wait(0.1)
        self.assertEqual(t["estado"], "concluida", t)
        st, corpo, _ = self.req("/api/casos/%d/pesquisa" % self.caso, {"filtros": {"natureza": ["C"]}})
        r = json.loads(corpo)
        self.assertEqual(r["totais"]["creditos_fmt"], "R$ 1.000,00")
        st, corpo, _ = self.req("/api/casos/%d/facetas" % self.caso, {"filtros": {}})
        self.assertIn("pessoa_doc", [f["chave"] for f in json.loads(corpo)])
        st, corpo, cab = self.req("/api/casos/%d/relatorio" % self.caso, {"formato": "docx", "filtros": {}})
        self.assertEqual(st, 200)
        self.assertTrue(corpo.startswith(b"PK"))
        st, _, _ = self.req("/api/casos/%d/fontes" % self.caso, cab={"X-Usuario": "intruso"})
        self.assertEqual(st, 403)
        st, corpo, _ = self.req("/api/casos/%d/ia" % self.caso, {"pergunta": "resumo preliminar", "gerar_analise": True})
        self.assertEqual(st, 200, corpo)
        tid = json.loads(corpo)["tarefa"]
        for _ in range(100):
            t = json.loads(self.req("/api/tarefas/" + tid)[1])
            if t["estado"] != "executando":
                break
            threading.Event().wait(0.1)
        self.assertEqual(t["estado"], "concluida", t)
        self.assertEqual(t["resultado"]["modo"], "local")
        self.assertIn("preliminar", t["resultado"]["resposta"].lower())

    def _esperar_tarefa(self, tid):
        t = None
        for _ in range(100):
            t = json.loads(self.req("/api/tarefas/" + tid)[1])
            if t["estado"] != "executando":
                break
            threading.Event().wait(0.1)
        return t

    def test_anexar_documento_analise_http(self):
        texto = "BOLETIM FICTICIO\nVítima: ANA TESTE\n".encode("utf-8")
        st, corpo, _ = self.req("/api/casos/%d/docs-analise" % self.caso, bruto=texto,
                                cab={"X-Nome-Arquivo": "bo.txt", "X-Papel": "boletim"})
        self.assertEqual(st, 200, corpo)
        t = self._esperar_tarefa(json.loads(corpo)["tarefa"])
        self.assertEqual(t["estado"], "concluida", t)
        self.assertEqual(t["resultado"]["fonte"]["papel"], "boletim")
        self.assertEqual(t["resultado"]["relatorio"]["paginas"], 1)
        st, corpo, _ = self.req("/api/casos/%d/docs-analise" % self.caso, bruto=b"x",
                                cab={"X-Nome-Arquivo": "planilha.xlsx", "X-Papel": "boletim"})
        self.assertEqual(st, 400, corpo)
        self.assertIn(b"PDF", corpo)

    def test_aviso_de_atualizacao(self):
        class Falso:
            def verificar_atualizacao(self):
                return {"instalada": "3.1.0", "disponivel": "3.2.0", "ha_nova": True, "ramo": "main"}

        class Offline:
            def verificar_atualizacao(self):
                raise OSError("sem rede")

        orig, cfg = servidor._atualizador, servidor.CONFIG_LOCAL
        servidor.CONFIG_LOCAL = os.path.join(self.tmp, "configuracao_local.json")
        try:
            servidor._atualizador = lambda: Falso()
            st, corpo, _ = self.req("/api/atualizacao/verificar")
            self.assertTrue(json.loads(corpo)["ha_nova"])
            servidor._atualizador = lambda: Offline()
            st, corpo, _ = self.req("/api/atualizacao/verificar")
            r = json.loads(corpo)
            self.assertFalse(r["ha_nova"])
            self.assertIn("erro", r)
            self.assertTrue(json.loads(self.req("/api/atualizacao/config")[1])["automatica"])
            self.req("/api/atualizacao/config", {"automatica": False})
            self.assertFalse(json.loads(self.req("/api/atualizacao/config")[1])["automatica"])
            self.assertEqual(self.req("/api/atualizacao/aplicar", {}, xrw=False)[0], 403)
            chamados = []
            orig_re = servidor._agendar_reinicio
            servidor._agendar_reinicio = lambda pasta, porta: chamados.append((pasta, porta))
            try:
                st, corpo, _ = self.req("/api/atualizacao/reiniciar", {})
                self.assertEqual(st, 200, corpo)
                self.assertTrue(chamados)
            finally:
                servidor._agendar_reinicio = orig_re
        finally:
            servidor._atualizador, servidor.CONFIG_LOCAL = orig, cfg


if __name__ == "__main__":
    unittest.main()
