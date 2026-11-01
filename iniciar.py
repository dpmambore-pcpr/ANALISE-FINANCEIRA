"""Inicia a Análise Bancária Local (Windows/Linux, Python portátil ou instalado)."""

import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
# O Python portátil do Windows (._pth) não inclui a pasta do script no sys.path.
sys.path.insert(0, RAIZ)

if sys.version_info < (3, 9):
    sys.exit("É necessário Python 3.9 ou superior. Use o runtime incluído no pacote.")

from financeira import servidor  # noqa: E402

if __name__ == "__main__":
    servidor.main()
