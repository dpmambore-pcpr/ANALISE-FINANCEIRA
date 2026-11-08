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
        self.assertEqual(VERSAO, "3.4.10")

    def test_html_fluxo_simples(self):
        html = _ler("index.html")
        self.assertIn("1. Importar", html)
        self.assertIn("2. Movimentações", html)
        self.assertIn("3. Grafo", html)
        self.assertIn("4. Análise", html)
        self.assertIn('id="nav-mais"', html)
        self.assertIn("Clique para escolher os arquivos", html)
        self.assertIn('id="imp-arquivo" multiple', html)
        self.assertIn('id="imp-fila"', html)
        self.assertIn("Enviar arquivos", html)
        self.assertIn("quebra de bancos", html)
        self.assertIn("btn-analisar-juntos", html)
        self.assertIn("estante-casos", html)
        self.assertIn("056-PCPR-000677-20", html)
        self.assertIn('id="valores-extrato"', html)
        self.assertIn('id="grafo-valores-lista"', html)
        self.assertIn("Valores das transferências", html)
        self.assertIn("Abrir no ChatGPT", html)
        self.assertIn("Abrir no Claude", html)
        self.assertIn("chatgpt.com", html)
        self.assertIn("não precisa de chave", html.lower())
        self.assertIn("aistudio.google.com/apikey", html)
        self.assertIn("platform.openai.com/api-keys", html)
        self.assertIn("console.anthropic.com", html)
        self.assertIn("Salvar e testar", html)
        self.assertIn("gemini-3.8-flash", html)
        self.assertIn("ia-aprender", html)
        self.assertIn("chatgpt-chave", html)
        self.assertIn("claude-chave", html)
        self.assertNotIn("Peça a chave à TI da unidade", html)
        self.assertNotIn("só se a TI pedir", html)
        self.assertIn("Boletim, relatório e outros documentos", html)
        self.assertIn('id="ia-doc-soltar"', html)
        self.assertIn('id="ia-doc-papel"', html)
        self.assertIn("O mapa monta sozinho", html)
        self.assertIn("Pirâmide", html)
        self.assertIn('id="btn-grafo-tela"', html)
        self.assertIn("Tela cheia", html)
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
        self.assertIn("layoutTorre", js)
        self.assertIn("layoutPiramide", js)
        self.assertIn("htmlOrgGrafo", js)
        self.assertIn("htmlLegendaGrafo", js)
        self.assertIn("ligarOrgGrafo", js)
        self.assertIn("data-layout=\"piramide\"", js)
        self.assertIn("data-layout=\"circular\"", js)
        self.assertIn("data-layout=\"torre\"", js)
        self.assertIn('id="gf-valores"', js)
        self.assertIn("grafo-legenda-btn", js)
        self.assertIn("alternarTelaCheia", js)
        self.assertIn("sairTelaCheia", js)
        self.assertIn("gz-tela", js)
        self.assertIn("pintarValoresExtrato", js)
        self.assertIn("abrirIANavegador", js)
        self.assertIn("/api/casos/${exigirCaso()}/ia/prompt", js)
        self.assertIn("salvarChaveIA", js)
        self.assertIn("chatgpt:", js)
        self.assertIn("claude:", js)
        self.assertIn("geomArestaReta", js)
        self.assertIn("listaArquivos", js)
        self.assertIn("opcoesRif", js)
        self.assertIn("rifLoteId", js)
        self.assertIn("filaImportacao", js)
        self.assertIn('markerUnits="userSpaceOnUse"', js)
        self.assertNotIn("aresta-alca", js)
        self.assertNotIn("function ligarPanZoom", js)
        self.assertIn("Este programa está desatualizado", js)
        self.assertIn("verificarAtualizacao(false)", js)
        self.assertIn("enviarDocsAnalise", js)
        self.assertIn("/api/casos/${exigirCaso()}/docs-analise", js)
        self.assertIn("perguntarDestinoArquivo", js)
        self.assertIn("/api/casos/reconhecer", js)
        self.assertIn("/api/casos/integrar", js)
        self.assertIn("escolherCaso", js)
        self.assertIn(".estante-casos", _ler("estilo.css"))
        self.assertNotIn("atu-auto", js)
        self.assertNotIn('id="atu-auto"', _ler("index.html"))

    def test_css_grafo_escuro(self):
        css = _ler("estilo.css")
        self.assertIn(".grafo-viewport", css)
        self.assertIn("#0b1424", css)
        self.assertIn(".vazio-grafo", css)
        self.assertIn("ol.passos", css)
        self.assertIn(".org-btn", css)
        self.assertIn(".grafo-org-in", css)
        self.assertIn(".grafo-viewport.tela-cheia", css)
        self.assertIn(".grafo-legenda.retraida", css)
        self.assertIn(".chaves-ia", css)
        self.assertIn(".lista-valores", css)
        self.assertIn(".valores-extrato", css)
        self.assertIn(".no-grafo", css)
        self.assertIn(".aresta.ativa", css)


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
