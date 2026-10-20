"""Atualização completa de um índice: do IBGE aos marts, num comando só (#9).

Etapas, em ordem; a primeira que falha interrompe tudo e nada mais é escrito:

1. extração incremental do raw (meses novos e revisões dos últimos meses, decisão 0003);
2. se nada mudou no raw (e sem `--forcar`), para aqui: não há o que publicar;
3. mapa de harmonização e série longa (revisões humanas preservadas);
4. publicação dos marts, que valida e confere antes de gravar (#8);
5. páginas de transformações e de revisão regeradas.

Códigos de saída: 0 = publicado, nada novo ou IBGE ainda divulgando (tabela de dados um mês atrás
da referência, decisão 0003); 1 = falha (fonte, validação, conferência ou página); 2 = o catálogo
diverge dos metadados do IBGE (provável troca de POF: ver a issue #27).

Depois de uma falha numa execução local, o raw já tem o mês novo e o mapa pode ter mudado; a
execução seguinte diria "nada novo". Rode de novo com `--forcar`.

No GitHub Actions, escreve `publicar=true|false` em `$GITHUB_OUTPUT`.

Uso:

    uv run python -m macroaf.pipeline --indice ipca15
    uv run python -m macroaf.pipeline --indice ipca15 --forcar   # republica sem mês novo
"""

from __future__ import annotations

import argparse
import os
import sys

from macroaf.catalogo import carregar_catalogo
from macroaf.extract import atualizar
from macroaf.marts import publicar
from macroaf.relatorios import revisao, transformacoes
from macroaf.transform import harmonizacao


def _saida_github(publicado: bool) -> None:
    caminho = os.environ.get("GITHUB_OUTPUT")
    if caminho:
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(f"publicar={'true' if publicado else 'false'}\n")


def executar(codigo_indice: str, forcar: bool = False) -> int:
    codigo, relatorio = atualizar.extrair(codigo_indice)
    if codigo == 3:
        print("O IBGE ainda está publicando o mês; a próxima execução completa.")
        _saida_github(False)
        return 0
    if relatorio is None:
        if codigo == 2:
            print("Provável troca de POF: siga o roteiro da issue #27.", file=sys.stderr)
        return codigo
    print(
        f"raw: {relatorio.total_novos} mês(es) novo(s), {relatorio.total_revisados} revisado(s), "
        f"metadados alterados: {relatorio.metadados or 'nenhum'}"
    )
    if not relatorio.houve_mudanca and not forcar:
        print("Nada novo no IBGE; nada a publicar.")
        _saida_github(False)
        return 0

    return _publicar(codigo_indice)


def _publicar(codigo_indice: str) -> int:
    """Harmonização, marts e páginas, parando na primeira falha."""
    argumentos = ["--indice", codigo_indice]
    if harmonizacao.main(argumentos) != 0:
        print("Mapa de harmonização com problema; publicação interrompida.", file=sys.stderr)
        return 1
    indice = carregar_catalogo().indices[codigo_indice]
    problemas = publicar.publicar(indice)
    if problemas:
        print("Publicação bloqueada:", file=sys.stderr)
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
        return 1
    if transformacoes.main(argumentos) != 0 or revisao.main(argumentos) != 0:
        print("Falha ao regerar as páginas.", file=sys.stderr)
        return 1
    print(f"Marts de {codigo_indice} publicados.")
    _saida_github(True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atualiza um índice do IBGE até os marts.")
    parser.add_argument("--indice", default="ipca15")
    parser.add_argument(
        "--forcar", action="store_true", help="publica mesmo sem mês novo ou revisado"
    )
    args = parser.parse_args(argv)
    return executar(args.indice, forcar=args.forcar)


if __name__ == "__main__":
    sys.exit(main())
