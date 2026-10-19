import pandas as pd
import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.transform.classificacao import (
    ErroClassificacao,
    classificacao_da_tabela,
    montar_dim_classificacao,
    separar_codigo,
)

CATALOGO = carregar_catalogo()
IPCA15 = CATALOGO.indices["ipca15"]
TABELA_7062 = next(t for t in IPCA15.tabelas if t.tabela == 7062)


def metadados(*nomes, niveis=None):
    """Metadados mínimos; `niveis` permite simular o campo `nivel` incoerente da API."""
    niveis = niveis or [0] * len(nomes)
    return {
        "classificacoes": [
            {
                "id": 315,
                "categorias": [
                    {"id": 7169 + i, "nome": n, "nivel": nv}
                    for i, (n, nv) in enumerate(zip(nomes, niveis, strict=True))
                ],
            }
        ]
    }


ARVORE = (
    "Índice geral",
    "1.Alimentação e bebidas",
    "11.Alimentação no domicílio",
    "1101.Cereais, leguminosas e oleaginosas",
    "1101002.Arroz",
)


@pytest.fixture(scope="module")
def dim():
    return montar_dim_classificacao(IPCA15, ArmazemRaw(IPCA15.fonte))


# --- regras de derivação --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("1101002.Arroz", ("1101002", "Arroz")),
        ("1.Alimentação e bebidas", ("1", "Alimentação e bebidas")),
        ("Índice geral", ("0", "Índice geral")),
    ],
)
def test_separar_codigo(nome, esperado):
    assert separar_codigo(nome) == esperado


@pytest.mark.parametrize("nome", ["Arroz", "110.Três dígitos", "11010023.Oito dígitos"])
def test_separar_codigo_rejeita_fora_do_padrao(nome):
    with pytest.raises(ErroClassificacao):
        separar_codigo(nome)


def test_hierarquia_vem_do_codigo_e_ignora_o_campo_nivel():
    # Todos com nivel = 0, como o subitem 4103031 da 1387 (A-010): o resultado não muda.
    linhas = classificacao_da_tabela(metadados(*ARVORE), TABELA_7062)
    por_codigo = {linha["codigo_ibge"]: linha for linha in linhas}
    assert [linha["nivel_hierarquico"] for linha in linhas] == [
        "geral",
        "grupo",
        "subgrupo",
        "item",
        "subitem",
    ]
    arroz = por_codigo["1101002"]
    assert (arroz["codigo_pai"], arroz["grupo"], arroz["subgrupo"], arroz["item"]) == (
        "1101",
        "1",
        "11",
        "1101",
    )
    assert por_codigo["1"]["codigo_pai"] == "0"
    assert por_codigo["0"]["codigo_pai"] is None
    assert por_codigo["11"]["item"] is None


def test_categoria_sem_pai_na_tabela_e_rejeitada():
    with pytest.raises(ErroClassificacao, match="sem pai"):
        classificacao_da_tabela(
            metadados("Índice geral", "1.Alimentação", "1101.Cereais"), TABELA_7062
        )


def test_codigo_repetido_e_rejeitado():
    with pytest.raises(ErroClassificacao, match="repetidos"):
        classificacao_da_tabela(metadados("Índice geral", "1.A", "1.B"), TABELA_7062)


def test_sem_indice_geral_e_rejeitado():
    with pytest.raises(ErroClassificacao, match="sem o índice geral"):
        classificacao_da_tabela(metadados("1.Alimentação"), TABELA_7062)


# --- classificação real do IPCA-15 (metadados guardados no raw) -----------------------------


def test_contagem_por_nivel_em_cada_tabela(dim):
    contagem = dim.groupby(["tabela_sidra", "nivel_hierarquico"]).size().unstack()
    esperado = {
        1646: (1, 9, 19, 52, 512),
        1387: (1, 9, 19, 52, 384),
        1705: (1, 9, 19, 52, 365),
        7062: (1, 9, 19, 51, 367),  # IPCA-15 próprio: o IPCA cheio (7060) tem 377 subitens (A-002)
    }
    for tabela, valores in esperado.items():
        niveis = ["geral", "grupo", "subgrupo", "item", "subitem"]
        assert tuple(contagem.loc[tabela, niveis]) == valores, tabela


def test_subitem_com_nivel_zero_da_1387_e_subitem(dim):
    conjunto = dim[(dim.tabela_sidra == 1387) & (dim.codigo_ibge == "4103031")].iloc[0]
    assert conjunto.nivel_hierarquico == "subitem"
    assert conjunto.codigo_sidra == 12409
    assert conjunto.nome == "Conjunto infantil"


def test_todo_subitem_tem_cadeia_completa_ate_o_grupo(dim):
    for tabela, categorias in dim.groupby("tabela_sidra"):
        existentes = set(categorias.codigo_ibge)
        subitens = categorias[categorias.nivel_hierarquico == "subitem"]
        for coluna in ["item", "subgrupo", "grupo"]:
            assert subitens[coluna].isin(existentes).all(), (tabela, coluna)


def test_versao_pof_vem_do_catalogo(dim):
    pofs = dim.groupby("tabela_sidra").versao_pof.unique().map(list).to_dict()
    assert pofs == {1646: ["1995-96"], 1387: ["2002-03"], 1705: ["2008-09"], 7062: ["2017-18"]}


def test_staging_grava_e_le_em_parquet(dim, tmp_path):
    caminho = tmp_path / "dim.parquet"
    dim.to_parquet(caminho, index=False)
    pd.testing.assert_frame_equal(pd.read_parquet(caminho), dim, check_dtype=False)
