"""Guarda dos arquivos originais. O original nunca é alterado; o SHA-256 é calculado na entrada."""

import os
import re
import shutil
import zipfile

from . import auditoria, util

EXTENSOES = {
    ".csv": "delimitado", ".txt": "delimitado", ".tsv": "delimitado",
    ".xlsx": "xlsx", ".xlsm": "xlsx", ".zip": "zip", ".pdf": "pdf",
    ".png": "imagem", ".jpg": "imagem", ".jpeg": "imagem",
}


class FonteDuplicada(Exception):
    def __init__(self, fonte):
        super().__init__("Arquivo de bytes idênticos já incluído neste caso (fonte %d, %s)." % (fonte["id"], fonte["nome_original"]))
        self.fonte = fonte


def _nome_seguro(nome):
    base = os.path.basename(nome.replace("\\", "/"))
    base = re.sub(r"[^\w.\-]+", "_", base, flags=re.UNICODE)
    return base[:120] or "arquivo"


def tipo_por_nome(nome):
    return EXTENSOES.get(os.path.splitext(nome.lower())[1], "outro")


def pasta_caso(pasta_dados, caso_id):
    p = os.path.join(pasta_dados, "casos", "caso_%d" % caso_id)
    os.makedirs(os.path.join(p, "originais"), exist_ok=True)
    os.makedirs(os.path.join(p, "derivados"), exist_ok=True)
    return p


def registrar(b, pasta_dados, caso_id, caminho_tmp, nome_original, usuario, remessa_id=None,
              pai_id=None, caminho_no_pacote=None):
    sha = util.sha256_arquivo(caminho_tmp)
    existente = b.q1("SELECT * FROM fontes WHERE caso_id=? AND sha256=? AND "
                     "COALESCE(pai_id,0)=COALESCE(?,0)", (caso_id, sha, pai_id))
    if existente:
        raise FonteDuplicada(existente)
    destino_rel = os.path.join("casos", "caso_%d" % caso_id, "originais", "%s_%s" % (sha[:16], _nome_seguro(nome_original)))
    destino = os.path.join(pasta_dados, destino_rel)
    pasta_caso(pasta_dados, caso_id)
    if not os.path.exists(destino):
        shutil.copyfile(caminho_tmp, destino)
    if util.sha256_arquivo(destino) != sha:
        raise IOError("SHA-256 da cópia guardada não confere com o arquivo recebido")
    fid = b.x("INSERT INTO fontes(caso_id, remessa_id, pai_id, nome_original, caminho_no_pacote, arquivo_guardado, "
              "sha256, tamanho, tipo, criado_em, criado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (caso_id, remessa_id, pai_id, nome_original, caminho_no_pacote, destino_rel, sha,
               os.path.getsize(destino), tipo_por_nome(nome_original), util.agora_iso(), usuario))
    auditoria.registrar(b, caso_id, usuario, "fonte_incluida",
                        {"fonte_id": fid, "nome": nome_original, "sha256": sha, "pai_id": pai_id,
                         "caminho_no_pacote": caminho_no_pacote})
    return b.q1("SELECT * FROM fontes WHERE id=?", (fid,))


def caminho(pasta_dados, fonte):
    return os.path.join(pasta_dados, fonte["arquivo_guardado"])


def conferir_integridade(pasta_dados, fonte):
    p = caminho(pasta_dados, fonte)
    if not os.path.exists(p):
        return False
    return util.sha256_arquivo(p) == fonte["sha256"]


def listar_zip(pasta_dados, fonte):
    with zipfile.ZipFile(caminho(pasta_dados, fonte)) as z:
        out = []
        for info in z.infolist():
            if info.is_dir():
                continue
            out.append({"nome": info.filename, "tamanho": info.file_size, "tipo": tipo_por_nome(info.filename)})
        return out


def extrair_membro(b, pasta_dados, fonte_zip, membro, usuario):
    """Cria uma fonte filha com o conteúdo de um arquivo do ZIP (o ZIP original permanece intacto)."""
    existente = b.q1("SELECT * FROM fontes WHERE pai_id=? AND caminho_no_pacote=?", (fonte_zip["id"], membro))
    if existente:
        return existente
    tmp_dir = os.path.join(pasta_dados, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp = os.path.join(tmp_dir, "membro_%d_%s" % (fonte_zip["id"], _nome_seguro(membro)))
    with zipfile.ZipFile(caminho(pasta_dados, fonte_zip)) as z:
        if membro not in z.namelist():
            raise KeyError("arquivo não está no pacote: %s" % membro)
        with z.open(membro) as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
    try:
        return registrar(b, pasta_dados, fonte_zip["caso_id"], tmp, os.path.basename(membro), usuario,
                         remessa_id=fonte_zip["remessa_id"], pai_id=fonte_zip["id"], caminho_no_pacote=membro)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def descricao(fonte):
    if fonte.get("caminho_no_pacote"):
        return "%s (dentro do pacote, fonte pai %s)" % (fonte["caminho_no_pacote"], fonte.get("pai_id"))
    return fonte["nome_original"]
