"""Trilha de auditoria e permissões por caso.

A identificação do usuário é declarada na tela (não há senha): serve para registro e
separação de funções, não como controle de acesso forte. Proteja o computador e a pasta
dados com as credenciais e a criptografia autorizadas pela unidade.
"""

from . import util

PAPEIS = ["leitor", "analista", "revisor", "administrador"]


class SemPermissao(Exception):
    pass


def registrar(b, caso_id, usuario, acao, detalhes=None):
    b.x("INSERT INTO auditoria(caso_id, usuario, acao, detalhes_json, em) VALUES (?,?,?,?,?)",
        (caso_id, usuario or "(não informado)", acao, util.json_dump(detalhes or {}), util.agora_iso()))


def papel(b, caso_id, usuario):
    linhas = b.q("SELECT usuario, papel FROM permissoes WHERE caso_id=?", (caso_id,))
    if not linhas:
        return "administrador"
    for ln in linhas:
        if ln["usuario"] == usuario:
            return ln["papel"]
    return None


def exigir(b, caso_id, usuario, minimo):
    p = papel(b, caso_id, usuario)
    if p is None or PAPEIS.index(p) < PAPEIS.index(minimo):
        raise SemPermissao("O usuário %r não tem papel %r neste caso (papel atual: %s)." % (usuario, minimo, p or "nenhum"))
    return p


def definir_permissao(b, caso_id, usuario_admin, alvo, novo_papel):
    exigir(b, caso_id, usuario_admin, "administrador")
    if novo_papel not in PAPEIS and novo_papel != "remover":
        raise ValueError("papel inválido")
    if not b.q("SELECT 1 FROM permissoes WHERE caso_id=?", (caso_id,)) and alvo != usuario_admin:
        b.x("INSERT OR REPLACE INTO permissoes(caso_id, usuario, papel) VALUES (?,?,?)",
            (caso_id, usuario_admin, "administrador"))
    if novo_papel == "remover":
        b.x("DELETE FROM permissoes WHERE caso_id=? AND usuario=?", (caso_id, alvo))
    else:
        b.x("INSERT OR REPLACE INTO permissoes(caso_id, usuario, papel) VALUES (?,?,?)", (caso_id, alvo, novo_papel))
    registrar(b, caso_id, usuario_admin, "permissao", {"usuario": alvo, "papel": novo_papel})
