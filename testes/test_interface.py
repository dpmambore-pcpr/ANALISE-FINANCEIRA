"""Conferência da interface simplificada (HTML/CSS/JS e grafo com dados fictícios)."""

import os
import re
import unittest

from base import CasoTeste, RAIZ, exemplo
from financeira import VERSAO, grafo


WEB = os.path.join(RAIZ, "financeira", "web")


def _ler(nome):
    with open(os.path.join(WEB, nome), encoding="utf-8") as f:
        return f.read()


class TestInterfaceArquivos(unittest.TestCase):
    def test_versao(self):
        self.assertEqual(VERSAO, "3.4.4")

    def test_html_fluxo_simples(self):
        html = _ler("index.html")
        self.assertIn("1. Importar", html)
        self.assertIn("2. Movimentações", html)
        self.assertIn("3. Grafo", html)
        self.assertIn("4. Análise", html)
        self.assertIn('id="nav-mais"', html)
        self.assertIn("Clique para escolher o arquivo", html)
        self.assertIn("aistudio.google.com/apikey", html)
        self.assertIn("Salvar e testar", html)
        self.assertIn("Peça a chave à TI da unidade", html)
        self.assertIn("Boletim, relatório e outros documentos", html)
        self.assertIn('id="ia-doc-soltar"', html)
        self.assertIn('id="ia-doc-papel"', html)
        self.assertIn("O mapa monta sozinho", html)
        self.assertIn("Mercure", html)
        self.assertNotIn("Gerar grafo", html)

    def test_js_auto_grafo_e_analise(self):
        js = _ler("app.js")
        self.assertIn("async function gerarGrafo", js)
        self.assertIn("await gerarGrafo()", js)
        self.assertIn("async function gerarAnalise", js)
        self.assertIn("else await gerarAnalise()", js)
        self.assertIn("htmlProximosPassos", js)
        self.assertIn('abrirAba("pesquisar")', js)
        self.assertIn("ligarSoltar", js)
        self.assertIn("aoVivo", js)
        self.assertIn("Pode marcar várias. Cada caixa já aplica.", js)
        self.assertIn("agendarGrafo", js)
        self.assertIn("ligarGrafoInterativo", js)
        self.assertIn("aresta-alca", js)
        self.assertIn('markerUnits="userSpaceOnUse"', js)
        self.assertNotIn("function ligarPanZoom", js)
        self.assertIn("Este programa está desatualizado", js)
        self.assertIn("verificarAtualizacao(false)", js)
        self.assertIn("enviarDocsAnalise", js)
        self.assertIn("/api/casos/${exigirCaso()}/docs-analise", js)
        self.assertNotIn("atu-auto", js)
        self.assertNotIn('id="atu-auto"', _ler("index.html"))

    def test_css_grafo_escuro(self):
        css = _ler("estilo.css")
        self.assertIn(".grafo-viewport", css)
        self.assertIn("#0b1424", css)
        self.assertIn(".vazio-grafo", css)
        self.assertIn("ol.passos", css)
        self.assertIn(".aresta-alca", css)
        self.assertIn(".no-grafo", css)


class TestGrafoAposImportar(CasoTeste):
    def test_grafo_tem_nos_e_arestas_no_exemplo(self):
        self.importar_tabela(exemplo("EXEMPLO_FICTICIO_extrato.csv"))
        g = grafo.grafo(self.app.b, self.caso, {})
        self.assertTrue(g["nos"], g)
        self.assertTrue(g["arestas"], g)
        tipos = {n["tipo"] for n in g["nos"]}
        self.assertIn("conta", tipos)
        self.assertTrue(any(a.get("valor") for a in g["arestas"]))
        self.assertTrue(re.search(r"Não comprovam", g["aviso"]))
