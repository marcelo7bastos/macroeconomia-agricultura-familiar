"""Difusão e sazonalidade (#44).

**Difusão:** % dos subitens com variação mensal positiva, por mês, no geral e em cada grupo:

- simples: subitens com variação > 0 / subitens com variação publicada;
- ponderada: soma dos pesos dos subitens com variação > 0 / soma dos pesos.

Os subitens são os da tabela do mês (a cesta da POF vigente); a difusão não depende de série
longa. Nos subitens in natura da 1646 o peso fora de safra é 0 (A-013): entram na simples e não
pesam na ponderada.

**Sazonalidade:** para cada série longa e mês do ano, média e mediana da variação mensal nos
últimos `ANOS` anos (janela móvel que termina em cada ano). A janela só usa anos da própria série:
se falta um ano na série, aquele mês do ano fica sem valor (decisão 0005).

Uso:

    uv run python -m macroaf.indicators.difusao   # grava difusao_ e sazonalidade_<indice>
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from macroaf.catalogo import RAIZ, carregar_catalogo
from macroaf.indicators.indice import caminho_indice
from macroaf.transform.harmonizacao import caminho_serie_longa
from macroaf.transform.ipca15 import diretorio_staging

ANOS = 5
NIVEL_SUBITEM = "subitem"
COLUNAS_SAZONALIDADE = [
    "serie_id",
    "codigo_ibge",
    "nivel_hierarquico",
    "mes_do_ano",
    "ano_final",
    "media",
    "mediana",
    "cesta_variavel",
]


def montar_difusao(longa: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por mês e recorte (geral = "0" ou código do grupo)."""
    subitens = longa[
        (longa.nivel_hierarquico == NIVEL_SUBITEM) & longa.variacao_mensal.notna()
    ].assign(positivo=lambda d: d.variacao_mensal > 0)
    subitens = subitens.assign(peso_positivo=subitens.peso.where(subitens.positivo, 0.0))
    recortes = [subitens.assign(recorte="0"), subitens.assign(recorte=subitens.codigo_ibge.str[0])]
    dados = pd.concat(recortes, ignore_index=True)
    resultado = dados.groupby(["mes", "tabela_sidra", "recorte"], as_index=False).agg(
        subitens=("positivo", "size"),
        positivos=("positivo", "sum"),
        peso=("peso", "sum"),
        peso_positivo=("peso_positivo", "sum"),
    )
    resultado["difusao_simples"] = resultado.positivos / resultado.subitens * 100
    resultado["difusao_ponderada"] = resultado.peso_positivo / resultado.peso * 100
    return resultado.rename(columns={"recorte": "codigo_ibge"}).drop(columns="peso_positivo")


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
    cesta = (
        dados.cesta_variavel.astype(int)
        .groupby([dados.serie_id, dados.mes_do_ano])
        .rolling(anos, min_periods=1)
        .max()
        .reset_index(level=chave, drop=True)
        .astype(bool)
    )
    dados["cesta_variavel"] = cesta
    resultado = dados[consecutivos & dados.media.notna()].rename(columns={"ano": "ano_final"})
    return resultado[COLUNAS_SAZONALIDADE].reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calcula a difusão e a sazonalidade.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    catalogo_indice = carregar_catalogo().indices[args.indice]
    pasta = diretorio_staging(catalogo_indice)
    difusao = montar_difusao(pd.read_parquet(caminho_serie_longa(catalogo_indice)))
    sazonalidade = montar_sazonalidade(pd.read_parquet(caminho_indice(catalogo_indice)))
    for nome, tabela in [("difusao", difusao), ("sazonalidade", sazonalidade)]:
        destino = pasta / f"{nome}_{catalogo_indice.codigo}.parquet"
        tabela.to_parquet(destino, index=False)
        print(f"{len(tabela)} linhas em {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
