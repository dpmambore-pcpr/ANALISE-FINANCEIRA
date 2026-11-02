#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ -x runtime_linux/bin/python3 ]; then PY=runtime_linux/bin/python3
elif command -v python3 >/dev/null 2>&1; then PY=python3
else echo "Python 3 não encontrado. Veja README.md."; exit 1; fi
exec "$PY" iniciar.py "$@"
