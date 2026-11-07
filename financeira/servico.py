"""Fachada da aplicação usada pelo servidor web e pelos testes."""

import base64
import os

from . import (adaptadores, auditoria, banco, documentos, extrato_pdf, fontes, importacao, leitores, rif, simba, util)

NOME_BANCO = "analise_v3.sqlite"


class App:
    def __init__(self, pasta_dados):
        self.pasta = os.path.abspath(pasta_dados)
        os.makedirs(os.path.join(self.pasta, "tmp"), exist_ok=True)
        self.b = banco.Banco(os.path.join(self.pasta, NOME_BANCO))

    # ------------------------------------------------------------ casos
    def criar_caso(self, nome, descricao, usuario):
        if not str(nome or "").strip():
            raise ValueError("Informe o nome do caso.")
        cid = self.b.x("INSERT INTO casos(nome, descricao, criado_em, criado_por) VALUES (?,?,?,?)",
                       (nome.strip(), descricao, util.agora_iso(), usuario))
        if usuario:
            self.b.x("INSERT INTO permissoes(caso_id, usuario, papel) VALUES (?,?, 'administrador')", (cid, usuario))
        auditoria.registrar(self.b, cid, usuario, "caso_criado", {"nome": nome})
        return cid

    def casos(self, usuario):
        out = []
        for c in self.b.q("SELECT * FROM casos ORDER BY id DESC"):
            c["papel"] = auditoria.papel(self.b, c["id"], usuario)
            if c["papel"]:
                c["n_fontes"] = self.b.q1("SELECT COUNT(*) AS n FROM fontes WHERE caso_id=?", (c["id"],))["n"]
                c["n_lancamentos"] = self.b.q1("SELECT COUNT(*) AS n FROM lancamentos WHERE caso_id=?", (c["id"],))["n"]
                c["permissoes"] = self.b.q("SELECT usuario, papel FROM permissoes WHERE caso_id=?", (c["id"],))
                out.append(c)
        return out

    def criar_remessa(self, caso_id, rotulo, instituicao, observacao, usuario):
        auditoria.exigir(self.b, caso_id, usuario, "analista")
        rid = self.b.x("INSERT INTO remessas(caso_id, rotulo, instituicao, observacao, criado_em) VALUES (?,?,?,?,?)",
                       (caso_id, rotulo, instituicao, observacao, util.agora_iso()))
        auditoria.registrar(self.b, caso_id, usuario, "remessa_criada", {"remessa_id": rid, "rotulo": rotulo})
        return rid

    # ------------------------------------------------------------ fontes
    def receber_arquivo(self, caso_id, caminho_tmp, nome, usuario, remessa_id=None):
        auditoria.exigir(self.b, caso_id, usuario, "analista")
        return fontes.registrar(self.b, self.pasta, caso_id, caminho_tmp, nome, usuario, remessa_id=remessa_id)

    def fonte(self, fonte_id):
        f = self.b.q1("SELECT * FROM fontes WHERE id=?", (int(fonte_id),))
        if not f:
            raise KeyError("fonte inexistente")
        return f

    def listar_fontes(self, caso_id):
        fs = self.b.q("SELECT f.*, r.rotulo AS remessa FROM fontes f LEFT JOIN remessas r ON r.id=f.remessa_id WHERE f.caso_id=? ORDER BY f.id", (caso_id,))
        for f in fs:
            f["importacoes"] = self.b.q("SELECT id, adaptador, leiaute, local, criado_em, criado_por, aceitos, pendentes, rejeitados, "
                                        "duplicatas, estado FROM importacoes WHERE fonte_id=? ORDER BY id", (f["id"],))
        return fs

    def conferir_fontes(self, caso_id):
        return [{"id": f["id"], "nome": f["nome_original"], "ok": fontes.conferir_integridade(self.pasta, f)}
                for f in self.b.q("SELECT * FROM fontes WHERE caso_id=?", (caso_id,))]

    def conteudo_zip(self, fonte_id):
        f = self.fonte(fonte_id)
        itens = fontes.listar_zip(self.pasta, f)
        res = {"itens": itens, "simba": None, "rif": False}
        try:
            res["simba"] = simba.inspecionar(fontes.caminho(self.pasta, f))
        except simba.ErroSimba as e:
            res["simba_erro"] = str(e)
        nomes = " ".join(i["nome"].upper() for i in itens)
        res["rif"] = "COMUNICA" in nomes and "ENVOLVIDO" in nomes
        return res

    def extrair_membro(self, fonte_id, membro, usuario):
        f = self.fonte(fonte_id)
        auditoria.exigir(self.b, f["caso_id"], usuario, "analista")
        return fontes.extrair_membro(self.b, self.pasta, f, membro, usuario)

    def previa(self, fonte_id, aba=None, linha_cabecalho=None):
        f = self.fonte(fonte_id)
        cam = fontes.caminho(self.pasta, f)
        if f["tipo"] in ("delimitado", "xlsx"):
            p = adaptadores.previa(self.b, cam, f["tipo"], aba, linha_cabecalho)
            p["tipo_arquivo"] = f["tipo"]
            return p
        if f["tipo"] == "zip":
            return {"tipo_arquivo": "zip", "conteudo": self.conteudo_zip(fonte_id)}
        if f["tipo"] == "pdf":
            res = {"tipo_arquivo": "pdf", "ocr": documentos.ocr_disponivel()}
            try:
                paginas, _ = leitores.texto_pdf(cam)
                if extrato_pdf.reconhecer(paginas):
                    res["extrato_detalhado"] = extrato_pdf.resumo(extrato_pdf.analisar(paginas))
                elif any("EXTRATO DETALHADO" in t for t in paginas[:3]):
                    res["aviso_leitura"] = ("O PDF parece ser um EXTRATO DETALHADO, mas o texto foi lido sem manter as linhas da tabela "
                                            "(leitor interno). Confirme que a pasta vendor (pypdf) existe ao lado do programa e abra "
                                            "pelo INICIAR_WINDOWS.bat.")
            except Exception as e:  # noqa: BLE001
                res["aviso_leitura"] = "Não foi possível ler o texto do PDF: %s" % e
            return res
        return {"tipo_arquivo": f["tipo"]}

    # ------------------------------------------------------------ importação
    def importar(self, fonte_id, adaptador, mapeamento=None, opcoes=None, usuario=None, progresso=None):
        f = self.fonte(fonte_id)
        auditoria.exigir(self.b, f["caso_id"], usuario, "analista")
        opcoes = opcoes or {}
        cam = fontes.caminho(self.pasta, f)
        if not fontes.conferir_integridade(self.pasta, f):
            raise IOError("O SHA-256 do original guardado não confere. Importação recusada.")
        if adaptador in ("extrato", "acessos", "cadastro") and f["tipo"] not in ("delimitado", "xlsx"):
            raise ValueError("Este adaptador usa CSV, TXT delimitado ou XLSX.")
        leiaute = None
        if adaptador == "simba":
            leiaute = simba.inspecionar(cam)["leiaute"]
        imp = importacao.Importador(self.b, f["caso_id"], f, adaptador, usuario,
                                    parametros={"mapeamento": mapeamento, "opcoes": opcoes},
                                    leiaute=leiaute, local=opcoes.get("aba"), progresso=progresso)
        try:
            if adaptador == "extrato":
                adaptadores.importar_extrato(imp, cam, f["tipo"], mapeamento, opcoes)
            elif adaptador == "acessos":
                adaptadores.importar_acessos(imp, cam, f["tipo"], mapeamento, opcoes)
            elif adaptador == "cadastro":
                adaptadores.importar_cadastro(imp, cam, f["tipo"], mapeamento, opcoes)
            elif adaptador == "simba":
                if f["tipo"] != "zip":
                    raise ValueError("SIMBA bruto: envie um ZIP com EXTRATO e ORIGEM_DESTINO da mesma remessa.")
                simba.importar(imp, cam, opcoes)
            elif adaptador == "rif":
                rif.importar(imp, cam, f["tipo"], f["nome_original"], opcoes, os.path.join(self.pasta, "tmp"))
            elif adaptador == "pdf_extrato":
                if f["tipo"] != "pdf":
                    raise ValueError("Use um arquivo PDF.")
                extrato_pdf.importar(imp, cam)
                imp.b.con.execute("UPDATE fontes SET papel=? WHERE id=?", ("extrato", f["id"]))
            elif adaptador == "pdf_texto":
                if f["tipo"] != "pdf":
                    raise ValueError("Use um arquivo PDF.")
                documentos.extrair_texto(imp, cam)
                papel = opcoes.get("papel") or ("rif" if opcoes.get("rif") else "documento")
                imp.b.con.execute("UPDATE fontes SET papel=? WHERE id=?", (papel, f["id"]))
            else:
                raise ValueError("adaptador desconhecido: %s" % adaptador)
        except Exception as e:
            imp.abortar(e)
            raise
        rel = imp.finalizar(opcoes.get("controle"))
        if opcoes.get("salvar_perfil") and adaptador in ("extrato", "acessos", "cadastro"):
            prev = adaptadores.previa(self.b, cam, f["tipo"], opcoes.get("aba"), opcoes.get("linha_cabecalho"), n=1)
            adaptadores.salvar_perfil(self.b, opcoes.get("nome_perfil") or f["nome_original"], opcoes.get("instituicao"),
                                      prev["cabecalho"], adaptador, mapeamento,
                                      {k: v for k, v in opcoes.items() if k in ("natureza_fixa", "sinal_credito", "instituicao")}, usuario)
            rel["perfil_salvo"] = True
        return rel

    def relatorio_importacao(self, imp_id):
        import json
        i = self.b.q1("SELECT i.*, f.nome_original, f.sha256 FROM importacoes i JOIN fontes f ON f.id=i.fonte_id WHERE i.id=?", (imp_id,))
        if not i:
            raise KeyError("importação inexistente")
        i["relatorio"] = json.loads(i.pop("relatorio_json") or "{}")
        return i

    def desfazer_importacao(self, imp_id, usuario):
        i = self.b.q1("SELECT caso_id FROM importacoes WHERE id=?", (imp_id,))
        auditoria.exigir(self.b, i["caso_id"], usuario, "revisor")
        importacao.desfazer(self.b, imp_id, usuario)

    # ------------------------------------------------------------ evidências
    def salvar_evidencia(self, caso_id, fonte_id, pagina, descricao, png_b64, jpg_b64, usuario):
        auditoria.exigir(self.b, caso_id, usuario, "analista")
        png = base64.b64decode(png_b64.split(",", 1)[-1])
        if png[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("imagem PNG inválida")
        jpg = base64.b64decode(jpg_b64.split(",", 1)[-1]) if jpg_b64 else None
        if jpg and jpg[:2] != b"\xff\xd8":
            jpg = None
        sha = util.sha256_bytes(png)
        pasta = os.path.join(fontes.pasta_caso(self.pasta, caso_id), "derivados", "evidencias")
        os.makedirs(pasta, exist_ok=True)
        rel_png = os.path.relpath(os.path.join(pasta, sha[:20] + ".png"), self.pasta)
        with open(os.path.join(self.pasta, rel_png), "wb") as f:
            f.write(png)
        rel_jpg = None
        if jpg:
            rel_jpg = os.path.relpath(os.path.join(pasta, sha[:20] + ".jpg"), self.pasta)
            with open(os.path.join(self.pasta, rel_jpg), "wb") as f:
                f.write(jpg)
        fsha = None
        if fonte_id:
            fsha = self.fonte(fonte_id)["sha256"]
        import struct
        w, h = struct.unpack(">II", png[16:24])
        eid = self.b.x("INSERT INTO evidencias(caso_id, fonte_id, pagina, descricao, arquivo_png, arquivo_jpg, sha256_png, sha256_fonte, "
                       "largura, altura, criado_por, criado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (caso_id, fonte_id, pagina, descricao, rel_png, rel_jpg, sha, fsha, w, h, usuario, util.agora_iso()))
        auditoria.registrar(self.b, caso_id, usuario, "evidencia_salva", {"evidencia_id": eid, "fonte_id": fonte_id, "pagina": pagina,
                                                                          "sha256_imagem": sha, "sha256_fonte": fsha})
        return eid
