#!/usr/bin/env bash
# Ollama portátil: somente 127.0.0.1, nuvem desativada e modelos dentro da pasta da aplicação.
set -e
cd "$(dirname "$0")"
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_NO_CLOUD=1
export OLLAMA_MODELS="$PWD/modelos_ollama"
mkdir -p "$OLLAMA_MODELS"
if [ -x ollama/bin/ollama ]; then OLL=ollama/bin/ollama
elif command -v ollama >/dev/null 2>&1; then OLL=ollama
else echo "Ollama não encontrado em ollama/bin/ollama. Veja docs/IA_LOCAL.md."; exit 1; fi
echo "Mantenha este terminal aberto. Modelos em $OLLAMA_MODELS"
exec "$OLL" serve
