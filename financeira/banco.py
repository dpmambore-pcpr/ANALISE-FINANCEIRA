"""Banco de dados local (SQLite). Valores sempre em centavos inteiros."""

import os
import sqlite3
import threading

ESQUEMA_VERSAO = 2

ESQUEMA = r"""
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);

CREATE TABLE IF NOT EXISTS casos (
  id INTEGER PRIMARY KEY, nome TEXT NOT NULL, descricao TEXT,
  criado_em TEXT, criado_por TEXT
);

CREATE TABLE IF NOT EXISTS permissoes (
  caso_id INTEGER NOT NULL REFERENCES casos(id), usuario TEXT NOT NULL,
  papel TEXT NOT NULL CHECK (papel IN ('leitor','analista','revisor','administrador')),
  PRIMARY KEY (caso_id, usuario)
);

CREATE TABLE IF NOT EXISTS remessas (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL REFERENCES casos(id),
  rotulo TEXT NOT NULL, instituicao TEXT, observacao TEXT, criado_em TEXT
);

CREATE TABLE IF NOT EXISTS fontes (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL REFERENCES casos(id),
  remessa_id INTEGER REFERENCES remessas(id), pai_id INTEGER REFERENCES fontes(id),
  nome_original TEXT NOT NULL, caminho_no_pacote TEXT, arquivo_guardado TEXT,
  sha256 TEXT NOT NULL, tamanho INTEGER, tipo TEXT, criado_em TEXT, criado_por TEXT
);
CREATE INDEX IF NOT EXISTS ix_fontes_caso ON fontes(caso_id, sha256);

CREATE TABLE IF NOT EXISTS importacoes (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL, fonte_id INTEGER NOT NULL REFERENCES fontes(id),
  remessa_id INTEGER, adaptador TEXT NOT NULL, leiaute TEXT, local TEXT,
  parametros_json TEXT, criado_em TEXT, criado_por TEXT,
  aceitos INTEGER DEFAULT 0, pendentes INTEGER DEFAULT 0, rejeitados INTEGER DEFAULT 0,
  duplicatas INTEGER DEFAULT 0, relatorio_json TEXT, estado TEXT DEFAULT 'concluida'
);

CREATE TABLE IF NOT EXISTS lancamentos (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL, importacao_id INTEGER NOT NULL,
  fonte_id INTEGER NOT NULL, remessa_id INTEGER, local TEXT, linha INTEGER,
  chave_local TEXT,
  data TEXT, hora TEXT, fuso TEXT, data_original TEXT,
  valor_centavos INTEGER, valor_original TEXT,
  natureza TEXT CHECK (natureza IN ('C','D') OR natureza IS NULL), natureza_original TEXT,
  situacao TEXT NOT NULL CHECK (situacao IN ('aceito','pendente','rejeitado')), motivo TEXT,
  titular_nome TEXT, titular_doc TEXT, titular_doc_tipo TEXT, titular_obs TEXT,
  titular_nome_norm TEXT, titular_doc_norm TEXT,
  banco TEXT, agencia TEXT, conta TEXT, conta_qtd_titulares INTEGER,
  descricao TEXT, tipo_operacao TEXT, documento TEXT,
  pix_chave TEXT, pix_tipo TEXT, pix_id TEXT, ip TEXT, porta TEXT, mac TEXT,
  cidade TEXT, uf TEXT, interface TEXT, status_origem TEXT,
  parcelas_estado TEXT, consolidado_em INTEGER,
  bruto_json TEXT, hash_conteudo TEXT
);
CREATE INDEX IF NOT EXISTS ix_lanc_caso ON lancamentos(caso_id, situacao, natureza);
CREATE INDEX IF NOT EXISTS ix_lanc_data ON lancamentos(caso_id, data, valor_centavos);
CREATE INDEX IF NOT EXISTS ix_lanc_imp ON lancamentos(importacao_id);
CREATE INDEX IF NOT EXISTS ix_lanc_hash ON lancamentos(caso_id, hash_conteudo);
CREATE INDEX IF NOT EXISTS ix_lanc_chave ON lancamentos(fonte_id, chave_local);

CREATE TABLE IF NOT EXISTS partes (
  id INTEGER PRIMARY KEY, lancamento_id INTEGER NOT NULL REFERENCES lancamentos(id),
  caso_id INTEGER NOT NULL, papel TEXT NOT NULL CHECK (papel IN ('origem','destino','indefinido')),
  ordem INTEGER, chave_od TEXT, nome TEXT, doc TEXT, doc_tipo TEXT, nome_norm TEXT, doc_norm TEXT,
  banco TEXT, agencia TEXT, conta TEXT, tipo_conta TEXT,
  pix_chave TEXT, pix_tipo TEXT, pix_id TEXT, comentario TEXT,
  valor_centavos INTEGER, valor_original TEXT, observacao TEXT,
  fonte_id INTEGER, local TEXT, linha INTEGER, bruto_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_partes_lanc ON partes(lancamento_id);
CREATE INDEX IF NOT EXISTS ix_partes_caso ON partes(caso_id, doc_norm);
CREATE INDEX IF NOT EXISTS ix_lanc_tdoc2 ON lancamentos(caso_id, titular_doc_norm, data, valor_centavos);

CREATE TABLE IF NOT EXISTS titulares (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL, importacao_id INTEGER, fonte_id INTEGER NOT NULL,
  remessa_id INTEGER, local TEXT, linha INTEGER,
  banco TEXT, agencia TEXT, conta TEXT, tipo_conta TEXT, tipo_vinculo TEXT,
  pessoa_investigada TEXT, tipo_pessoa TEXT, doc TEXT, doc_tipo TEXT, nome TEXT,
  endereco TEXT, cidade TEXT, uf TEXT, cep TEXT, telefone TEXT, email TEXT,
  dispositivo TEXT, data_inicio TEXT, data_fim TEXT, bruto_json TEXT
);

CREATE TABLE IF NOT EXISTS acessos (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL, importacao_id INTEGER, fonte_id INTEGER NOT NULL,
  local TEXT, linha INTEGER, data TEXT, hora TEXT, fuso TEXT, data_original TEXT,
  ip TEXT, porta TEXT, latitude TEXT, longitude TEXT, precisao TEXT,
  cidade TEXT, uf TEXT, pais TEXT, endereco TEXT, dispositivo TEXT, sistema TEXT,
  evento TEXT, nome TEXT, doc TEXT, telefone TEXT, email TEXT, banco TEXT, conta TEXT,
  bruto_json TEXT
);

CREATE TABLE IF NOT EXISTS ocorrencias_ident (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL, tipo TEXT NOT NULL,
  valor_norm TEXT NOT NULL, valor_original TEXT, tabela TEXT NOT NULL, registro_id INTEGER,
  fonte_id INTEGER, local TEXT, linha INTEGER, papel TEXT, importacao_id INTEGER
);
CREATE INDEX IF NOT EXISTS ix_ident ON ocorrencias_ident(caso_id, tipo, valor_norm);
CREATE INDEX IF NOT EXISTS ix_ident_fonte ON ocorrencias_ident(fonte_id);

CREATE TABLE IF NOT EXISTS paginas (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL, fonte_id INTEGER NOT NULL, pagina INTEGER NOT NULL,
  texto TEXT, metodo TEXT, revisado INTEGER DEFAULT 0, revisado_por TEXT, revisado_em TEXT,
  imagem TEXT, largura REAL, altura REAL
);
CREATE TABLE IF NOT EXISTS ocr_palavras (
  id INTEGER PRIMARY KEY, pagina_id INTEGER NOT NULL REFERENCES paginas(id),
  texto TEXT, texto_corrigido TEXT, confianca REAL,
  x INTEGER, y INTEGER, w INTEGER, h INTEGER, revisado INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rif_relatorios (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL, fonte_id INTEGER NOT NULL,
  numero TEXT, observacao TEXT, restricao TEXT, criado_em TEXT, criado_por TEXT
);
CREATE TABLE IF NOT EXISTS rif_comunicacoes (
  id INTEGER PRIMARY KEY, rif_id INTEGER NOT NULL, caso_id INTEGER NOT NULL, fonte_id INTEGER,
  local TEXT, linha INTEGER, id_comunicacao TEXT, numero_ocorrencia TEXT,
  data_recebimento TEXT, data_operacao TEXT, data_fim TEXT,
  comunicante_doc TEXT, comunicante_nome TEXT, segmento TEXT,
  cidade TEXT, uf TEXT, agencia TEXT,
  valor_centavos INTEGER, valor_original TEXT, informacoes TEXT, bruto_json TEXT
);
CREATE TABLE IF NOT EXISTS rif_envolvidos (
  id INTEGER PRIMARY KEY, rif_id INTEGER NOT NULL, caso_id INTEGER NOT NULL, fonte_id INTEGER,
  local TEXT, linha INTEGER, id_comunicacao TEXT, doc TEXT, doc_tipo TEXT, nome TEXT,
  tipo_envolvido TEXT, agencia TEXT, conta TEXT, data_abertura TEXT, data_atualizacao TEXT, bruto_json TEXT
);
CREATE TABLE IF NOT EXISTS rif_ocorrencias (
  id INTEGER PRIMARY KEY, rif_id INTEGER NOT NULL, caso_id INTEGER NOT NULL, fonte_id INTEGER,
  local TEXT, linha INTEGER, id_comunicacao TEXT, ocorrencia TEXT, bruto_json TEXT
);
CREATE TABLE IF NOT EXISTS rif_citacoes (
  id INTEGER PRIMARY KEY, rif_id INTEGER NOT NULL, caso_id INTEGER NOT NULL, fonte_id INTEGER,
  pagina INTEGER, trecho TEXT, id_comunicacao TEXT, criado_por TEXT, criado_em TEXT
);

CREATE TABLE IF NOT EXISTS duplicatas (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL, lanc_a INTEGER NOT NULL, lanc_b INTEGER NOT NULL,
  criterio TEXT NOT NULL, detalhe TEXT,
  estado TEXT NOT NULL DEFAULT 'pendente' CHECK (estado IN ('pendente','mesma_operacao','distintas','dois_lados_confirmado')),
  decidido_por TEXT, decidido_em TEXT, justificativa TEXT,
  UNIQUE (lanc_a, lanc_b, criterio)
);

CREATE TABLE IF NOT EXISTS evidencias (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL, fonte_id INTEGER, pagina INTEGER,
  descricao TEXT, arquivo_png TEXT, arquivo_jpg TEXT, sha256_png TEXT, sha256_fonte TEXT,
  largura INTEGER, altura INTEGER, criado_por TEXT, criado_em TEXT
);

CREATE TABLE IF NOT EXISTS auditoria (
  id INTEGER PRIMARY KEY, caso_id INTEGER, usuario TEXT, acao TEXT NOT NULL,
  detalhes_json TEXT, em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS perfis_mapeamento (
  id INTEGER PRIMARY KEY, nome TEXT NOT NULL, instituicao TEXT, assinatura TEXT NOT NULL,
  adaptador TEXT NOT NULL, mapeamento_json TEXT NOT NULL, opcoes_json TEXT,
  usos INTEGER DEFAULT 0, criado_em TEXT, criado_por TEXT, origem TEXT DEFAULT 'aprendido'
);

CREATE TABLE IF NOT EXISTS conhecimento_docs (
  id INTEGER PRIMARY KEY, caso_id INTEGER, titulo TEXT NOT NULL, categoria TEXT,
  sha256 TEXT, criado_em TEXT, criado_por TEXT, ativo INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS conhecimento_trechos (
  id INTEGER PRIMARY KEY, doc_id INTEGER NOT NULL REFERENCES conhecimento_docs(id),
  ordem INTEGER, texto TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ia_correcoes (
  id INTEGER PRIMARY KEY, caso_id INTEGER, pergunta TEXT NOT NULL, resposta_revisada TEXT NOT NULL,
  observacao TEXT, criado_por TEXT, criado_em TEXT, ativo INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS caso_contexto (
  caso_id INTEGER PRIMARY KEY REFERENCES casos(id),
  hipotese_crime TEXT,
  vitimas_json TEXT,
  investigados_json TEXT,
  analise_json TEXT,
  analise_em TEXT,
  analise_por TEXT,
  atualizado_em TEXT,
  atualizado_por TEXT
);

CREATE TABLE IF NOT EXISTS ia_conversas (
  id INTEGER PRIMARY KEY, caso_id INTEGER NOT NULL REFERENCES casos(id),
  titulo TEXT, criado_em TEXT, criado_por TEXT
);
CREATE TABLE IF NOT EXISTS ia_mensagens (
  id INTEGER PRIMARY KEY, conversa_id INTEGER NOT NULL REFERENCES ia_conversas(id),
  papel TEXT NOT NULL, texto TEXT NOT NULL, alcance_json TEXT, modelo TEXT, em TEXT
);
"""

_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS conhecimento_fts USING fts5(
  texto, content='conhecimento_trechos', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
"""


class Banco:
    """Conexão serializada: o servidor é multithread e o SQLite recebe uma operação por vez."""

    def __init__(self, caminho):
        self.caminho = caminho
        if caminho != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
        self.con = sqlite3.connect(caminho, check_same_thread=False, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.trava = threading.RLock()
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.execute("PRAGMA journal_mode = DELETE")
        self.fts = False
        self._migrar()

    def _migrar(self):
        with self.trava:
            self.con.executescript(ESQUEMA)
            try:
                self.con.executescript(_FTS)
                self.fts = True
            except sqlite3.OperationalError:
                self.fts = False
            cols = [r["name"] for r in self.con.execute("PRAGMA table_info(fontes)").fetchall()]
            if "papel" not in cols:
                self.con.execute("ALTER TABLE fontes ADD COLUMN papel TEXT")
            self.con.execute(
                "INSERT OR REPLACE INTO meta(chave, valor) VALUES ('esquema_versao', ?)", (str(ESQUEMA_VERSAO),))

    def q(self, sql, params=()):
        with self.trava:
            return [dict(r) for r in self.con.execute(sql, params).fetchall()]

    def q1(self, sql, params=()):
        with self.trava:
            r = self.con.execute(sql, params).fetchone()
            return dict(r) if r else None

    def x(self, sql, params=()):
        with self.trava:
            cur = self.con.execute(sql, params)
            return cur.lastrowid

    def xm(self, sql, seq):
        with self.trava:
            self.con.executemany(sql, seq)

    def transacao(self):
        return _Transacao(self)

    def fechar(self):
        with self.trava:
            self.con.close()


class _Transacao:
    def __init__(self, banco):
        self.b = banco

    def __enter__(self):
        self.b.trava.acquire()
        self.b.con.execute("BEGIN")
        return self.b

    def __exit__(self, tipo, valor, tb):
        try:
            if tipo is None:
                self.b.con.execute("COMMIT")
            else:
                self.b.con.execute("ROLLBACK")
        finally:
            self.b.trava.release()
        return False
