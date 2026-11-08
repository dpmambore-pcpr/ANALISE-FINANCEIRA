"""Verifica o ambiente e roda os testes com dados FICTÍCIOS. Não lê arquivos dos casos."""

import os
import platform
import sqlite3
import sys
import unittest

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "testes"))


def main():
    from financeira import VERSAO, documentos, ia
    print("Análise Bancária Local v%s" % VERSAO)
    print("Python %s (%s) em %s" % (platform.python_version(), sys.executable, platform.platform()))
    print("SQLite %s" % sqlite3.sqlite_version)
    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        print("Busca de texto (FTS5): disponível")
    except sqlite3.OperationalError:
        print("Busca de texto (FTS5): indisponível - a base de conhecimento usa busca simples")
    o = documentos.ocr_disponivel()
    print("OCR local: %s" % ("disponível (%s)" % ", ".join(o["idiomas"]) if o["disponivel"] else "não instalado (opcional)"))
    pasta = os.path.join(RAIZ, "dados")
    m = ia.modelos(pasta=pasta if os.path.isdir(pasta) else None)
    if m.get("disponivel") is False:
        print("Ollama local: não encontrado (opcional) - %s" % m.get("erro"))
    else:
        print("Ollama local: %s, modelos: %s%s" % (m["versao"], ", ".join(m["modelos"]) or "nenhum",
                                                  "; bloqueados (nuvem): " + ", ".join(m["bloqueados_nuvem"]) if m["bloqueados_nuvem"] else ""))
    g = m.get("gemini") or {}
    if g.get("configurado"):
        print("Gemini: configurado (%s)" % (g.get("chave_mascarada") or g.get("origem") or "sim"))
    else:
        print("Gemini: desligado (opcional)")
    for p, s in (m.get("nuvem") or {}).items():
        if s.get("configurado"):
            print("%s: configurado (%s)" % (s.get("rotulo") or p, s.get("chave_mascarada") or "sim"))
        else:
            print("%s: desligado (opcional)" % (s.get("rotulo") or p))
    print("\nTestes automatizados (dados fictícios):")
    suite = unittest.defaultTestLoader.discover(os.path.join(RAIZ, "testes"), pattern="test_*.py", top_level_dir=os.path.join(RAIZ, "testes"))
    r = unittest.TextTestRunner(verbosity=1).run(suite)
    print("\nRESULTADO: %s" % ("OK" if r.wasSuccessful() else "FALHOU - envie esta tela ao responsável"))
    return 0 if r.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
