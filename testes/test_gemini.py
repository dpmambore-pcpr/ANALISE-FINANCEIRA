# -*- coding: utf-8 -*-
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from base import CasoTeste, exemplo
from financeira import gemini, ia, servidor


ENVS = ("ANALISE_GEMINI_CHAVE", "ANALISE_GEMINI_ENDPOINT", "ANALISE_GEMINI_MODELO", "ANALISE_GEMINI_TESTE",
        "ANALISE_OLLAMA_PORTA")


class FalsoGemini(BaseHTTPRequestHandler):
    recebido = []
    falhar = False

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        corpo = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if "/models" in self.path.split("?")[0] and "generateContent" not in self.path:
            self._json({"models": [
                {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/outro", "supportedGenerationMethods": ["embedContent"]},
            ]})
            return
        self._json({"error": {"message": "nao"}}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        bruto = self.rfile.read(n) if n else b""
        dados = json.loads(bruto.decode("utf-8")) if bruto else {}
        FalsoGemini.recebido.append({"path": self.path, "dados": dados})
        if FalsoGemini.falhar:
            self._json({"error": {"message": "chave invalida"}}, 403)
            return
        if "generateContent" in self.path:
            self._json({"candidates": [{"content": {"parts": [{"text": "resposta gemini ficticia"}]}}]})
            return
        self._json({"error": {"message": "rota"}}, 404)


class TestGemini(CasoTeste):
    def setUp(self):
        super().setUp()
        self._env = {k: os.environ.get(k) for k in ENVS}
        for k in ENVS:
            os.environ.pop(k, None)
        os.environ["ANALISE_OLLAMA_PORTA"] = "9"
        self.srv = None

    def tearDown(self):
        if self.srv:
            self.srv.shutdown()
            self.srv.server_close()
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDown()

    def _falso(self):
        FalsoGemini.recebido = []
        FalsoGemini.falhar = False
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), FalsoGemini)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        porta = self.srv.server_address[1]
        os.environ["ANALISE_GEMINI_TESTE"] = "1"
        os.environ["ANALISE_GEMINI_CHAVE"] = "teste-chave-gemini"
        os.environ["ANALISE_GEMINI_ENDPOINT"] = "http://127.0.0.1:%d/v1beta" % porta
        return porta

    def test_url_so_google_ou_localhost_de_teste(self):
        self.assertEqual(gemini.validar_url("https://generativelanguage.googleapis.com/v1beta"),
                         "https://generativelanguage.googleapis.com/v1beta")
        self.assertEqual(gemini.validar_url("https://us-central1-aiplatform.googleapis.com/v1"),
                         "https://us-central1-aiplatform.googleapis.com/v1")
        for url in ("http://generativelanguage.googleapis.com/v1beta",
                    "https://example.com/v1beta",
                    "https://evil.com/",
                    "http://127.0.0.1:9/v1beta",
                    "https://user:x@generativelanguage.googleapis.com/v1"):
            with self.assertRaises(ia.ErroIA, msg=url):
                gemini.validar_url(url)
        os.environ["ANALISE_GEMINI_TESTE"] = "1"
        self.assertEqual(gemini.validar_url("http://127.0.0.1:9/v1beta"), "http://127.0.0.1:9/v1beta")

    def test_salvar_exige_confirmacao_e_nao_expoe_chave(self):
        with self.assertRaises(ia.ErroIA):
            gemini.salvar(self.app.pasta, self.usuario, chave="abc12345xyz", confirmado=False)
        st = gemini.salvar(self.app.pasta, self.usuario, chave="abc12345xyz", confirmado=True, modelo="gemini-2.5-flash")
        self.assertNotIn("chave", st)
        self.assertNotIn("abc12345xyz", json.dumps(st))
        self.assertTrue(st["configurado"])
        self.assertTrue(st["confirmado"])
        self.assertEqual(st["chave_mascarada"], "…5xyz")
        with open(os.path.join(self.app.pasta, "gemini.json"), encoding="utf-8") as f:
            self.assertIn("abc12345xyz", f.read())

    def test_modelos_separa_gemini_do_ollama(self):
        gemini.salvar(self.app.pasta, self.usuario, chave="abc12345xyz", confirmado=True)
        m = ia.modelos(pasta=self.app.pasta)
        self.assertNotIn("gemini-2.5-flash", m["modelos"])
        self.assertIn("gemini-2.5-flash", m["gemini"]["modelos"])
        self.assertTrue(m["gemini"]["configurado"])

    def test_perguntar_envia_ao_gemini_e_audita(self):
        self._falso()
        self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"))
        r = ia.perguntar(self.app.b, self.caso, self.usuario, "gemini:gemini-2.5-flash",
                         "Qual o total de créditos?", {}, pasta=self.app.pasta)
        self.assertEqual(r["resposta"], "resposta gemini ficticia")
        self.assertEqual(r["modo"], "gemini")
        self.assertIn("saíram deste computador", r["aviso"])
        self.assertTrue(FalsoGemini.recebido)
        enviado = json.dumps(FalsoGemini.recebido[0]["dados"], ensure_ascii=False)
        self.assertIn("créditos", enviado.lower())
        self.assertNotIn("teste-chave-gemini", enviado)
        aud = self.app.b.q1("SELECT * FROM auditoria WHERE acao='pergunta_ia' ORDER BY id DESC")
        self.assertIn("gemini", aud["detalhes_json"])
        self.assertNotIn("teste-chave-gemini", aud["detalhes_json"])

    def test_conversar_gemini_com_erro_nao_cai_no_local(self):
        self._falso()
        FalsoGemini.falhar = True
        with self.assertRaises(ia.ErroIA) as ctx:
            ia.conversar(self.app.b, self.caso, self.usuario, "resumo", modelo="gemini:gemini-2.5-flash",
                         pasta=self.app.pasta, gerar_analise=False)
        self.assertIn("recusou", str(ctx.exception).lower())

    def test_modelo_invalido(self):
        self._falso()
        with self.assertRaises(ia.ErroIA):
            gemini.gerar(self.app.pasta, "../etc/passwd", "s", [{"role": "user", "content": "x"}])
        with self.assertRaises(ia.ErroIA):
            gemini.gerar(self.app.pasta, "http://evil", "s", [{"role": "user", "content": "x"}])

    def test_endpoint_malicioso_recusado_ao_salvar(self):
        with self.assertRaises(ia.ErroIA):
            gemini.salvar(self.app.pasta, self.usuario, chave="abc12345xyz", confirmado=True,
                          endpoint="https://evil.example/v1")

    def test_listar_modelos_no_falso(self):
        self._falso()
        nomes = gemini.listar_modelos(self.app.pasta)
        self.assertEqual(nomes, ["gemini-2.5-flash"])


class TestGeminiHTTP(CasoTeste):
    def setUp(self):
        super().setUp()
        self._env = {k: os.environ.get(k) for k in ENVS}
        for k in ENVS:
            os.environ.pop(k, None)
        os.environ["ANALISE_OLLAMA_PORTA"] = "9"
        self.app.b.fechar()
        self.http = servidor.criar_servidor(os.path.join(self.tmp, "dados"), 0)
        self.app = self.http.app
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.http.server_address[1]
        self.cookie = "sessao_%d=%s" % (self.http.server_address[1], self.http.chave)
        self.falso = None

    def tearDown(self):
        if self.falso:
            self.falso.shutdown()
            self.falso.server_close()
        self.http.shutdown()
        self.http.server_close()
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDown()

    def req(self, caminho, corpo=None):
        h = {"X-Usuario": self.usuario, "Cookie": self.cookie, "X-Requested-With": "analise"}
        dados = json.dumps(corpo).encode() if corpo is not None else None
        if dados is not None:
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(self.base + caminho, data=dados, headers=h,
                                   method="POST" if dados is not None else "GET")
        abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with abridor.open(r, timeout=20) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_api_nao_devolve_chave(self):
        st, corpo = self.req("/api/ia/gemini", {"chave": "segredo-super-xyz", "confirmado": True})
        self.assertEqual(st, 200, corpo)
        self.assertNotIn("segredo-super-xyz", json.dumps(corpo))
        self.assertTrue(corpo["configurado"])
        st, corpo = self.req("/api/ia/gemini")
        self.assertEqual(st, 200)
        self.assertNotIn("chave", corpo)
        self.assertNotIn("segredo-super-xyz", json.dumps(corpo))
        st, estado = self.req("/api/estado")
        self.assertTrue(estado["gemini"]["configurado"])
        self.assertNotIn("segredo-super-xyz", json.dumps(estado))
        st, corpo = self.req("/api/ia/gemini", {"chave": "x", "confirmado": False})
        self.assertEqual(st, 400)
        st, modelos = self.req("/api/ia/modelos")
        self.assertEqual(st, 200)
        self.assertIn("gemini-2.5-flash", modelos["gemini"]["modelos"])
        st, _ = self.req("/api/ia/gemini", {"remover": True})
        self.assertEqual(st, 200)
        st, modelos = self.req("/api/ia/modelos")
        self.assertFalse(modelos["gemini"]["configurado"])
        self.assertEqual(modelos["gemini"]["modelos"], [])

    def test_csp_continua_sem_google_no_navegador(self):
        h = {"X-Usuario": self.usuario, "Cookie": self.cookie, "X-Requested-With": "analise"}
        r = urllib.request.Request(self.base + "/", headers=h)
        abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with abridor.open(r, timeout=20) as resp:
            st, cab = resp.status, resp.headers
        self.assertEqual(st, 200)
        csp = cab["Content-Security-Policy"]
        self.assertIn("connect-src 'self'", csp)
        self.assertNotIn("googleapis", csp)

    def test_chat_http_com_gemini_falso(self):
        FalsoGemini.recebido = []
        FalsoGemini.falhar = False
        self.falso = ThreadingHTTPServer(("127.0.0.1", 0), FalsoGemini)
        threading.Thread(target=self.falso.serve_forever, daemon=True).start()
        os.environ["ANALISE_GEMINI_TESTE"] = "1"
        os.environ["ANALISE_GEMINI_CHAVE"] = "teste-http"
        os.environ["ANALISE_GEMINI_ENDPOINT"] = "http://127.0.0.1:%d/v1beta" % self.falso.server_address[1]
        st, corpo = self.req("/api/casos/%d/ia" % self.caso, {
            "pergunta": "faça um resumo preliminar", "modelo": "gemini:gemini-2.5-flash", "gerar_analise": False,
        })
        self.assertEqual(st, 200, corpo)
        tid = corpo["tarefa"]
        for _ in range(100):
            st, t = self.req("/api/tarefas/" + tid)
            if t["estado"] != "executando":
                break
            threading.Event().wait(0.1)
        self.assertEqual(t["estado"], "concluida", t)
        self.assertEqual(t["resultado"]["modo"], "gemini")
        self.assertEqual(t["resultado"]["resposta"], "resposta gemini ficticia")
        self.assertTrue(FalsoGemini.recebido)


if __name__ == "__main__":
    unittest.main()
