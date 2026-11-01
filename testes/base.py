import io
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from financeira import servico, util  # noqa: E402

EXEMPLOS = os.path.join(RAIZ, "exemplos")


def exemplo(nome):
    return os.path.join(EXEMPLOS, nome)


def cpf(n):
    return util.gerar_cpf_ficticio(n)


class CasoTeste(unittest.TestCase):
    usuario = "analista.teste"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="teste_analise_")
        self.app = servico.App(os.path.join(self.tmp, "dados"))
        self.caso = self.app.criar_caso("Teste fictício", "", self.usuario)

    def tearDown(self):
        self.app.b.fechar()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fonte(self, caminho, nome=None, remessa_id=None, caso=None):
        return self.app.receber_arquivo(caso or self.caso, caminho, nome or os.path.basename(caminho), self.usuario, remessa_id)

    def fonte_bytes(self, nome, dados, remessa_id=None):
        p = os.path.join(self.tmp, nome)
        with open(p, "wb") as f:
            f.write(dados)
        return self.fonte(p, nome, remessa_id)

    def importar_tabela(self, caminho, adaptador="extrato", opcoes=None, ajuste=None, aba=None):
        f = self.fonte(caminho)
        p = self.app.previa(f["id"], aba=aba)
        mapa = dict(p["sugestoes"][adaptador])
        if ajuste:
            mapa.update(ajuste)
        op = {"linha_cabecalho": p["linha_cabecalho"], "aba": p["aba"]}
        op.update(opcoes or {})
        return f, self.app.importar(f["id"], adaptador, mapa, op, self.usuario)


def zip_bytes(arquivos):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, texto in arquivos.items():
            z.writestr(nome, texto)
    return buf.getvalue()
