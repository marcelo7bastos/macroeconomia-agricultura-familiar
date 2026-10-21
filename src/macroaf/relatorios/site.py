"""Monta a árvore estática do GitHub Pages, sem raw ou credenciais."""

import argparse
import shutil
from pathlib import Path

from macroaf.catalogo import RAIZ
from macroaf.relatorios import gestao


def montar(destino: Path) -> None:
    if destino.exists() and any(destino.iterdir()):
        raise ValueError("Use um diretório vazio para não sobrescrever arquivos alheios")
    if gestao.main(["--verificar"]):
        raise ValueError("Regere as explicações antes de publicar")
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        RAIZ / "docs",
        destino / "docs",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(RAIZ / "data" / "marts", destino / "data" / "marts")
    shutil.copy2(RAIZ / "data" / "metadata.json", destino / "data" / "metadata.json")
    shutil.copytree(RAIZ / "reference", destino / "reference")
    for nome in ("README.md", "AGENTS.md", "CHANGELOG.md", "LICENSE", "LICENSE-DADOS.md"):
        shutil.copy2(RAIZ / nome, destino / nome)
    (destino / ".nojekyll").touch()
    (destino / "index.html").write_text(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="0;url=docs/gestao/ipca.html">'
        '<title>Inflação para gestores</title><p><a href="docs/gestao/ipca.html">'
        'Abrir IPCA geral</a> · <a href="docs/gestao/ipca15.html">IPCA-15</a></p></html>'
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destino", type=Path, required=True)
    args = parser.parse_args(argv)
    montar(args.destino)
    print(f"Site estático montado em {args.destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
