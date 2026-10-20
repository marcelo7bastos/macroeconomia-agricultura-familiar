"""Sazonalidade: média e mediana da variação por mês do ano, em janela móvel (#44).

Para cada série longa e mês do ano, média e mediana da variação mensal nos últimos `ANOS` anos
(janela móvel que termina em cada ano). A janela só usa anos seguidos da própria série: se falta
um ano, aquele mês do ano fica sem valor (decisão 0005). `cesta_variavel` marca a janela com mês
de cesta variável (A-013).

Uso:

    uv run python -m macroaf.indicators.sazonalidade   # grava sazonalidade_<indice> no staging
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from macroaf.catalogo import RAIZ, carregar_catalogo
from macroaf.indicators.indice import caminho_indice
from macroaf.transform.ipca15 import diretorio_staging

ANOS = 5
COLUNAS = [
    "serie_id",
    "codigo_ibge",
    "nivel_hierarquico",
    "mes_do_ano",
    "ano_final",
    "media",
    "mediana",
    "cesta_variavel",
]


def montar_sazonalidade(indice: pd.DataFrame, anos: int = ANOS) -> pd.DataFrame:
    """Média e mediana da variação de cada mês do ano nos `anos` anos até cada ano, por série."""
    dados = indice.assign(ano=indice.mes.str[:4].astype(int), mes_do_ano=indice.mes.str[5:])
    dados = dados.sort_values(["serie_id", "mes_do_ano", "ano"])
    chave = ["serie_id", "mes_do_ano"]
    moveis = dados.groupby(chave).variacao_mensal.rolling(anos)
    dados["media"] = moveis.mean().reset_index(level=chave, drop=True)
    dados["mediana"] = moveis.median().reset_index(level=chave, drop=True)
    # Anos seguidos: a janela não pode pular um ano que falta na série.
    primeiro_ano = dados.groupby(chave).ano.shift(anos - 1)
    consecutivos = dados.ano - primeiro_ano == anos - 1
    dados["cesta_variavel"] = (
        dados.cesta_variavel.astype(int)
        .groupby([dados.serie_id, dados.mes_do_ano])
        .rolling(anos, min_periods=1)
        .max()
        .reset_index(level=chave, drop=True)
        .astype(bool)
    )
    resultado = dados[consecutivos & dados.media.notna()].rename(columns={"ano": "ano_final"})
    return resultado[COLUNAS].reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calcula a sazonalidade por série longa.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    catalogo_indice = carregar_catalogo().indices[args.indice]
    sazonalidade = montar_sazonalidade(pd.read_parquet(caminho_indice(catalogo_indice)))
    destino = diretorio_staging(catalogo_indice) / f"sazonalidade_{catalogo_indice.codigo}.parquet"
    sazonalidade.to_parquet(destino, index=False)
    print(f"{len(sazonalidade)} linhas em {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
