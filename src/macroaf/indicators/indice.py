"""Índice encadeado por série longa: a base dos acumulados e das contribuições acumuladas (#41).

Para cada `serie_id` da série longa:

    I_t = I_(t-1) * (1 + v_t / 100),   com I = 100 no mês anterior ao início da série

Assim o acumulado de k meses terminado em t é `(I_t / I_(t-k) - 1) * 100`, inclusive para a
primeira janela completa da série. O índice nunca atravessa uma quebra da harmonização: cada série
começa de novo em 100 (decisão 0005). Rebase para uma data escolhida é uma divisão; só uma base é
guardada.

Os subitens com cesta variável (exceção estrutural de `acumulado_ano`, A-013) recebem
`cesta_variavel = True`: o índice é calculável, mas não reproduz os acumulados do IBGE.

Uso:

    uv run python -m macroaf.indicators.indice     # grava indice_ipca15 no staging
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from macroaf.catalogo import RAIZ, Indice, carregar_catalogo
from macroaf.transform.harmonizacao import caminho_serie_longa
from macroaf.validate.ipca15 import carregar_excecoes

BASE = 100.0
COLUNAS = [
    "serie_id",
    "mes",
    "tabela_sidra",
    "codigo_sidra",
    "codigo_ibge",
    "nivel_hierarquico",
    "variacao_mensal",
    "indice",
    "cesta_variavel",
]


def marcar_cesta_variavel(longa: pd.DataFrame, excecoes: pd.DataFrame) -> pd.Series:
    """Linhas cobertas por exceção estrutural do acumulado no ano (A-013), vinda de `reference/`."""
    marcadas = pd.Series(False, index=longa.index)
    estruturais = excecoes[
        (excecoes.tipo == "estrutural") & (excecoes.validacao == "acumulado_ano")
    ]
    for e in estruturais.itertuples():
        marcadas |= (
            (longa.tabela_sidra == e.tabela_sidra)
            & longa.codigo_ibge.str.fullmatch(e.codigo_ibge)
            & (longa.mes >= e.mes_inicio)
            & (longa.mes <= e.mes_fim)
        )
    return marcadas


def _conferir_continuidade(dados: pd.DataFrame) -> None:
    """O encadeamento e as janelas por deslocamento supõem séries sem meses faltando."""
    periodo = pd.PeriodIndex(dados.mes, freq="M")
    passo = pd.Series(periodo.asi8, index=dados.index).groupby(dados.serie_id).diff().dropna()
    if (passo != 1).any():
        raise ValueError("série longa com mês faltando ou repetido: o índice não se encadeia")


def montar_indice(longa: pd.DataFrame, cesta_variavel: pd.Series | None = None) -> pd.DataFrame:
    """Índice encadeado de cada série longa (base 100 no mês anterior ao início da série)."""
    dados = longa.sort_values(["serie_id", "mes"]).copy()
    _conferir_continuidade(dados)
    fator = 1 + dados.variacao_mensal / 100
    if (fator <= 0).any() or fator.isna().any():
        raise ValueError("variação mensal ausente ou de -100% ou menos: o índice não se encadeia")
    dados["indice"] = BASE * np.exp(np.log(fator).groupby(dados.serie_id).cumsum())
    dados["cesta_variavel"] = (
        False if cesta_variavel is None else cesta_variavel.reindex(dados.index).fillna(False)
    )
    return dados[COLUNAS].reset_index(drop=True)


def acumulado(indice: pd.DataFrame, meses: int) -> pd.Series:
    """Acumulado de `meses` meses em % (vazio onde a janela sairia do início da série).

    `indice` deve estar ordenado por série e mês, como `montar_indice` devolve.
    """
    posicao = indice.groupby("serie_id").cumcount()
    anterior = indice.groupby("serie_id").indice.shift(meses)
    anterior = anterior.where(posicao != meses - 1, BASE)
    return (indice.indice / anterior - 1) * 100


def acumulado_no_ano(indice: pd.DataFrame) -> pd.Series:
    """Acumulado desde janeiro em % (vazio se a série começou depois de janeiro daquele ano)."""
    mes_do_ano = indice.mes.str[5:].astype(int)
    resultado = pd.Series(np.nan, index=indice.index)
    for k in sorted(mes_do_ano.unique()):
        linhas = mes_do_ano == k
        resultado[linhas] = acumulado(indice, int(k))[linhas]
    return resultado


def rebasear(indice: pd.DataFrame, mes_base: str) -> pd.Series:
    """Índice com base 100 em `mes_base`, por série (vazio para séries sem esse mês)."""
    no_mes = indice[indice.mes == mes_base].set_index("serie_id").indice
    return indice.indice / indice.serie_id.map(no_mes) * 100


def caminho_indice(indice: Indice) -> Path:
    return RAIZ / "data" / "staging" / indice.codigo / f"indice_{indice.codigo}.parquet"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calcula o índice encadeado por série longa.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    catalogo_indice = carregar_catalogo().indices[args.indice]
    longa = pd.read_parquet(caminho_serie_longa(catalogo_indice))
    marcas = marcar_cesta_variavel(longa, carregar_excecoes(catalogo_indice))
    resultado = montar_indice(longa, marcas)
    destino = caminho_indice(catalogo_indice)
    resultado.to_parquet(destino, index=False)
    print(
        f"{resultado.serie_id.nunique()} séries, {len(resultado)} linhas "
        f"({int(resultado.cesta_variavel.sum())} com cesta variável) em {destino.relative_to(RAIZ)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
