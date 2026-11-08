"""Gemini (Google) opcional, para a parceria institucional da Polícia Civil.

Desligado por padrão. Só envia dados se houver chave, confirmação de envio e o analista
escolher um modelo gemini: no chat. A chave fica em dados/gemini.json (fora do Git) ou
na variável ANALISE_GEMINI_CHAVE. O destino é só HTTPS em googleapis.com (ou 127.0.0.1
nos testes).
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

ENDPOINT_PADRAO = "https://generativelanguage.googleapis.com/v1beta"
MODELOS_PADRAO = (
    "gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash",
    "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro",
)
RE_MODELO_SUGERIDO = re.compile(
    r"(?:use|using)\s+models/([\w.-]+)|models/(gemini-[\w.-]+)\s+for the latest", re.I)
NOME_ARQ = "gemini.json"


def _host_ok(hostname):
    h = (hostname or "").lower()
    if h == "generativelanguage.googleapis.com":
        return True
    if h == "aiplatform.googleapis.com" or h.endswith("-aiplatform.googleapis.com"):
        return True
    if h == "127.0.0.1" and os.environ.get("ANALISE_GEMINI_TESTE"):
        return True
    return False


def validar_url(url):
    u = urllib.parse.urlsplit(url)
    if u.username or u.password:
        raise ErroIA("Endereço do Gemini recusado.")
    if not _host_ok(u.hostname):
        raise ErroIA("Endereço do Gemini recusado: somente Google (generativelanguage.googleapis.com "
                     "ou *-aiplatform.googleapis.com), para a parceria institucional.")
    if u.hostname == "127.0.0.1":
        if u.scheme != "http":
            raise ErroIA("teste Gemini: use http://127.0.0.1")
    elif u.scheme != "https":
        raise ErroIA("Gemini só é chamado por HTTPS.")
    return url


def caminho_config(pasta):
    return os.path.join(pasta, NOME_ARQ)


def _ler_arquivo(pasta):
    p = caminho_config(pasta) if pasta else None
    if not p or not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _mascara(chave):
    c = (chave or "").strip()
    if len(c) < 8:
        return "(definida)" if c else ""
    return "…" + c[-4:]


def configuracao(pasta):
    arq = _ler_arquivo(pasta)
    env_chave = (os.environ.get("ANALISE_GEMINI_CHAVE") or "").strip()
    env_modelo = (os.environ.get("ANALISE_GEMINI_MODELO") or "").strip()
    env_endpoint = (os.environ.get("ANALISE_GEMINI_ENDPOINT") or "").strip()
    chave = env_chave or (arq.get("chave") or "").strip()
    return {
        "chave": chave,
        "origem": "ambiente" if env_chave else ("arquivo" if arq.get("chave") else None),
        "modelo": env_modelo or arq.get("modelo") or MODELOS_PADRAO[0],
        "endpoint": env_endpoint or arq.get("endpoint") or ENDPOINT_PADRAO,
        "confirmado": bool(arq.get("confirmado")) or bool(env_chave),
        "atualizado_em": arq.get("atualizado_em"),
        "configurado": bool(chave),
        "chave_mascarada": _mascara(chave) if chave else "",
    }


def status(pasta):
    c = configuracao(pasta)
    c.pop("chave", None)
    c["modelos"] = list(MODELOS_PADRAO)
    c["aviso"] = ("Gemini envia trechos do caso (totais, amostra de lançamentos, texto de BO/relatório) aos "
                  "servidores do Google. Use só com autorização da unidade e chave da parceria institucional. "
                  "A análise preliminar automática continua neste computador.")
    return c


def salvar(pasta, usuario, chave=None, modelo=None, endpoint=None, confirmado=None, remover=False):
    if not pasta:
        raise ErroIA("pasta de dados indisponível")
    os.makedirs(pasta, exist_ok=True)
    atual = _ler_arquivo(pasta)
    if remover:
        if os.path.isfile(caminho_config(pasta)):
            os.remove(caminho_config(pasta))
        return status(pasta)
    if chave is not None:
        chave = str(chave).strip()
        if chave:
            atual["chave"] = chave
        elif "chave" not in atual:
            raise ErroIA("Informe a chave da API do Gemini (ou defina ANALISE_GEMINI_CHAVE).")
    if modelo:
        atual["modelo"] = str(modelo).strip().split("gemini:", 1)[-1]
    if endpoint is not None:
        ep = str(endpoint).strip()
        if ep:
            validar_url(ep)
            atual["endpoint"] = ep.rstrip("/")
        else:
            atual.pop("endpoint", None)
    if confirmado is not None:
        atual["confirmado"] = bool(confirmado)
    if not atual.get("confirmado") and not os.environ.get("ANALISE_GEMINI_CHAVE"):
        raise ErroIA("Marque a autorização de envio dos dados do caso ao Gemini (parceria institucional).")
    if not ((atual.get("chave") or os.environ.get("ANALISE_GEMINI_CHAVE") or "").strip()):
        raise ErroIA("Informe a chave da API do Gemini (ou defina ANALISE_GEMINI_CHAVE).")
    atual["atualizado_em"] = util.agora_iso()
    atual["atualizado_por"] = usuario
    tmp = caminho_config(pasta) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(atual, f, ensure_ascii=False, indent=2)
    os.replace(tmp, caminho_config(pasta))
    try:
        os.chmod(caminho_config(pasta), 0o600)
    except OSError:
        pass
    return status(pasta)


def _opener():
    ctx = ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.ProxyHandler())


def _req(url, corpo=None, chave=None, timeout=120):
    url = validar_url(url)
    u = urllib.parse.urlsplit(url)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if chave and u.hostname and u.hostname.endswith("googleapis.com"):
        if "key=" not in url:
            headers["x-goog-api-key"] = chave
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(url, data=dados, headers=headers, method="POST" if dados is not None else "GET")
    try:
        with _opener().open(req, timeout=timeout) as r:
            bruto = r.read().decode("utf-8")
            return json.loads(bruto) if bruto else {}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
            msg = ((err.get("error") or {}).get("message") or str(err))[:400]
        except (ValueError, UnicodeError):
            msg = str(e)
        raise ErroIA("Gemini recusou a requisição (%s): %s" % (e.code, msg))
    except urllib.error.URLError as e:
        raise ErroIA("Não foi possível alcançar o Gemini (%s). Verifique internet, proxy da unidade e a chave."
                     % (getattr(e, "reason", None) or "falha de rede"))


def _endpoint(cfg):
    return (cfg.get("endpoint") or ENDPOINT_PADRAO).rstrip("/")


def _vertex(endpoint):
    return "aiplatform.googleapis.com" in urllib.parse.urlsplit(endpoint).netloc


def _nome_modelo(modelo):
    nome = (modelo or "").strip().split("gemini:", 1)[-1].replace("models/", "").strip()
    if not re.match(r"^[\w.-]{3,80}$", nome):
        raise ErroIA("modelo Gemini inválido")
    return nome


def _juntar_modelos(*listas):
    out = []
    for lista in listas:
        for n in lista or []:
            n = (n or "").strip()
            if n and n not in out:
                out.append(n)
    return out


def _modelo_sugerido_erro(msg, atual):
    """Se a API disser que o modelo saiu de linha, devolve o substituto indicado."""
    txt = msg or ""
    m = RE_MODELO_SUGERIDO.search(txt)
    if m:
        nome = (m.group(1) or m.group(2) or "").replace("models/", "").strip()
        if nome and nome != atual and re.match(r"^[\w.-]{3,80}$", nome):
            return nome
    if "no longer available" in txt.lower() and MODELOS_PADRAO[0] != atual:
        return MODELOS_PADRAO[0]
    return None


def _persistir_modelo(pasta, modelo):
    if not pasta or os.environ.get("ANALISE_GEMINI_MODELO"):
        return
    atual = _ler_arquivo(pasta)
    if not atual:
        return
    try:
        atual["modelo"] = _nome_modelo(modelo)
    except ErroIA:
        return
    atual["atualizado_em"] = util.agora_iso()
    tmp = caminho_config(pasta) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(atual, f, ensure_ascii=False, indent=2)
    os.replace(tmp, caminho_config(pasta))
    try:
        os.chmod(caminho_config(pasta), 0o600)
    except OSError:
        pass


def _url_gerar(cfg, modelo):
    ep, chave = _endpoint(cfg), cfg["chave"]
    modelo = _nome_modelo(modelo or cfg["modelo"] or MODELOS_PADRAO[0])
    if _vertex(ep):
        url = "%s/publishers/google/models/%s:generateContent" % (ep, urllib.parse.quote(modelo, safe=".-"))
    else:
        url = "%s/models/%s:generateContent" % (ep, urllib.parse.quote(modelo, safe=".-"))
    if chave and not _vertex(ep):
        sep = "&" if "?" in url else "?"
        url = url + sep + "key=" + urllib.parse.quote(chave, safe="")
    return url, modelo


def listar_modelos(pasta):
    cfg = configuracao(pasta)
    out = list(MODELOS_PADRAO)
    if not cfg["chave"]:
        return out
    try:
        ep = _endpoint(cfg)
        if _vertex(ep):
            return out
        url = ep + "/models"
        if cfg["chave"]:
            url += "?key=" + urllib.parse.quote(cfg["chave"], safe="")
        dados = _req(url, chave=cfg["chave"], timeout=20)
        nomes = []
        for m in dados.get("models") or []:
            metodos = m.get("supportedGenerationMethods") or m.get("supported_generation_methods") or []
            if metodos and "generateContent" not in metodos:
                continue
            nome = (m.get("name") or "").split("/")[-1]
            if nome.startswith("gemini"):
                nomes.append(nome)
        if nomes:
            return _juntar_modelos(MODELOS_PADRAO, nomes)
    except ErroIA:
        pass
    return out


def gerar(pasta, modelo, sistema, mensagens, timeout=180, _retentou=False):
    cfg = configuracao(pasta)
    if not cfg["chave"]:
        raise ErroIA("Gemini não configurado. Cole a chave da parceria na aba IA ou defina ANALISE_GEMINI_CHAVE.")
    if not cfg["confirmado"]:
        raise ErroIA("Autorize o envio ao Gemini (caixa de confirmação) antes de usar a nuvem.")
    url, modelo = _url_gerar(cfg, modelo)
    contents = []
    for m in mensagens:
        papel = m.get("role")
        if papel == "system":
            continue
        role = "model" if papel in ("assistant", "model") else "user"
        contents.append({"role": role, "parts": [{"text": m.get("content") or ""}]})
    if not contents:
        raise ErroIA("nada para enviar ao Gemini")
    if contents[0].get("role") != "user":
        contents.insert(0, {"role": "user", "parts": [{"text": "(início da conversa)"}]})
    corpo = {
        "systemInstruction": {"parts": [{"text": sistema or ""}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
    }
    try:
        resp = _req(url, corpo, chave=cfg["chave"], timeout=timeout)
    except ErroIA as e:
        alt = None if _retentou else _modelo_sugerido_erro(str(e), modelo)
        if alt:
            texto, meta = gerar(pasta, alt, sistema, mensagens, timeout=timeout, _retentou=True)
            _persistir_modelo(pasta, alt)
            return texto, meta
        raise
    if (resp.get("promptFeedback") or {}).get("blockReason"):
        raise ErroIA("Gemini bloqueou o prompt (%s)." % resp["promptFeedback"]["blockReason"])
    cands = resp.get("candidates") or []
    if not cands:
        raise ErroIA("Gemini não devolveu candidatos. %s" % ((resp.get("error") or {}).get("message") or ""))
    parts = ((cands[0].get("content") or {}).get("parts") or [])
    texto = "".join(p.get("text") or "" for p in parts).strip()
    if not texto:
        raise ErroIA("Gemini devolveu resposta vazia.")
    return texto, {"provedor": "gemini", "modelo": modelo, "endpoint": urllib.parse.urlsplit(url).netloc}


def testar(pasta):
    """Chamada curta, sem dados de caso, só para conferir chave e rede."""
    texto, meta = gerar(
        pasta, None, "Responda exatamente com a palavra ok.",
        [{"role": "user", "content": "Responda exatamente com a palavra ok."}], timeout=45)
    return {"ok": True, "resposta": (texto or "")[:200], "meta": meta}
