"""Contribuições em pontos percentuais para o índice geral (#43).

- **No mês:** `c = peso * v / Σ pesos dos grupos`, com peso e variação do mesmo mês e tabela. A
  divisão pela soma dos pesos dos grupos (100, salvo erro da fonte, A-015) faz a soma das
  contribuições dos grupos reproduzir a média ponderada que dá a variação do geral.
- **Participação no grupo:** a contribuição da categoria dividida pela soma das contribuições das
  categorias do mesmo nível no mesmo grupo, em %. Soma 100% por construção; perde sentido quando
  a variação do grupo é próxima de zero, e fica vazia onde falta contribuição no nível e grupo.
- **Para o acumulado:** cada mês da janela é reescalado pelo índice geral acumulado até o mês
  anterior: `Σ_m c_m * I_geral(m-1) / I_geral(início - 1)`. A soma dos grupos dá o acumulado do
  geral. A janela não sai da série longa da categoria (decisão 0005).

Subitens com cesta variável (1646 in natura, A-013) ficam sem contribuição: os pesos deles não
reproduzem o item; a contribuição desses produtos é a do item.

Uso:

    uv run python -m macroaf.indicators.contribuicoes  # grava contribuicoes_ipca15 no staging
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from macroaf.catalogo import RAIZ, Indice, carregar_catalogo
from macroaf.indicators.acumulados import JANELAS, tamanho_da_janela
from macroaf.indicators.indice import caminho_indice
from macroaf.transform.harmonizacao import caminho_serie_longa
from macroaf.transform.ipca15 import diretorio_staging

NIVEL_SUBITEM = "subitem"
COLUNAS = [
    "serie_id",
    "mes",
    "tabela_sidra",
    "codigo_sidra",
    "codigo_ibge",
    "nivel_hierarquico",
    "janela",
    "contribuicao",
    "participacao_no_grupo",
]


def contribuicao_mensal(dados: pd.DataFrame) -> pd.Series:
    """Contribuição do mês em p.p.: peso * variação / soma dos pesos dos grupos (mês e tabela)."""
    grupos = dados[dados.nivel_hierarquico == "grupo"]
    soma = grupos.groupby(["mes", "tabela_sidra"]).peso.sum().rename("soma_pesos_grupos")
    soma_da_linha = dados[["mes", "tabela_sidra"]].join(soma, on=["mes", "tabela_sidra"])
    contribuicao = dados.peso * dados.variacao_mensal / soma_da_linha.soma_pesos_grupos
    geral = dados.codigo_ibge == "0"
    return contribuicao.where(~geral, dados.variacao_mensal)


def participacao_no_grupo(dados: pd.DataFrame, contribuicao: pd.Series) -> pd.Series:
    """% da soma das contribuições do mesmo nível e grupo.

    Vazia no geral, se a soma é 0 e se falta alguma contribuição no mesmo nível e grupo (ex.:
    subitens in natura da 1646): sem ela, a soma não é a variação do grupo (A-025).
    """
    grupo = dados.codigo_ibge.str[0]
    chave = [dados.mes, dados.tabela_sidra, dados.nivel_hierarquico, grupo]
    soma = contribuicao.groupby(chave).transform("sum")
    completo = contribuicao.isna().groupby(chave).transform("sum") == 0
    participacao = contribuicao / soma.where(soma != 0) * 100
    return participacao.where((dados.codigo_ibge != "0") & completo)


def contribuicao_acumulada(
    dados: pd.DataFrame, contribuicao: pd.Series, janela: str, indice_geral: pd.Series
) -> pd.Series:
    """Contribuição em p.p. para o acumulado do geral na janela (vazio fora da série).

    `dados` ordenado por série e mês; `indice_geral` é o índice encadeado do geral por mês.
    """
    anterior = dados.mes.map(indice_geral.shift(1))
    primeiro = indice_geral.index[0]
    anterior = anterior.where(dados.mes != primeiro, 100.0)  # base do encadeamento
    pesada = contribuicao * anterior
    tamanho = tamanho_da_janela(dados, janela)
    acumulada = pesada.groupby(dados.serie_id).cumsum()
    posicao = dados.groupby("serie_id").cumcount()
    resultado = pd.Series(np.nan, index=dados.index)
    for k in sorted(tamanho.unique()):
        linhas = tamanho == k
        antes = acumulada.groupby(dados.serie_id).shift(int(k)).fillna(0)
        inicio = dados.mes.map(_mes_menos(indice_geral, int(k)))
        resultado[linhas] = ((acumulada - antes) / inicio)[linhas]
    return resultado.where(posicao >= tamanho - 1)


def _mes_menos(indice_geral: pd.Series, k: int) -> pd.Series:
    """Índice geral no mês anterior ao início de uma janela de k meses terminada em cada mês."""
    deslocado = indice_geral.shift(k)
    if k <= len(indice_geral):
        deslocado.iloc[k - 1] = 100.0
    return deslocado


def montar_contribuicoes(indice: pd.DataFrame, longa: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por série, mês e janela ("mes" e as de acumulados) com contribuição."""
    dados = indice.merge(
        longa[["serie_id", "mes", "peso"]], on=["serie_id", "mes"], validate="one_to_one"
    )
    geral = dados[dados.codigo_ibge == "0"]
    if geral.serie_id.nunique() != 1:
        raise ValueError("o índice geral precisa ser uma série só para reescalar as contribuições")
    indice_geral = geral.set_index("mes").indice
    contribuicao = contribuicao_mensal(dados)
    sem_cesta = ~(dados.cesta_variavel & (dados.nivel_hierarquico == NIVEL_SUBITEM))
    contribuicao = contribuicao.where(sem_cesta)
    partes = [
        dados.assign(
            janela="mes",
            contribuicao=contribuicao,
            participacao_no_grupo=participacao_no_grupo(dados, contribuicao),
        )
    ]
    for janela in JANELAS:
        partes.append(
            dados.assign(
                janela=janela,
                contribuicao=contribuicao_acumulada(dados, contribuicao, janela, indice_geral),
                participacao_no_grupo=np.nan,
            )
        )
    resultado = pd.concat(partes, ignore_index=True)
    return resultado[resultado.contribuicao.notna()][COLUNAS].reset_index(drop=True)


def caminho_contribuicoes(indice: Indice) -> Path:
    return diretorio_staging(indice) / f"contribuicoes_{indice.codigo}.parquet"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calcula as contribuições em p.p.")
    parser.add_argument("--indice", default="ipca15")
    args = parser.parse_args(argv)

    catalogo_indice = carregar_catalogo().indices[args.indice]
    resultado = montar_contribuicoes(
        pd.read_parquet(caminho_indice(catalogo_indice)),
        pd.read_parquet(caminho_serie_longa(catalogo_indice)),
    )
    destino = caminho_contribuicoes(catalogo_indice)
    resultado.to_parquet(destino, index=False)
    print(resultado.groupby("janela").size().to_string())
    print(f"{len(resultado)} linhas em {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
