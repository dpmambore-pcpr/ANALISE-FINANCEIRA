#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ -x runtime_linux/bin/python3 ]; then PY=runtime_linux/bin/python3; else PY=python3; fi
exec "$PY" atualizar.py --testar --sim "$@"
