"""Difusão: % dos subitens com variação mensal positiva (#44).

Por mês, no geral e em cada grupo:

- simples: subitens com variação > 0 / subitens coletados;
- ponderada: soma dos pesos dos subitens com variação > 0 / soma dos pesos.

Os subitens são os da tabela do mês (a cesta da POF vigente); a difusão não depende de série
longa. A troca de cesta aparece em `versao_pof` e em `cesta_nova` (primeiro mês da POF).

Subitem com peso 0 está fora de coleta (fora de safra nos in natura da 1646, A-013): a variação
publicada (em geral 0,00) não informa preço, por isso ele sai dos dois denominadores e é contado
em `subitens_peso_zero` (A-026).

Uso:

    uv run python -m macroaf.indicators.difusao   # grava difusao_<indice> no staging
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from macroaf.catalogo import RAIZ, carregar_catalogo
from macroaf.transform.harmonizacao import caminho_serie_longa
from macroaf.transform.ipca15 import diretorio_staging

NIVEL_SUBITEM = "subitem"


def montar_difusao(longa: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por mês e recorte (geral = "0" ou código do grupo)."""
    subitens = longa[
        (longa.nivel_hierarquico == NIVEL_SUBITEM) & longa.variacao_mensal.notna()
    ].assign(
        coletado=lambda d: d.peso > 0,
        positivo=lambda d: (d.variacao_mensal > 0) & (d.peso > 0),
    )
    subitens = subitens.assign(peso_positivo=subitens.peso.where(subitens.positivo, 0.0))
    recortes = [subitens.assign(recorte="0"), subitens.assign(recorte=subitens.codigo_ibge.str[0])]
    dados = pd.concat(recortes, ignore_index=True)
    chave = ["mes", "tabela_sidra", "versao_pof", "recorte"]
    resultado = dados.groupby(chave, as_index=False).agg(
        subitens=("coletado", "sum"),
        subitens_peso_zero=("coletado", lambda c: int((~c).sum())),
        positivos=("positivo", "sum"),
        peso=("peso", "sum"),
        peso_positivo=("peso_positivo", "sum"),
    )
    resultado["difusao_simples"] = resultado.positivos / resultado.subitens * 100
    resultado["difusao_ponderada"] = resultado.peso_positivo / resultado.peso * 100
    primeiro_mes = resultado.groupby("versao_pof").mes.transform("min")
    resultado["cesta_nova"] = (resultado.mes == primeiro_mes) & (
        resultado.mes != resultado.mes.min()
    )
    return resultado.rename(columns={"recorte": "codigo_ibge"}).drop(columns="peso_positivo")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calcula a difusão.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    catalogo_indice = carregar_catalogo().indices[args.indice]
    difusao = montar_difusao(pd.read_parquet(caminho_serie_longa(catalogo_indice)))
    destino = diretorio_staging(catalogo_indice) / f"difusao_{catalogo_indice.codigo}.parquet"
    difusao.to_parquet(destino, index=False)
    print(f"{len(difusao)} linhas em {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
