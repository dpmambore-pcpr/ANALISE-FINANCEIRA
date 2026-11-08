# -*- coding: utf-8 -*-
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from base import CasoTeste
from financeira import conhecimento, gemini, ia, nuvem, servidor


ENVS = ("ANALISE_CHATGPT_CHAVE", "ANALISE_CLAUDE_CHAVE", "ANALISE_NUVEM_TESTE",
        "ANALISE_GEMINI_CHAVE", "ANALISE_OLLAMA_PORTA")


class FalsoNuvem(BaseHTTPRequestHandler):
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

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        bruto = self.rfile.read(n) if n else b""
        dados = json.loads(bruto.decode("utf-8")) if bruto else {}
        FalsoNuvem.recebido.append({"path": self.path, "dados": dados, "auth": self.headers.get("Authorization"),
                                    "xkey": self.headers.get("x-api-key")})
        if FalsoNuvem.falhar:
            self._json({"error": {"message": "chave invalida"}}, 403)
            return
        if "chat/completions" in self.path:
            self._json({"choices": [{"message": {"content": "resposta chatgpt ficticia"}}]})
            return
        if self.path.endswith("/messages") or "/messages" in self.path:
            self._json({"content": [{"type": "text", "text": "resposta claude ficticia"}]})
            return
        self._json({"error": {"message": "rota"}}, 404)


class TestNuvem(CasoTeste):
    def setUp(self):
        super().setUp()
        self._env = {k: os.environ.get(k) for k in ENVS}
        for k in ENVS:
            os.environ.pop(k, None)
        os.environ["ANALISE_OLLAMA_PORTA"] = "9"
        self.falso = None

    def tearDown(self):
        if self.falso:
            self.falso.shutdown()
            self.falso.server_close()
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDown()

    def _sobe(self):
        FalsoNuvem.recebido = []
        FalsoNuvem.falhar = False
        self.falso = ThreadingHTTPServer(("127.0.0.1", 0), FalsoNuvem)
        threading.Thread(target=self.falso.serve_forever, daemon=True).start()
        os.environ["ANALISE_NUVEM_TESTE"] = "1"
        return "http://127.0.0.1:%d/v1" % self.falso.server_address[1]

    def test_host_recusado(self):
        for url, hosts in (("http://api.openai.com/v1", ("api.openai.com",)),
                           ("https://evil.example/v1", ("api.openai.com",)),
                           ("https://api.openai.com.evil/v1", ("api.openai.com",))):
            with self.assertRaises(ia.ErroIA, msg=url):
                nuvem.validar_url(url, hosts)
        self.assertEqual(nuvem.validar_url("https://api.openai.com/v1", ("api.openai.com",)),
                         "https://api.openai.com/v1")
        self.assertEqual(nuvem.validar_url("https://api.anthropic.com/v1", ("api.anthropic.com",)),
                         "https://api.anthropic.com/v1")
        os.environ["ANALISE_NUVEM_TESTE"] = "1"
        self.assertEqual(nuvem.validar_url("http://127.0.0.1:9/v1", ("api.openai.com",)),
                         "http://127.0.0.1:9/v1")

    def test_salvar_nao_expoe_chave(self):
        st = nuvem.salvar(self.app.pasta, self.usuario, "chatgpt", chave="sk-segredo-xyz")
        self.assertNotIn("chave", st)
        self.assertNotIn("sk-segredo-xyz", json.dumps(st))
        self.assertTrue(st["configurado"])
        self.assertEqual(st["chave_mascarada"], "…-xyz")
        with open(os.path.join(self.app.pasta, "chatgpt.json"), encoding="utf-8") as f:
            self.assertIn("sk-segredo-xyz", f.read())
        m = ia.modelos(pasta=self.app.pasta)
        self.assertIn("gpt-4.1-mini", m["nuvem"]["chatgpt"]["modelos"])
        self.assertNotIn("gpt-4.1-mini", m["modelos"])

    def test_gemini_salva_sem_checkbox(self):
        st = gemini.salvar(self.app.pasta, self.usuario, chave="abc12345xyz")
        self.assertTrue(st["confirmado"])
        self.assertTrue(st["configurado"])

    def test_chatgpt_pergunta_e_ensina_local(self):
        ep = self._sobe()
        nuvem.salvar(self.app.pasta, self.usuario, "chatgpt", chave="sk-teste")
        # endpoint de teste: grava direto no json
        caminho = os.path.join(self.app.pasta, "chatgpt.json")
        with open(caminho, encoding="utf-8") as f:
            d = json.load(f)
        d["endpoint"] = ep
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(d, f)
        r = ia.perguntar(self.app.b, self.caso, self.usuario, "chatgpt:gpt-4.1-mini",
                         "quais pix existem?", pasta=self.app.pasta)
        self.assertEqual(r["resposta"], "resposta chatgpt ficticia")
        self.assertEqual(r["modo"], "chatgpt")
        self.assertTrue(FalsoNuvem.recebido)
        self.assertIn("Bearer sk-teste", FalsoNuvem.recebido[0]["auth"] or "")
        corr = self.app.b.q("SELECT * FROM ia_correcoes WHERE ativo=1")
        self.assertTrue(corr)
        self.assertIn("quais pix existem?", corr[0]["pergunta"])
        self.assertIn("chatgpt", corr[0]["observacao"])
        docs = conhecimento.listar(self.app.b, None)
        self.assertTrue(any(d["categoria"] == "exemplo_ia_paga" for d in docs))

    def test_claude_erro_nao_cai_no_local(self):
        ep = self._sobe()
        FalsoNuvem.falhar = True
        nuvem.salvar(self.app.pasta, self.usuario, "claude", chave="ant-teste")
        caminho = os.path.join(self.app.pasta, "claude.json")
        with open(caminho, encoding="utf-8") as f:
            d = json.load(f)
        d["endpoint"] = ep
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(d, f)
        with self.assertRaises(ia.ErroIA):
            ia.conversar(self.app.b, self.caso, self.usuario, "resumo", modelo="claude:claude-sonnet-4-5",
                         gerar_analise=False, pasta=self.app.pasta)

    def test_csp_sem_openai_no_navegador(self):
        self.app.b.fechar()
        http = servidor.criar_servidor(os.path.join(self.tmp, "dados"), 0)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        try:
            h = {"X-Usuario": self.usuario,
                 "Cookie": "sessao_%d=%s" % (http.server_address[1], http.chave),
                 "X-Requested-With": "analise"}
            r = urllib.request.Request("http://127.0.0.1:%d/" % http.server_address[1], headers=h)
            abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with abridor.open(r, timeout=20) as resp:
                csp = resp.headers["Content-Security-Policy"]
            self.assertIn("connect-src 'self'", csp)
            self.assertNotIn("openai", csp)
            self.assertNotIn("anthropic", csp)
        finally:
            http.shutdown()
            http.server_close()


if __name__ == "__main__":
    unittest.main()
