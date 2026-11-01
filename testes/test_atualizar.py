import io
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

from base import RAIZ


class TestAtualizar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="teste_atualizar_")
        self.inst = os.path.join(self.tmp, "IA_Bancaria_Windows")
        os.makedirs(os.path.join(self.inst, "financeira"))
        for nome, conteudo in {"financeira/__init__.py": 'VERSAO = "2.0.0"\n', "financeira/antigo.py": "x = 1\n",
                               "dados/analise_v3.sqlite": "BANCO", "dados/casos/caso_1/originais/a.csv": "SIGILOSO",
                               "runtime_windows/python.exe": "RUNTIME", "modelos_ollama/blob": "MODELO",
                               "configuracao_local.json": "{}"}.items():
            p = os.path.join(self.inst, *nome.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write(conteudo)
        shutil.copy(os.path.join(RAIZ, "atualizar.py"), self.inst)
        sys.path.insert(0, self.inst)
        import importlib
        import atualizar
        importlib.reload(atualizar)
        self.mod = atualizar

    def tearDown(self):
        sys.path.remove(self.inst)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pacote(self, extras=None):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("ANALISE-FINANCEIRA-main/financeira/__init__.py", 'VERSAO = "9.9.9"\n')
            z.writestr("ANALISE-FINANCEIRA-main/financeira/novo.py", "y = 2\n")
            z.writestr("ANALISE-FINANCEIRA-main/INICIAR_WINDOWS.bat", "@echo off\r\n")
            z.writestr("ANALISE-FINANCEIRA-main/dados/analise_v3.sqlite", "SOBRESCREVER")
            z.writestr("ANALISE-FINANCEIRA-main/runtime_windows/python.exe", "SOBRESCREVER")
            for k, v in (extras or {}).items():
                z.writestr(k, v)
        return buf.getvalue()

    def ler(self, rel):
        with open(os.path.join(self.inst, *rel.split("/"))) as f:
            return f.read()

    def test_preserva_dados_runtime_e_modelos(self):
        self.assertEqual(self.mod.aplicar(self.pacote()), 0)
        self.assertIn("9.9.9", self.ler("financeira/__init__.py"))
        self.assertTrue(os.path.exists(os.path.join(self.inst, "financeira", "novo.py")))
        self.assertFalse(os.path.exists(os.path.join(self.inst, "financeira", "antigo.py")))
        self.assertEqual(self.ler("dados/analise_v3.sqlite"), "BANCO")
        self.assertEqual(self.ler("dados/casos/caso_1/originais/a.csv"), "SIGILOSO")
        self.assertEqual(self.ler("runtime_windows/python.exe"), "RUNTIME")
        self.assertEqual(self.ler("modelos_ollama/blob"), "MODELO")
        backups = os.listdir(os.path.join(self.inst, "backup_versoes"))
        self.assertEqual(len(backups), 1)
        self.assertTrue(os.path.exists(os.path.join(self.inst, "backup_versoes", backups[0], "financeira", "antigo.py")))

    def test_recusa_caminho_suspeito(self):
        with self.assertRaises(IOError):
            self.mod.aplicar(self.pacote({"ANALISE-FINANCEIRA-main/../fora.py": "x"}))
        self.assertIn("2.0.0", self.ler("financeira/__init__.py"))

    def test_recusa_host_estranho(self):
        with self.assertRaises(IOError):
            self.mod.baixar("https://exemplo.invalid/x.zip")
        with self.assertRaises(IOError):
            self.mod.baixar("http://github.com/x.zip")


if __name__ == "__main__":
    unittest.main()
