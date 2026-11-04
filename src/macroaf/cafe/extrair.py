"""Comando de coleta do piloto do café: câmbio (BCB), FMI e Banco Mundial para o raw.

    uv run python -m macroaf.cafe.extrair              # baixa o que falta ou mudou
    uv run python -m macroaf.cafe.extrair --verificar  # só diz o que falta ou mudou

Idempotente: uma segunda execução sem novidade nas fontes não grava nada.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from macroaf.cafe.configuracao import carregar
from macroaf.cafe.fontes import coletar_banco_mundial, coletar_fmi, coletar_sgs
from macroaf.extract.cliente import Cliente


def extrair(verificar: bool = False, hoje: date | None = None, raiz=None) -> list:
    configuracao = carregar()
    hoje = hoje or date.today()
    with Cliente() as cliente:
        resultado = coletar_sgs(configuracao, cliente, hoje, raiz, verificar)
        resultado += coletar_fmi(configuracao, cliente, raiz, verificar)
        resultado += coletar_banco_mundial(configuracao, cliente, raiz, verificar)
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verificar", action="store_true", help="não grava; só lista")
    args = parser.parse_args(argv)
    resultado = extrair(verificar=args.verificar)
    if not resultado:
        print("Nada novo nas fontes de preços.")
        return 0
    for item in resultado:
        print(item if isinstance(item, str) else f"gravado: {item.arquivo} ({item.n_registros})")
    print(f"{len(resultado)} {'pendências' if args.verificar else 'arquivos gravados'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
