import math

import pandas as pd
import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.transform.ipca15 import (
    COLUNAS_FATO,
    ErroTransformacao,
    converter_valor,
    montar_referencia,
)

IPCA15 = carregar_catalogo().indices["ipca15"]
ARMAZEM = ArmazemRaw(IPCA15.fonte)


@pytest.fixture(scope="module")
def dim(dados_dim):
    return dados_dim


@pytest.fixture(scope="module")
def fato(dim, dados_fato):
    return dados_fato


def test_converter_valor():
    assert converter_valor("-", "x") == 0.0
    assert converter_valor("0.70", "x") == 0.70
    assert converter_valor("-1.5", "x") == -1.5
    assert math.isnan(converter_valor("...", "x"))


@pytest.mark.parametrize("texto", ["..", "X", ""])
def test_outros_sinais_do_ibge_interrompem_ate_ganhar_tratamento(texto):
    with pytest.raises(ErroTransformacao, match="não numérico"):
        converter_valor(texto, "contexto")


def test_fato_tem_uma_linha_por_mes_e_categoria(fato, dim):
    assert list(fato.columns) == COLUNAS_FATO
    assert not fato.duplicated(["mes", "tabela_sidra", "codigo_sidra"]).any()
    meses = fato.groupby("tabela_sidra").mes.nunique().to_dict()
    assert meses == {1646: 75, 1387: 66, 1705: 96, 7062: len(ARMAZEM.periodos(7062))}
    categorias = dim.groupby("tabela_sidra").size()
    linhas = fato.groupby("tabela_sidra").size()
    assert (linhas == categorias * pd.Series(meses)).all()


def test_fato_liga_valores_pelo_id_sidra_e_nao_pelo_codigo(fato):
    # 1111004 é "Leite pasteurizado" (id 7357) até a 1387 e "Leite longa vida" (12393) depois.
    leite = fato[fato.codigo_ibge == "1111004"].groupby("tabela_sidra").codigo_sidra.unique()
    assert {t: list(ids) for t, ids in leite.items()} == {
        1646: [7357],
        1387: [7357],
        1705: [12393],
        7062: [12393],
    }


def test_acumulado_12m_ausente_onde_o_ibge_nao_publica(fato):
    # A-009: 1120 não existe na 1646/1387 e vem `...` em 2012-02..2017-02 e 2020-02..2020-12.
    doze = (
        fato.set_index(["tabela_sidra", "mes"]).variacao_acum_12m.isna().groupby(level=[0, 1]).all()
    )
    assert doze.loc[1646].all() and doze.loc[1387].all()
    assert doze.loc[(1705, "2017-02")] and not doze.loc[(1705, "2017-03")]
    assert doze.loc[(7062, "2020-12")] and not doze.loc[(7062, "2021-01")]


def test_referencia_cobre_toda_a_serie(fato):
    referencia = montar_referencia(IPCA15, ARMAZEM)
    assert referencia.mes.iloc[0] == "2000-05"
    assert referencia.mes.tolist() == sorted(fato.mes.unique())
    assert not referencia.isna().any().any()
