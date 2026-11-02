"""Atualiza o CÓDIGO do programa a partir do GitHub, preservando dados, modelos e runtime.

Uso:
  python atualizar.py               baixa a versão mais recente do ramo configurado e aplica
  python atualizar.py --verificar   apenas informa se há versão nova
  python atualizar.py --zip ARQ.zip aplica um ZIP baixado em outro computador (sem internet aqui)
  python atualizar.py --testar      roda os testes automatizados depois de atualizar

Nunca são alterados: dados/, runtime_windows/, runtime_linux/, ollama/, modelos_ollama/,
ferramentas_ocr/ (exceto LEIA.txt), backup_versoes/ e configuracao_local.json.
Antes de substituir, os arquivos atuais vão para backup_versoes/<data-hora>/.
Este é o único componente que acessa a internet, e só quando executado pelo usuário.
"""

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(RAIZ, "atualizacao.json")
GERENCIADOS = ["financeira", "ferramentas", "testes", "exemplos", "docs", ".github", "vendor", "licencas"]
ARQUIVOS_RAIZ = re.compile(r"^[^/]+\.(py|bat|sh|txt|md|json)$|^\.gitignore$", re.I)
PROTEGIDOS = {"dados", "runtime_windows", "runtime_linux", "ollama", "modelos_ollama", "ferramentas_ocr", "backup_versoes",
              "configuracao_local.json", "relatorios_gerados"}
HOSTS = {"codeload.github.com", "github.com", "api.github.com", "objects.githubusercontent.com"}


def config():
    c = {"repositorio": "dpmambore-pcpr/ANALISE-FINANCEIRA", "ramo": "main"}
    if os.path.exists(CONFIG):
        with open(CONFIG, encoding="utf-8") as f:
            c.update(json.load(f))
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", c["repositorio"]) or not re.fullmatch(r"[\w./-]+", c["ramo"]):
        sys.exit("atualizacao.json inválido")
    return c


def versao_local():
    try:
        with open(os.path.join(RAIZ, "financeira", "__init__.py"), encoding="utf-8") as f:
            return re.search(r'VERSAO\s*=\s*"([^"]+)"', f.read()).group(1)
    except (OSError, AttributeError):
        return "desconhecida"


class _SoGithub(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).hostname not in HOSTS or not newurl.startswith("https://"):
            raise IOError("Redirecionamento recusado para %s" % newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def baixar(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.hostname not in HOSTS:
        raise IOError("Endereço não permitido: %s" % url)
    abridor = urllib.request.build_opener(_SoGithub)
    req = urllib.request.Request(url, headers={"User-Agent": "analise-bancaria-atualizador"})
    with abridor.open(req, timeout=120) as r:
        return r.read()


def versao_no_zip(z, prefixo):
    try:
        txt = z.read(prefixo + "financeira/__init__.py").decode("utf-8")
        return re.search(r'VERSAO\s*=\s*"([^"]+)"', txt).group(1)
    except (KeyError, AttributeError):
        return None


def prefixo_zip(z):
    nomes = z.namelist()
    for n in nomes:
        if n.endswith("financeira/__init__.py") and n.count("/") <= 2:
            return n[: -len("financeira/__init__.py")]
    raise IOError("O ZIP não contém o programa (financeira/__init__.py).")


def gerenciado(rel):
    topo = rel.split("/", 1)[0]
    if topo == "runtime_windows" and not os.path.isfile(os.path.join(RAIZ, "runtime_windows", "python.exe")):
        return True
    if topo in PROTEGIDOS:
        return False
    if "/" not in rel:
        return bool(ARQUIVOS_RAIZ.match(rel))
    return topo in GERENCIADOS


def aplicar(dados_zip, testar=False):
    sha = hashlib.sha256(dados_zip).hexdigest()
    with zipfile.ZipFile(io.BytesIO(dados_zip)) as z:
        pref = prefixo_zip(z)
        nova = versao_no_zip(z, pref)
        print("Pacote recebido: SHA-256 %s; versão %s (instalada: %s)" % (sha, nova, versao_local()))
        itens = []
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(pref):
                continue
            rel = info.filename[len(pref):]
            if not rel or rel.startswith("/") or ".." in rel.split("/") or ":" in rel:
                raise IOError("Caminho suspeito no pacote: %r" % info.filename)
            if gerenciado(rel):
                itens.append((rel, info))
        if not any(r == "financeira/__init__.py" for r, _ in itens):
            raise IOError("Pacote incompleto.")
        carimbo = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(RAIZ, "backup_versoes", "%s_v%s" % (carimbo, versao_local()))
        for pasta in GERENCIADOS:
            origem = os.path.join(RAIZ, pasta)
            if os.path.isdir(origem):
                shutil.copytree(origem, os.path.join(backup, pasta), ignore=shutil.ignore_patterns("__pycache__"))
        for nome in os.listdir(RAIZ):
            if os.path.isfile(os.path.join(RAIZ, nome)) and gerenciado(nome):
                os.makedirs(backup, exist_ok=True)
                shutil.copy2(os.path.join(RAIZ, nome), os.path.join(backup, nome))
        temp = tempfile.mkdtemp(prefix="atualizacao_", dir=RAIZ)
        try:
            for rel, info in itens:
                destino = os.path.join(temp, *rel.split("/"))
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with z.open(info) as src, open(destino, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            for pasta in ("financeira", "ferramentas", "testes", "exemplos"):
                if os.path.isdir(os.path.join(temp, pasta)) and os.path.isdir(os.path.join(RAIZ, pasta)):
                    shutil.rmtree(os.path.join(RAIZ, pasta))
            for rel, _ in itens:
                origem = os.path.join(temp, *rel.split("/"))
                destino = os.path.join(RAIZ, *rel.split("/"))
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                shutil.copy2(origem, destino)
        finally:
            shutil.rmtree(temp, ignore_errors=True)
    print("Atualizado para a versão %s. Cópia da versão anterior: %s" % (nova, backup))
    print("Seus dados (pasta dados/) não foram alterados.")
    if testar:
        r = subprocess.run([sys.executable, os.path.join(RAIZ, "verificar.py")], cwd=RAIZ)
        if r.returncode:
            print("ATENÇÃO: verificação falhou. A versão anterior está em", backup)
            return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--zip")
    ap.add_argument("--testar", action="store_true")
    ap.add_argument("--sim", action="store_true", help="não pedir confirmação")
    a = ap.parse_args(argv)
    if a.zip:
        with open(a.zip, "rb") as f:
            return aplicar(f.read(), a.testar)
    c = config()
    if os.path.isdir(os.path.join(RAIZ, ".git")) and shutil.which("git"):
        print("Pasta com Git: use 'git pull --ff-only' (executando agora).")
        return subprocess.run(["git", "pull", "--ff-only"], cwd=RAIZ).returncode
    base = "https://codeload.github.com/%s/zip/refs/heads/%s" % (c["repositorio"], c["ramo"])
    print("Versão instalada:", versao_local())
    print("Baixando de", base)
    dados = baixar(base)
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nova = versao_no_zip(z, prefixo_zip(z))
    print("Versão disponível:", nova)
    if a.verificar:
        return 0
    if nova == versao_local() and not a.sim:
        if input("Mesma versão. Reaplicar mesmo assim? (s/N) ").strip().lower() != "s":
            return 0
    elif not a.sim and input("Aplicar atualização? Seus dados serão preservados. (s/N) ").strip().lower() != "s":
        return 0
    return aplicar(dados, a.testar)


if __name__ == "__main__":
    sys.exit(main())
