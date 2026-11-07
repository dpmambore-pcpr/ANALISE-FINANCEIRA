"""Servidor web local. Escuta somente em 127.0.0.1 e exige a chave de sessão exibida no terminal."""

import argparse
import json
import mimetypes
import os
import re
import secrets
import shutil
import sys
import threading
import traceback
import urllib.parse
import webbrowser
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import (VERSAO, adaptadores, analise, auditoria, conciliacao, conhecimento, documentos, fontes, gemini, grafo, ia,
               pesquisa, relatorio, rif, servico, util)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
MAX_MB = int(os.environ.get("ANALISE_MAX_MB", "2048"))


class Tarefas:
    def __init__(self):
        self.itens = {}
        self.trava = threading.Lock()

    def iniciar(self, func, *args, **kwargs):
        tid = secrets.token_hex(8)
        with self.trava:
            self.itens[tid] = {"estado": "executando", "progresso": "iniciando", "resultado": None, "erro": None}

        def prog(n, msg=""):
            self.itens[tid]["progresso"] = msg or str(n)

        def rodar():
            try:
                kwargs_ = dict(kwargs)
                if "progresso" in func.__code__.co_varnames:
                    kwargs_["progresso"] = prog
                self.itens[tid]["resultado"] = func(*args, **kwargs_)
                self.itens[tid]["estado"] = "concluida"
            except Exception as e:  # noqa: BLE001
                self.itens[tid]["estado"] = "erro"
                self.itens[tid]["erro"] = str(e)
                traceback.print_exc()
        threading.Thread(target=rodar, daemon=True).start()
        return tid

    def obter(self, tid):
        return self.itens.get(tid)


ROTAS = []


def rota(metodo, padrao):
    def dec(f):
        ROTAS.append((metodo, re.compile("^" + padrao + "$"), f))
        return f
    return dec


class Manipulador(BaseHTTPRequestHandler):
    server_version = "AnaliseLocal"
    sys_version = ""

    def log_message(self, fmt, *args):
        if os.environ.get("ANALISE_LOG"):
            sys.stderr.write("%s\n" % (fmt % args))

    @property
    def app(self):
        return self.server.app

    # ---------------------------------------------------------------- utilidades
    def _host_ok(self):
        host = (self.headers.get("Host") or "").lower()
        porta = self.server.server_address[1]
        return host in ("127.0.0.1:%d" % porta, "localhost:%d" % porta)

    def _sessao_ok(self):
        c = cookies.SimpleCookie(self.headers.get("Cookie") or "")
        valor = c.get("sessao_%d" % self.server.server_address[1])
        return valor is not None and secrets.compare_digest(valor.value, self.server.chave)

    def _cabecalhos_seguranca(self):
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
                                                    "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")

    def enviar(self, codigo, corpo, tipo="application/json; charset=utf-8", extra=None):
        if isinstance(corpo, (dict, list)):
            corpo = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
        elif isinstance(corpo, str):
            corpo = corpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self._cabecalhos_seguranca()
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def erro(self, codigo, msg):
        self.enviar(codigo, {"erro": msg})

    def json_corpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 50 * 1024 * 1024:
            raise ValueError("requisição grande demais")
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}

    @property
    def usuario(self):
        u = urllib.parse.unquote(self.headers.get("X-Usuario") or "").strip()
        return u[:80] or None

    def ler_caso(self, caso_id):
        if auditoria.papel(self.app.b, int(caso_id), self.usuario) is None:
            raise auditoria.SemPermissao("Sem acesso a este caso.")
        return int(caso_id)

    def caso_da_fonte(self, fonte_id):
        f = self.app.fonte(fonte_id)
        self.ler_caso(f["caso_id"])
        return f

    # ---------------------------------------------------------------- despacho
    def _despachar(self, metodo):
        if not self._host_ok():
            return self.erro(403, "Host não permitido")
        partes = urllib.parse.urlsplit(self.path)
        caminho = partes.path
        consulta = urllib.parse.parse_qs(partes.query)
        if caminho == "/" and "chave" in consulta:
            if secrets.compare_digest(consulta["chave"][0], self.server.chave):
                self.send_response(303)
                self.send_header("Set-Cookie", "sessao_%d=%s; HttpOnly; SameSite=Strict; Path=/" % (self.server.server_address[1], self.server.chave))
                self.send_header("Location", "/")
                self._cabecalhos_seguranca()
                self.end_headers()
                return
            return self.erro(403, "Chave de sessão inválida")
        if not self._sessao_ok():
            return self.enviar(403, "<h3>Sessão inválida. Use o endereço completo exibido no terminal.</h3>", "text/html; charset=utf-8")
        if metodo == "POST" and self.headers.get("X-Requested-With") != "analise":
            return self.erro(403, "Requisição recusada")
        if not caminho.startswith("/api/"):
            return self._estatico(caminho)
        for m, padrao, func in ROTAS:
            if m != metodo:
                continue
            achou = padrao.match(caminho)
            if achou:
                try:
                    return func(self, consulta, *achou.groups())
                except auditoria.SemPermissao as e:
                    return self.erro(403, str(e))
                except fontes.FonteDuplicada as e:
                    return self.enviar(409, {"erro": str(e), "fonte": e.fonte})
                except (ValueError, KeyError, ia.ErroIA, IOError, RuntimeError) as e:
                    return self.erro(400, str(e))
                except Exception as e:  # noqa: BLE001
                    traceback.print_exc()
                    return self.erro(500, "Erro interno: %s" % e)
        return self.erro(404, "rota inexistente")

    def do_GET(self):
        self._despachar("GET")

    def do_POST(self):
        self._despachar("POST")

    def _estatico(self, caminho):
        nome = "index.html" if caminho in ("/", "") else caminho.lstrip("/")
        alvo = os.path.normpath(os.path.join(WEB, nome))
        if not alvo.startswith(WEB + os.sep) or not os.path.isfile(alvo):
            return self.erro(404, "não encontrado")
        tipo = mimetypes.guess_type(alvo)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo.endswith("javascript"):
            tipo += "; charset=utf-8"
        with open(alvo, "rb") as f:
            self.enviar(200, f.read(), tipo)


# ---------------------------------------------------------------- rotas: geral e casos

@rota("GET", r"/api/estado")
def r_estado(h, q):
    g = gemini.status(h.app.pasta)
    h.enviar(200, {"versao": VERSAO, "ocr": documentos.ocr_disponivel(), "ia_endereco": ia.url_base(),
                   "pasta_dados": h.app.pasta, "fts": h.app.b.fts,
                   "gemini": {"configurado": g["configurado"], "confirmado": g["confirmado"],
                              "chave_mascarada": g.get("chave_mascarada") or ""}})


@rota("GET", r"/api/casos")
def r_casos(h, q):
    h.enviar(200, h.app.casos(h.usuario))


@rota("POST", r"/api/casos")
def r_criar_caso(h, q):
    d = h.json_corpo()
    if not h.usuario:
        raise ValueError("Informe seu nome de usuário no topo da tela.")
    h.enviar(200, {"id": h.app.criar_caso(d.get("nome"), d.get("descricao"), h.usuario)})


@rota("POST", r"/api/casos/(\d+)/permissoes")
def r_perm(h, q, c):
    d = h.json_corpo()
    auditoria.definir_permissao(h.app.b, int(c), h.usuario, d["usuario"].strip(), d["papel"])
    h.enviar(200, {"ok": True})


@rota("GET", r"/api/casos/(\d+)/remessas")
def r_remessas(h, q, c):
    h.enviar(200, h.app.b.q("SELECT * FROM remessas WHERE caso_id=? ORDER BY id", (h.ler_caso(c),)))


@rota("POST", r"/api/casos/(\d+)/remessas")
def r_criar_remessa(h, q, c):
    d = h.json_corpo()
    h.enviar(200, {"id": h.app.criar_remessa(int(c), d.get("rotulo") or "Remessa", d.get("instituicao"), d.get("observacao"), h.usuario)})


@rota("GET", r"/api/casos/(\d+)/auditoria")
def r_auditoria(h, q, c):
    h.enviar(200, h.app.b.q("SELECT * FROM auditoria WHERE caso_id=? ORDER BY id DESC LIMIT 2000", (h.ler_caso(c),)))


# ---------------------------------------------------------------- fontes e importação

@rota("GET", r"/api/casos/(\d+)/fontes")
def r_fontes(h, q, c):
    h.enviar(200, h.app.listar_fontes(h.ler_caso(c)))


@rota("GET", r"/api/casos/(\d+)/integridade")
def r_integridade(h, q, c):
    h.enviar(200, h.app.conferir_fontes(h.ler_caso(c)))


@rota("POST", r"/api/casos/(\d+)/upload")
def r_upload(h, q, c):
    caso = int(c)
    auditoria.exigir(h.app.b, caso, h.usuario, "analista")
    nome = urllib.parse.unquote(h.headers.get("X-Nome-Arquivo") or "arquivo")
    remessa = h.headers.get("X-Remessa")
    n = int(h.headers.get("Content-Length") or 0)
    if n <= 0:
        raise ValueError("arquivo vazio")
    if n > MAX_MB * 1024 * 1024:
        raise ValueError("arquivo maior que %d MB (ajuste ANALISE_MAX_MB)" % MAX_MB)
    tmp = os.path.join(h.app.pasta, "tmp", "upload_%s" % secrets.token_hex(8))
    try:
        with open(tmp, "wb") as f:
            restante = n
            while restante:
                bloco = h.rfile.read(min(restante, 1024 * 1024))
                if not bloco:
                    break
                f.write(bloco)
                restante -= len(bloco)
        if restante:
            raise IOError("envio interrompido")
        fonte = h.app.receber_arquivo(caso, tmp, nome, h.usuario, int(remessa) if remessa and remessa.isdigit() else None)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    h.enviar(200, fonte)


@rota("GET", r"/api/fontes/(\d+)/zip")
def r_zip(h, q, f):
    h.caso_da_fonte(f)
    h.enviar(200, h.app.conteudo_zip(int(f)))


@rota("POST", r"/api/fontes/(\d+)/extrair")
def r_extrair(h, q, f):
    h.caso_da_fonte(f)
    d = h.json_corpo()
    h.enviar(200, h.app.extrair_membro(int(f), d["membro"], h.usuario))


@rota("POST", r"/api/fontes/(\d+)/previa")
def r_previa(h, q, f):
    h.caso_da_fonte(f)
    d = h.json_corpo()
    lc = d.get("linha_cabecalho")
    h.enviar(200, h.app.previa(int(f), d.get("aba"), int(lc) if lc else None))


@rota("POST", r"/api/fontes/(\d+)/importar")
def r_importar(h, q, f):
    fonte = h.caso_da_fonte(f)
    auditoria.exigir(h.app.b, fonte["caso_id"], h.usuario, "analista")
    d = h.json_corpo()
    tid = h.server.tarefas.iniciar(h.app.importar, int(f), d["adaptador"], d.get("mapeamento"), d.get("opcoes") or {}, h.usuario)
    h.enviar(200, {"tarefa": tid})


@rota("GET", r"/api/tarefas/(\w+)")
def r_tarefa(h, q, t):
    tarefa = h.server.tarefas.obter(t)
    if not tarefa:
        raise KeyError("tarefa inexistente")
    h.enviar(200, tarefa)


@rota("GET", r"/api/importacoes/(\d+)")
def r_imp(h, q, i):
    rel = h.app.relatorio_importacao(int(i))
    h.ler_caso(rel["caso_id"])
    h.enviar(200, rel)


@rota("POST", r"/api/importacoes/(\d+)/desfazer")
def r_desfazer(h, q, i):
    h.app.desfazer_importacao(int(i), h.usuario)
    h.enviar(200, {"ok": True})


@rota("GET", r"/api/perfis")
def r_perfis(h, q):
    aprendidos = h.app.b.q("SELECT id, nome, instituicao, adaptador, usos, criado_em, criado_por, mapeamento_json FROM perfis_mapeamento ORDER BY id DESC")
    h.enviar(200, {"aprendidos": aprendidos, "embutidos": adaptadores.perfis_embutidos()})


@rota("POST", r"/api/perfis/(\d+)/remover")
def r_perfil_rem(h, q, p):
    h.app.b.x("DELETE FROM perfis_mapeamento WHERE id=?", (int(p),))
    auditoria.registrar(h.app.b, None, h.usuario, "perfil_removido", {"perfil_id": int(p)})
    h.enviar(200, {"ok": True})


# ---------------------------------------------------------------- pesquisa

@rota("POST", r"/api/casos/(\d+)/facetas")
def r_facetas(h, q, c):
    h.enviar(200, pesquisa.facetas(h.app.b, h.ler_caso(c), h.json_corpo().get("filtros")))


@rota("POST", r"/api/casos/(\d+)/pesquisa")
def r_pesquisa(h, q, c):
    d = h.json_corpo()
    caso = h.ler_caso(c)
    res = pesquisa.registros(h.app.b, caso, d.get("filtros"), min(int(d.get("limite") or 500), 2000),
                             int(d.get("deslocamento") or 0), d.get("ordem") or "data")
    res["totais"] = pesquisa.totais(h.app.b, caso, d.get("filtros"))
    res["filtros_descricao"] = pesquisa.descrever_filtros(h.app.b, d.get("filtros"))
    h.enviar(200, res)


@rota("GET", r"/api/lancamentos/(\d+)")
def r_lanc(h, q, i):
    d = pesquisa.detalhe(h.app.b, int(i))
    if not d:
        raise KeyError("lançamento inexistente")
    h.ler_caso(d["caso_id"])
    h.enviar(200, d)


@rota("POST", r"/api/casos/(\d+)/exportar")
def r_exportar(h, q, c):
    caso = h.ler_caso(c)
    d = h.json_corpo()
    auditoria.registrar(h.app.b, caso, h.usuario, "exportacao_csv", {"filtros": d.get("filtros")})
    h.enviar(200, pesquisa.exportar_csv(h.app.b, caso, d.get("filtros")), "text/csv; charset=utf-8",
             {"Content-Disposition": 'attachment; filename="pesquisa_caso_%d.csv"' % caso})


@rota("POST", r"/api/casos/(\d+)/identificadores")
def r_ident(h, q, c):
    d = h.json_corpo()
    h.enviar(200, pesquisa.facetas_identificadores(h.app.b, h.ler_caso(c), d.get("busca"), d.get("tabelas")))


@rota("POST", r"/api/casos/(\d+)/ocorrencias")
def r_ocorr(h, q, c):
    h.enviar(200, pesquisa.ocorrencias(h.app.b, h.ler_caso(c), h.json_corpo().get("selecionados")))


@rota("POST", r"/api/casos/(\d+)/acessos")
def r_acessos(h, q, c):
    h.enviar(200, pesquisa.acessos(h.app.b, h.ler_caso(c), h.json_corpo().get("filtros")))


@rota("POST", r"/api/casos/(\d+)/grafo")
def r_grafo(h, q, c):
    d = h.json_corpo()
    h.enviar(200, grafo.grafo(h.app.b, h.ler_caso(c), d.get("filtros"), d.get("max_nos") or 80,
                              d.get("min_volume") or 0))


@rota("POST", r"/api/casos/(\d+)/sequencias")
def r_seq(h, q, c):
    d = h.json_corpo()
    h.enviar(200, grafo.sequencias(h.app.b, h.ler_caso(c), d["inicio"], int(d.get("janela_dias") or 3),
                                   int(d.get("tolerancia_pct") or 0), int(d.get("profundidade") or 3), bool(d.get("por_nome")),
                                   data_ini=d.get("data_ini") or None, data_fim=d.get("data_fim") or None))


@rota("GET", r"/api/casos/(\d+)/duplicatas")
def r_dups(h, q, c):
    h.enviar(200, conciliacao.listar(h.app.b, h.ler_caso(c), (q.get("estado") or [None])[0]))


@rota("POST", r"/api/duplicatas/(\d+)/decidir")
def r_dup_dec(h, q, d_id):
    d = h.json_corpo()
    conciliacao.decidir(h.app.b, int(d_id), d["estado"], d.get("justificativa"), h.usuario)
    h.enviar(200, {"ok": True})


# ---------------------------------------------------------------- RIF, documentos, evidências

@rota("GET", r"/api/casos/(\d+)/rif")
def r_rif(h, q, c):
    h.enviar(200, rif.resumo(h.app.b, h.ler_caso(c)))


@rota("POST", r"/api/casos/(\d+)/rif/(\d+)/citacao")
def r_rif_cit(h, q, c, r):
    d = h.json_corpo()
    h.enviar(200, {"id": rif.adicionar_citacao(h.app.b, int(c), int(r), d.get("fonte_id"), d.get("pagina"), d.get("trecho"),
                                               d.get("id_comunicacao"), h.usuario)})


@rota("GET", r"/api/fontes/(\d+)/paginas")
def r_paginas(h, q, f):
    h.caso_da_fonte(f)
    h.enviar(200, h.app.b.q("SELECT id, pagina, metodo, revisado, revisado_por, revisado_em, texto, imagem FROM paginas "
                            "WHERE fonte_id=? ORDER BY pagina, metodo", (int(f),)))


@rota("GET", r"/api/fontes/(\d+)/original")
def r_original(h, q, f):
    fonte = h.caso_da_fonte(f)
    auditoria.registrar(h.app.b, fonte["caso_id"], h.usuario, "original_aberto", {"fonte_id": fonte["id"]})
    with open(fontes.caminho(h.app.pasta, fonte), "rb") as fh:
        dados = fh.read()
    tipo = mimetypes.guess_type(fonte["nome_original"])[0] or "application/octet-stream"
    h.enviar(200, dados, tipo, {"Content-Disposition": 'inline; filename="original_%d"' % fonte["id"]})


@rota("GET", r"/api/fontes/(\d+)/pagina_imagem/(\d+)")
def r_pag_img(h, q, f, n):
    fonte = h.caso_da_fonte(f)
    png = documentos.renderizar_pagina(h.app.pasta, fonte, fontes.caminho(h.app.pasta, fonte), int(n))
    with open(png, "rb") as fh:
        h.enviar(200, fh.read(), "image/png")


@rota("POST", r"/api/fontes/(\d+)/ocr")
def r_ocr(h, q, f):
    fonte = h.caso_da_fonte(f)
    auditoria.exigir(h.app.b, fonte["caso_id"], h.usuario, "analista")
    d = h.json_corpo()
    tid = h.server.tarefas.iniciar(documentos.ocr_pagina, h.app.b, h.app.pasta, fonte, fontes.caminho(h.app.pasta, fonte),
                                   int(d.get("pagina") or 1), h.usuario, d.get("idioma") or "por")
    h.enviar(200, {"tarefa": tid})


@rota("GET", r"/api/paginas/(\d+)/palavras")
def r_palavras(h, q, p):
    pg = h.app.b.q1("SELECT * FROM paginas WHERE id=?", (int(p),))
    h.ler_caso(pg["caso_id"])
    h.enviar(200, {"pagina": pg, "palavras": h.app.b.q("SELECT * FROM ocr_palavras WHERE pagina_id=? ORDER BY id", (int(p),))})


@rota("POST", r"/api/paginas/(\d+)/revisar")
def r_revisar(h, q, p):
    d = h.json_corpo()
    documentos.revisar_pagina(h.app.b, int(p), h.usuario, d.get("texto"), d.get("correcoes"))
    h.enviar(200, {"ok": True})


@rota("GET", r"/api/casos/(\d+)/evidencias")
def r_evid(h, q, c):
    h.enviar(200, h.app.b.q("SELECT e.*, f.nome_original FROM evidencias e LEFT JOIN fontes f ON f.id=e.fonte_id WHERE e.caso_id=? ORDER BY e.id",
                            (h.ler_caso(c),)))


@rota("POST", r"/api/casos/(\d+)/evidencias")
def r_evid_salvar(h, q, c):
    d = h.json_corpo()
    h.enviar(200, {"id": h.app.salvar_evidencia(int(c), d.get("fonte_id") or None, d.get("pagina") or None, d.get("descricao"),
                                                d["png"], d.get("jpg"), h.usuario)})


@rota("GET", r"/api/evidencias/(\d+)/imagem")
def r_evid_img(h, q, e):
    ev = h.app.b.q1("SELECT * FROM evidencias WHERE id=?", (int(e),))
    h.ler_caso(ev["caso_id"])
    with open(os.path.join(h.app.pasta, ev["arquivo_png"]), "rb") as fh:
        h.enviar(200, fh.read(), "image/png")


@rota("POST", r"/api/casos/(\d+)/relatorio")
def r_relatorio(h, q, c):
    caso = h.ler_caso(c)
    d = h.json_corpo()
    corpo, tipo, nome = relatorio.gerar(h.app.b, caso, d.get("formato") or "html", d.get("filtros"), d.get("observacoes"),
                                        d.get("evidencias"), h.usuario, h.app.pasta,
                                        incluir_analise=bool(d.get("incluir_analise")))
    auditoria.registrar(h.app.b, caso, h.usuario, "relatorio_gerado", {"formato": d.get("formato"), "filtros": d.get("filtros"),
                                                                       "sha256": util.sha256_bytes(corpo)})
    h.enviar(200, corpo, tipo, {"Content-Disposition": 'attachment; filename="caso_%d_%s"' % (caso, nome)})


# ---------------------------------------------------------------- atualização do programa

CONFIG_LOCAL = os.path.join(RAIZ, "configuracao_local.json")


def _config_local():
    try:
        with open(CONFIG_LOCAL, encoding="utf-8") as f:
            c = json.load(f)
        return c if isinstance(c, dict) else {}
    except (OSError, ValueError):
        return {}


def _atualizador():
    if RAIZ not in sys.path:
        sys.path.insert(0, RAIZ)
    import atualizar
    return atualizar


def _aplicar_atualizacao():
    codigo, texto = _atualizador().atualizar_agora(testar=True)
    return {"codigo": codigo, "texto": texto}


@rota("GET", r"/api/atualizacao/config")
def r_atu_cfg(h, q):
    h.enviar(200, {"automatica": bool(_config_local().get("verificar_atualizacao_ao_abrir", True))})


@rota("POST", r"/api/atualizacao/config")
def r_atu_cfg_salvar(h, q):
    d = h.json_corpo()
    c = _config_local()
    c["verificar_atualizacao_ao_abrir"] = bool(d.get("automatica"))
    with open(CONFIG_LOCAL, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    h.enviar(200, {"automatica": c["verificar_atualizacao_ao_abrir"]})


@rota("GET", r"/api/atualizacao/verificar")
def r_atu_verificar(h, q):
    try:
        h.enviar(200, _atualizador().verificar_atualizacao())
    except (OSError, ValueError) as e:
        h.enviar(200, {"erro": "Não foi possível consultar o GitHub (%s). Sem internet ou acesso bloqueado?" % e,
                       "instalada": VERSAO, "ha_nova": False})


@rota("POST", r"/api/atualizacao/aplicar")
def r_atu_aplicar(h, q):
    h.enviar(200, {"tarefa": h.server.tarefas.iniciar(_aplicar_atualizacao)})


# ---------------------------------------------------------------- IA e conhecimento

@rota("GET", r"/api/ia/modelos")
def r_modelos(h, q):
    h.enviar(200, ia.modelos(pasta=h.app.pasta))


@rota("GET", r"/api/ia/gemini")
def r_gemini_get(h, q):
    h.enviar(200, gemini.status(h.app.pasta))


@rota("POST", r"/api/ia/gemini")
def r_gemini_post(h, q):
    d = h.json_corpo()
    h.enviar(200, gemini.salvar(
        h.app.pasta, h.usuario, chave=d.get("chave"), modelo=d.get("modelo"),
        endpoint=d.get("endpoint"), confirmado=d.get("confirmado"),
        remover=bool(d.get("remover"))))


@rota("POST", r"/api/ia/gemini/teste")
def r_gemini_teste(h, q):
    h.enviar(200, gemini.testar(h.app.pasta))


@rota("GET", r"/api/casos/(\d+)/contexto")
def r_contexto_get(h, q, c):
    h.enviar(200, analise.contexto(h.app.b, h.ler_caso(c)))


@rota("POST", r"/api/casos/(\d+)/contexto")
def r_contexto_post(h, q, c):
    caso = h.ler_caso(c)
    d = h.json_corpo()
    h.enviar(200, analise.salvar_contexto(h.app.b, caso, h.usuario, d.get("hipotese_crime"),
                                          d.get("vitimas"), d.get("investigados")))


@rota("POST", r"/api/casos/(\d+)/analise")
def r_analise(h, q, c):
    caso = h.ler_caso(c)
    d = h.json_corpo()
    tid = h.server.tarefas.iniciar(analise.analisar, h.app.b, caso, h.usuario, d.get("filtros"),
                                   d.get("hipotese_crime"), d.get("vitimas"), d.get("investigados"),
                                   int(d.get("janela_vitima_dias") or 7))
    h.enviar(200, {"tarefa": tid})


@rota("GET", r"/api/casos/(\d+)/analise")
def r_analise_get(h, q, c):
    h.enviar(200, analise.contexto(h.app.b, h.ler_caso(c)))


@rota("POST", r"/api/fontes/(\d+)/papel")
def r_fonte_papel(h, q, f):
    fonte = h.app.fonte(int(f))
    h.ler_caso(fonte["caso_id"])
    d = h.json_corpo()
    h.enviar(200, analise.definir_papel_fonte(h.app.b, fonte["id"], d.get("papel"), h.usuario))


@rota("GET", r"/api/casos/(\d+)/ia/conversas")
def r_conversas(h, q, c):
    h.enviar(200, ia.listar_conversas(h.app.b, h.ler_caso(c)))


@rota("GET", r"/api/casos/(\d+)/ia/conversas/(\d+)")
def r_conversa(h, q, c, i):
    caso = h.ler_caso(c)
    h.enviar(200, {"id": int(i), "mensagens": ia.historico_conversa(h.app.b, caso, int(i), 200)})


@rota("POST", r"/api/casos/(\d+)/ia")
def r_ia(h, q, c):
    caso = h.ler_caso(c)
    d = h.json_corpo()
    tid = h.server.tarefas.iniciar(
        ia.conversar, h.app.b, caso, h.usuario, d.get("pergunta") or "",
        modelo=d.get("modelo") or None, filtros=d.get("filtros"), fonte_id=d.get("fonte_id") or None,
        usar_conhecimento=bool(d.get("usar_conhecimento", True)), conversa_id=d.get("conversa_id") or None,
        hipotese_crime=d.get("hipotese_crime"), vitimas=d.get("vitimas"), investigados=d.get("investigados"),
        gerar_analise=bool(d.get("gerar_analise", True)), pasta=h.app.pasta)
    h.enviar(200, {"tarefa": tid})


@rota("GET", r"/api/conhecimento")
def r_conh(h, q):
    caso = (q.get("caso") or [None])[0]
    h.enviar(200, {"documentos": conhecimento.listar(h.app.b, int(caso) if caso else None),
                   "correcoes": h.app.b.q("SELECT * FROM ia_correcoes WHERE ativo=1 ORDER BY id DESC LIMIT 500")})


@rota("POST", r"/api/conhecimento/texto")
def r_conh_txt(h, q):
    d = h.json_corpo()
    h.enviar(200, {"id": conhecimento.adicionar(h.app.b, d.get("titulo") or "Sem título", d.get("texto"), d.get("categoria") or "referencia",
                                               d.get("caso_id") or None, h.usuario)})


@rota("POST", r"/api/conhecimento/upload")
def r_conh_up(h, q):
    nome = urllib.parse.unquote(h.headers.get("X-Nome-Arquivo") or "documento.txt")
    caso = h.headers.get("X-Caso")
    cat = urllib.parse.unquote(h.headers.get("X-Categoria") or "referencia")
    n = int(h.headers.get("Content-Length") or 0)
    if n > 200 * 1024 * 1024:
        raise ValueError("arquivo grande demais para a base de conhecimento")
    tmp = os.path.join(h.app.pasta, "tmp", "conh_%s" % secrets.token_hex(8))
    try:
        with open(tmp, "wb") as f:
            f.write(h.rfile.read(n))
        did = conhecimento.adicionar_arquivo(h.app.b, tmp, nome, cat, int(caso) if caso and caso.isdigit() else None, h.usuario)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    h.enviar(200, {"id": did})


@rota("POST", r"/api/conhecimento/(\d+)/remover")
def r_conh_rem(h, q, i):
    conhecimento.remover(h.app.b, int(i), h.usuario)
    h.enviar(200, {"ok": True})


@rota("POST", r"/api/ia/correcoes")
def r_corr(h, q):
    d = h.json_corpo()
    h.enviar(200, {"id": conhecimento.adicionar_correcao(h.app.b, d.get("caso_id") or None, d.get("pergunta") or "",
                                                         d.get("resposta_revisada") or "", d.get("observacao"), h.usuario)})


@rota("POST", r"/api/ia/modelfile")
def r_modelfile(h, q):
    d = h.json_corpo()
    h.enviar(200, conhecimento.modelfile(d.get("modelo_base"), ia.prompt_sistema()), "text/plain; charset=utf-8",
             {"Content-Disposition": 'attachment; filename="Modelfile"'})


# ---------------------------------------------------------------- inicialização

def criar_servidor(pasta_dados, porta=0):
    srv = ThreadingHTTPServer(("127.0.0.1", porta), Manipulador)
    srv.daemon_threads = True
    srv.app = servico.App(pasta_dados)
    srv.chave = secrets.token_urlsafe(24)
    srv.tarefas = Tarefas()
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(description="Análise bancária local")
    ap.add_argument("--dados", default=os.path.join(RAIZ, "dados"))
    ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--sem-navegador", action="store_true")
    a = ap.parse_args(argv)
    try:
        srv = criar_servidor(a.dados, a.porta)
    except OSError:
        srv = criar_servidor(a.dados, 0)
    porta = srv.server_address[1]
    url = "http://127.0.0.1:%d/?chave=%s" % (porta, srv.chave)
    print("=" * 70)
    print("Análise Bancária Local v%s - Delegacia de Polícia de Mamborê" % VERSAO)
    print("Pasta de dados:", os.path.abspath(a.dados))
    print("Abra no navegador (não compartilhe este endereço; contém a chave da sessão):")
    print(url)
    print("Para encerrar, feche esta janela ou pressione Ctrl+C.")
    print("=" * 70)
    if not a.sem_navegador:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        shutil.rmtree(os.path.join(srv.app.pasta, "tmp"), ignore_errors=True)


if __name__ == "__main__":
    main()
