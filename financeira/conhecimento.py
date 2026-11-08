"""Base de conhecimento local para a IA (recuperação de trechos, sem treinar o modelo).

Como "alimentar" a IA com o tempo, sem enviar nada para fora do computador:
1. Documentos de referência (manuais, leiautes, normas, modelos de relatório, glossários e
   exemplos ANONIMIZADOS) são divididos em trechos e indexados aqui. A cada pergunta, os
   trechos mais relevantes acompanham o pedido ao Ollama local.
2. Respostas revisadas pelo analista ficam como "correções" e são usadas como exemplos.
3. Perfis de mapeamento aprendidos na importação fazem o programa reconhecer leiautes de
   bancos já vistos.
Documentos de um caso ficam restritos ao caso; os gerais (caso_id vazio) valem para todos.
"""

import re

from . import auditoria, leitores, util

TAM_TRECHO = 900


def dividir(texto, tam=TAM_TRECHO):
    pars = [p.strip() for p in re.split(r"\n\s*\n", texto or "") if p.strip()]
    trechos, atual = [], ""
    for p in pars:
        while len(p) > tam:
            corte = p.rfind(" ", 0, tam)
            corte = corte if corte > tam // 2 else tam
            if atual:
                trechos.append(atual)
                atual = ""
            trechos.append(p[:corte].strip())
            p = p[corte:].strip()
        if len(atual) + len(p) + 2 > tam and atual:
            trechos.append(atual)
            atual = p
        else:
            atual = (atual + "\n\n" + p) if atual else p
    if atual:
        trechos.append(atual)
    return trechos


def adicionar(b, titulo, texto, categoria="referencia", caso_id=None, usuario=None):
    if not str(texto or "").strip():
        raise ValueError("Documento sem texto.")
    sha = util.sha256_bytes(texto.encode("utf-8"))
    ex = b.q1("SELECT id FROM conhecimento_docs WHERE sha256=? AND COALESCE(caso_id,0)=COALESCE(?,0) AND ativo=1", (sha, caso_id))
    if ex:
        raise ValueError("Este texto já está na base de conhecimento (documento %d)." % ex["id"])
    with b.transacao():
        did = b.con.execute("INSERT INTO conhecimento_docs(caso_id, titulo, categoria, sha256, criado_em, criado_por) VALUES (?,?,?,?,?,?)",
                            (caso_id, titulo, categoria, sha, util.agora_iso(), usuario)).lastrowid
        for i, t in enumerate(dividir(texto)):
            tid = b.con.execute("INSERT INTO conhecimento_trechos(doc_id, ordem, texto) VALUES (?,?,?)", (did, i, t)).lastrowid
            if b.fts:
                b.con.execute("INSERT INTO conhecimento_fts(rowid, texto) VALUES (?,?)", (tid, t))
    auditoria.registrar(b, caso_id, usuario, "conhecimento_incluido", {"doc_id": did, "titulo": titulo, "sha256": sha})
    return did


def adicionar_arquivo(b, caminho, nome, categoria, caso_id, usuario):
    ext = nome.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        paginas, _ = leitores.texto_pdf(caminho)
        texto = "\n\n".join("[página %d]\n%s" % (i + 1, t) for i, t in enumerate(paginas) if t.strip())
    elif ext in ("txt", "md", "csv"):
        with open(caminho, "rb") as f:
            dados = f.read()
        cod = leitores.detectar_codificacao(dados[:1024 * 1024])
        texto = dados.decode(cod, errors="replace")
    else:
        raise ValueError("Use TXT, MD, CSV ou PDF com texto.")
    return adicionar(b, nome, texto, categoria, caso_id, usuario)


def remover(b, doc_id, usuario):
    d = b.q1("SELECT * FROM conhecimento_docs WHERE id=?", (doc_id,))
    if not d:
        raise KeyError("documento inexistente")
    b.x("UPDATE conhecimento_docs SET ativo=0 WHERE id=?", (doc_id,))
    auditoria.registrar(b, d["caso_id"], usuario, "conhecimento_desativado", {"doc_id": doc_id})


def listar(b, caso_id=None):
    return b.q("SELECT d.*, (SELECT COUNT(*) FROM conhecimento_trechos t WHERE t.doc_id=d.id) AS trechos FROM conhecimento_docs d "
               "WHERE d.ativo=1 AND (d.caso_id IS NULL OR d.caso_id=?) ORDER BY d.id DESC", (caso_id,))


PALAVRAS_VAZIAS = set("que qual quais quem como onde quando para por com sem dos das nos nas uma uns umas este esta isso "
                     "esse essa sao foi ser ter tem existe existem houve pelo pela entre sobre mais menos".split())


def _termos(consulta):
    return [t for t in re.findall(r"\w{3,}", util.sem_acentos(consulta).lower()) if t not in PALAVRAS_VAZIAS][:20]


def _radical(t):
    """Radical simples (sem dicionário) para casar singular/plural e variações: tarifas -> tarif."""
    return t if len(t) <= 4 else t[:max(4, len(t) - 2)]


def buscar(b, consulta, caso_id=None, limite=5):
    termos = _termos(consulta)
    if not termos:
        return []
    if b.fts:
        q = " OR ".join('"%s"*' % _radical(t) for t in termos)
        try:
            return b.q("SELECT t.id, t.texto, d.titulo, d.categoria, d.id AS doc_id, bm25(conhecimento_fts) AS pont "
                       "FROM conhecimento_fts JOIN conhecimento_trechos t ON t.id=conhecimento_fts.rowid "
                       "JOIN conhecimento_docs d ON d.id=t.doc_id WHERE conhecimento_fts MATCH ? AND d.ativo=1 "
                       "AND (d.caso_id IS NULL OR d.caso_id=?) ORDER BY pont LIMIT ?", (q, caso_id, limite))
        except Exception:  # noqa: BLE001 - consulta FTS inválida cai na busca simples
            pass
    linhas = b.q("SELECT t.id, t.texto, d.titulo, d.categoria, d.id AS doc_id FROM conhecimento_trechos t "
                 "JOIN conhecimento_docs d ON d.id=t.doc_id WHERE d.ativo=1 AND (d.caso_id IS NULL OR d.caso_id=?)", (caso_id,))
    for ln in linhas:
        txt = util.sem_acentos(ln["texto"]).lower()
        ln["pont"] = -sum(txt.count(_radical(t)) for t in termos)
    return sorted([ln for ln in linhas if ln["pont"] < 0], key=lambda x: x["pont"])[:limite]


def aprender_da_nuvem(b, caso_id, usuario, pergunta, resposta, provedor):
    """Guarda a resposta da IA paga como exemplo para a IA local nas próximas perguntas."""
    pergunta = (pergunta or "").strip()
    resposta = (resposta or "").strip()
    if not pergunta or not resposta:
        return None
    obs = "exemplo automático da IA %s — a IA local usa nas próximas perguntas" % provedor
    cid = adicionar_correcao(b, None, pergunta[:2000], resposta[:8000], obs, usuario)
    titulo = "Exemplo %s — %s" % (provedor, pergunta[:80])
    texto = ("Pergunta do analista:\n%s\n\nResposta da IA %s (exemplo para a IA local; "
             "confira os números no programa):\n%s" % (pergunta[:2000], provedor, resposta[:6000]))
    try:
        adicionar(b, titulo, texto, "exemplo_ia_paga", None, usuario)
    except ValueError:
        pass
    return cid


def adicionar_correcao(b, caso_id, pergunta, resposta_revisada, observacao, usuario):
    if not pergunta.strip() or not resposta_revisada.strip():
        raise ValueError("Informe a pergunta e a resposta revisada.")
    cid = b.x("INSERT INTO ia_correcoes(caso_id, pergunta, resposta_revisada, observacao, criado_por, criado_em) VALUES (?,?,?,?,?,?)",
              (caso_id, pergunta, resposta_revisada, observacao, usuario, util.agora_iso()))
    auditoria.registrar(b, caso_id, usuario, "ia_correcao", {"correcao_id": cid})
    return cid


def buscar_correcoes(b, consulta, caso_id=None, limite=3):
    termos = set(_radical(t) for t in _termos(consulta))
    linhas = b.q("SELECT * FROM ia_correcoes WHERE ativo=1 AND (caso_id IS NULL OR caso_id=?)", (caso_id,))
    for ln in linhas:
        ln["pont"] = len(termos & set(_radical(t) for t in _termos(ln["pergunta"])))
    return sorted([ln for ln in linhas if ln["pont"] > 0], key=lambda x: -x["pont"])[:limite]


def modelfile(modelo_base, prompt_sistema):
    """Texto de Modelfile do Ollama: cria, localmente, um modelo com as regras fixas da unidade."""
    if not re.fullmatch(r"[\w.:\-/]+", modelo_base or ""):
        raise ValueError("Nome de modelo inválido")
    corpo = prompt_sistema.replace('"""', "'''")
    return ('FROM %s\nPARAMETER temperature 0.1\nPARAMETER num_ctx 8192\nSYSTEM """%s"""\n' % (modelo_base, corpo))
