"""ChatGPT (OpenAI) e Claude (Anthropic) opcionais, no mesmo espírito do Gemini.

Chaves em dados/chatgpt.json e dados/claude.json (fora do Git) ou nas variáveis
ANALISE_CHATGPT_CHAVE / ANALISE_CLAUDE_CHAVE. Destino só HTTPS nos hosts oficiais
(ou 127.0.0.1 nos testes).
"""

import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from . import util
from .ia import ErroIA

PROVEDORES = {
    "chatgpt": {
        "rotulo": "ChatGPT",
        "arquivo": "chatgpt.json",
        "env": "ANALISE_CHATGPT_CHAVE",
        "endpoint": "https://api.openai.com/v1",
        "hosts": ("api.openai.com",),
        "modelos": ("gpt-4.1-mini", "gpt-4o-mini", "gpt-4o"),
    },
    "claude": {
        "rotulo": "Claude",
        "arquivo": "claude.json",
        "env": "ANALISE_CLAUDE_CHAVE",
        "endpoint": "https://api.anthropic.com/v1",
        "hosts": ("api.anthropic.com",),
        "modelos": ("claude-sonnet-4-5", "claude-sonnet-4-0", "claude-3-5-haiku-latest"),
    },
}


def _host_ok(hostname, hosts):
    h = (hostname or "").lower()
    if h in hosts:
        return True
    if h == "127.0.0.1" and os.environ.get("ANALISE_NUVEM_TESTE"):
        return True
    return False


def validar_url(url, hosts):
    u = urllib.parse.urlsplit(url)
    if u.username or u.password:
        raise ErroIA("Endereço da IA recusado.")
    if not _host_ok(u.hostname, hosts):
        raise ErroIA("Endereço da IA recusado: use só o site oficial do serviço.")
    if u.hostname == "127.0.0.1":
        if u.scheme != "http":
            raise ErroIA("teste: use http://127.0.0.1")
    elif u.scheme != "https":
        raise ErroIA("A IA na nuvem só é chamada por HTTPS.")
    return url


def _mascara(chave):
    c = (chave or "").strip()
    if len(c) < 8:
        return "(definida)" if c else ""
    return "…" + c[-4:]


def _ler(pasta, spec):
    p = os.path.join(pasta, spec["arquivo"]) if pasta else None
    if not p or not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _spec(provedor):
    if provedor not in PROVEDORES:
        raise ErroIA("Serviço de IA desconhecido.")
    return PROVEDORES[provedor]


def configuracao(pasta, provedor):
    spec = _spec(provedor)
    arq = _ler(pasta, spec)
    env_chave = (os.environ.get(spec["env"]) or "").strip()
    chave = env_chave or (arq.get("chave") or "").strip()
    return {
        "provedor": provedor,
        "rotulo": spec["rotulo"],
        "chave": chave,
        "origem": "ambiente" if env_chave else ("arquivo" if arq.get("chave") else None),
        "modelo": (arq.get("modelo") or spec["modelos"][0]),
        "endpoint": arq.get("endpoint") or spec["endpoint"],
        "confirmado": bool(arq.get("confirmado")) or bool(env_chave),
        "configurado": bool(chave),
        "chave_mascarada": _mascara(chave) if chave else "",
        "modelos": list(spec["modelos"]),
    }


def status(pasta, provedor):
    c = configuracao(pasta, provedor)
    c.pop("chave", None)
    return c


def status_todos(pasta):
    return {p: status(pasta, p) for p in PROVEDORES}


def salvar(pasta, usuario, provedor, chave=None, modelo=None, remover=False):
    spec = _spec(provedor)
    if not pasta:
        raise ErroIA("pasta de dados indisponível")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, spec["arquivo"])
    if remover:
        if os.path.isfile(caminho):
            os.remove(caminho)
        return status(pasta, provedor)
    atual = _ler(pasta, spec)
    if chave is not None:
        chave = str(chave).strip()
        if chave:
            atual["chave"] = chave
        elif "chave" not in atual:
            raise ErroIA("Cole a chave do %s." % spec["rotulo"])
    if modelo:
        atual["modelo"] = str(modelo).strip().split(provedor + ":", 1)[-1]
    atual["confirmado"] = True
    if not ((atual.get("chave") or os.environ.get(spec["env"]) or "").strip()):
        raise ErroIA("Cole a chave do %s." % spec["rotulo"])
    atual["atualizado_em"] = util.agora_iso()
    atual["atualizado_por"] = usuario
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(atual, f, ensure_ascii=False, indent=2)
    os.replace(tmp, caminho)
    try:
        os.chmod(caminho, 0o600)
    except OSError:
        pass
    return status(pasta, provedor)


def _opener():
    ctx = ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.ProxyHandler())


def _req(url, corpo, headers, hosts, timeout=120):
    url = validar_url(url, hosts)
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=dados, headers=h, method="POST" if dados is not None else "GET")
    try:
        with _opener().open(req, timeout=timeout) as r:
            bruto = r.read().decode("utf-8")
            return json.loads(bruto) if bruto else {}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
            msg = ((err.get("error") or {}).get("message") or err.get("error") or str(err))
            if isinstance(msg, dict):
                msg = msg.get("message") or str(msg)
            msg = str(msg)[:400]
        except (ValueError, UnicodeError):
            msg = str(e)
        raise ErroIA("%s recusou a requisição (%s): %s" % (urllib.parse.urlsplit(url).hostname, e.code, msg))
    except urllib.error.URLError as e:
        raise ErroIA("Não foi possível alcançar a IA (%s). Verifique a internet e a chave."
                     % (getattr(e, "reason", None) or "falha de rede"))


def _nome_modelo(modelo, spec):
    nome = (modelo or "").strip()
    for pref in ("chatgpt:", "claude:", "openai:"):
        if nome.startswith(pref):
            nome = nome.split(":", 1)[-1]
    nome = nome.strip()
    if not re.match(r"^[\w.-]{3,80}$", nome):
        raise ErroIA("modelo inválido")
    return nome


def gerar(pasta, provedor, modelo, sistema, mensagens, timeout=180):
    spec = _spec(provedor)
    cfg = configuracao(pasta, provedor)
    if not cfg["chave"]:
        raise ErroIA("%s não configurado. Cole a chave na aba Análise." % spec["rotulo"])
    modelo = _nome_modelo(modelo or cfg["modelo"], spec)
    contents = []
    for m in mensagens:
        papel = m.get("role")
        if papel == "system":
            continue
        role = "assistant" if papel in ("assistant", "model") else "user"
        contents.append({"role": role, "content": m.get("content") or ""})
    if not contents:
        raise ErroIA("nada para enviar")
    if contents[0]["role"] != "user":
        contents.insert(0, {"role": "user", "content": "(início da conversa)"})
    ep = (cfg.get("endpoint") or spec["endpoint"]).rstrip("/")
    if provedor == "chatgpt":
        url = ep + "/chat/completions"
        corpo = {"model": modelo, "temperature": 0.1, "messages":
                 ([{"role": "system", "content": sistema or ""}] if sistema else []) + contents}
        headers = {"Authorization": "Bearer " + cfg["chave"]}
    else:
        url = ep + "/messages"
        corpo = {"model": modelo, "max_tokens": 8192, "temperature": 0.1,
                 "system": sistema or "", "messages": contents}
        headers = {"x-api-key": cfg["chave"], "anthropic-version": "2023-06-01"}
    resp = _req(url, corpo, headers, spec["hosts"], timeout=timeout)
    if provedor == "chatgpt":
        escolhas = resp.get("choices") or []
        if not escolhas:
            raise ErroIA("ChatGPT não devolveu resposta.")
        texto = (((escolhas[0].get("message") or {}).get("content")) or "").strip()
    else:
        parts = resp.get("content") or []
        texto = "".join(p.get("text") or "" for p in parts if isinstance(p, dict)).strip()
    if not texto:
        raise ErroIA("%s devolveu resposta vazia." % spec["rotulo"])
    return texto, {"provedor": provedor, "modelo": modelo, "endpoint": urllib.parse.urlsplit(url).netloc}


def testar(pasta, provedor):
    texto, meta = gerar(
        pasta, provedor, None, "Responda exatamente com a palavra ok.",
        [{"role": "user", "content": "Responda exatamente com a palavra ok."}], timeout=45)
    return {"ok": True, "resposta": (texto or "")[:200], "meta": meta}
