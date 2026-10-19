"""`dim_classificacao`: categorias da classificação 315 por tabela, hierarquia pelo código IBGE.

A hierarquia sai do código IBGE no nome da categoria (`1101002.Arroz`): 1 dígito = grupo,
2 = subgrupo, 4 = item, 7 = subitem. O campo `nivel` dos metadados **não é usado**: a numeração
muda entre tabelas e há subitem com `nivel = 0` na 1387 (lições A-001 e A-010).

O índice geral não tem código no nome; recebe o código `0` por convenção do projeto, para que
toda categoria tenha chave e todo grupo tenha pai.

Uso:

    uv run python -m macroaf.transform.classificacao     # grava o staging do IPCA-15
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from macroaf.catalogo import RAIZ, Indice, Tabela, carregar_catalogo
from macroaf.extract.raw import METADADOS, ArmazemRaw

CODIGO_GERAL = "0"
NOME_GERAL = "Índice geral"
NIVEL_POR_DIGITOS = {1: "grupo", 2: "subgrupo", 4: "item", 7: "subitem"}
DIGITOS_DO_PAI = {1: 0, 2: 1, 4: 2, 7: 4}
NIVEIS = ["geral", "grupo", "subgrupo", "item", "subitem"]
_PADRAO_NOME = re.compile(r"^(\d+)\.(.+)$")

COLUNAS = [
    "versao_pof",
    "tabela_sidra",
    "codigo_sidra",
    "codigo_ibge",
    "nome",
    "nivel_hierarquico",
    "codigo_pai",
    "grupo",
    "subgrupo",
    "item",
]

ESQUEMA = pa.DataFrameSchema(
    {
        "versao_pof": pa.Column(str),
        "tabela_sidra": pa.Column(int),
        "codigo_sidra": pa.Column(int),
        "codigo_ibge": pa.Column(str, pa.Check.str_matches(r"^(0|\d|\d{2}|\d{4}|\d{7})$")),
        "nome": pa.Column(str, pa.Check.str_length(min_value=1)),
        "nivel_hierarquico": pa.Column(str, pa.Check.isin(NIVEIS)),
        "codigo_pai": pa.Column(str, nullable=True),
        "grupo": pa.Column(str, nullable=True),
        "subgrupo": pa.Column(str, nullable=True),
        "item": pa.Column(str, nullable=True),
    },
    unique=["tabela_sidra", "codigo_ibge"],
    strict=True,
    ordered=True,
)


class ErroClassificacao(ValueError):
    """A classificação da tabela não segue o padrão esperado."""


def separar_codigo(nome_sidra: str) -> tuple[str, str]:
    """`1101002.Arroz` → (`1101002`, `Arroz`); `Índice geral` → (`0`, `Índice geral`)."""
    correspondencia = _PADRAO_NOME.match(nome_sidra)
    if correspondencia:
        codigo, nome = correspondencia.groups()
        if len(codigo) not in NIVEL_POR_DIGITOS:
            raise ErroClassificacao(f"código com {len(codigo)} dígitos: {nome_sidra!r}")
        return codigo, nome.strip()
    if nome_sidra.strip() == NOME_GERAL:
        return CODIGO_GERAL, NOME_GERAL
    raise ErroClassificacao(f"categoria sem código IBGE: {nome_sidra!r}")


def _no_nivel(codigo: str, digitos: int) -> str | None:
    """Código do grupo/subgrupo/item a que a categoria pertence (ela mesma, se for desse nível)."""
    if codigo == CODIGO_GERAL or len(codigo) < digitos:
        return None
    return codigo[:digitos]


def classificacao_da_tabela(metadados: dict, tabela: Tabela) -> list[dict]:
    """Linhas de `dim_classificacao` de uma tabela, a partir dos metadados guardados no raw."""
    contexto = f"tabela {tabela.tabela}"
    classificacoes = [c for c in metadados.get("classificacoes", []) if c.get("id") == 315]
    if len(classificacoes) != 1:
        raise ErroClassificacao(f"{contexto}: classificação 315 ausente nos metadados")

    linhas = []
    for categoria in classificacoes[0]["categorias"]:
        codigo, nome = separar_codigo(categoria["nome"])
        if codigo == CODIGO_GERAL:
            nivel, pai = "geral", None
        else:
            nivel = NIVEL_POR_DIGITOS[len(codigo)]
            digitos_pai = DIGITOS_DO_PAI[len(codigo)]
            pai = CODIGO_GERAL if digitos_pai == 0 else codigo[:digitos_pai]
        linhas.append(
            {
                "versao_pof": tabela.versao_pof,
                "tabela_sidra": tabela.tabela,
                "codigo_sidra": int(categoria["id"]),
                "codigo_ibge": codigo,
                "nome": nome,
                "nivel_hierarquico": nivel,
                "codigo_pai": pai,
                "grupo": _no_nivel(codigo, 1),
                "subgrupo": _no_nivel(codigo, 2),
                "item": _no_nivel(codigo, 4),
            }
        )

    codigos = [linha["codigo_ibge"] for linha in linhas]
    repetidos = sorted({c for c in codigos if codigos.count(c) > 1})
    if repetidos:
        raise ErroClassificacao(f"{contexto}: códigos IBGE repetidos: {repetidos}")
    if CODIGO_GERAL not in codigos:
        raise ErroClassificacao(f"{contexto}: sem o índice geral")
    existentes = set(codigos)
    orfaos = sorted(
        linha["codigo_ibge"] for linha in linhas if linha["codigo_pai"] not in existentes | {None}
    )
    if orfaos:
        raise ErroClassificacao(f"{contexto}: categorias sem pai na tabela: {orfaos}")
    return linhas


def montar_dim_classificacao(indice: Indice, armazem: ArmazemRaw) -> pd.DataFrame:
    """`dim_classificacao` de todas as tabelas de dados classificadas do índice."""
    linhas = []
    for tabela in indice.tabelas_dados:
        if tabela.classificacao is None:
            continue
        arquivo = armazem.vigente(tabela.tabela, METADADOS)
        if arquivo is None:
            raise ErroClassificacao(
                f"tabela {tabela.tabela}: metadados ausentes no raw "
                "(rode `python -m macroaf.extract.atualizar`)"
            )
        metadados = json.loads(armazem.ler(arquivo))
        linhas += classificacao_da_tabela(metadados, tabela)
    tabela_final = pd.DataFrame(linhas, columns=COLUNAS)
    for coluna in ["codigo_pai", "grupo", "subgrupo", "item"]:
        tabela_final[coluna] = tabela_final[coluna].astype(object)
    return ESQUEMA.validate(tabela_final)


def caminho_staging(indice: Indice) -> Path:
    return RAIZ / "data" / "staging" / indice.codigo / "dim_classificacao.parquet"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monta dim_classificacao a partir do raw.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    catalogo = carregar_catalogo()
    indice = catalogo.indices[args.indice]
    try:
        dim = montar_dim_classificacao(indice, ArmazemRaw(indice.fonte))
    except ErroClassificacao as erro:
        print(f"erro na classificação: {erro}", file=sys.stderr)
        return 1
    destino = caminho_staging(indice)
    destino.parent.mkdir(parents=True, exist_ok=True)
    dim.to_parquet(destino, index=False)
    contagem = dim.groupby(["tabela_sidra", "nivel_hierarquico"]).size().unstack(fill_value=0)
    print(contagem[NIVEIS].to_string())
    print(f"{len(dim)} categorias gravadas em {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
