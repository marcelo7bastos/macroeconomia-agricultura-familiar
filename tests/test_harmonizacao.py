import pandas as pd
import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.harmonizacao import (
    atualizar_mapa,
    conferir_mapa,
    conferir_serie_longa,
    ler_mapa,
    montar_serie_longa,
    parentesco,
    propor_mapa,
)
from macroaf.transform.ipca15 import montar_fato

IPCA15 = carregar_catalogo().indices["ipca15"]
ARMAZEM = ArmazemRaw(IPCA15.fonte)
CHAVE = ["tabela_origem", "codigo_sidra_origem", "tabela_destino", "codigo_sidra_destino"]


@pytest.fixture(scope="module")
def base():
    dim = montar_dim_classificacao(IPCA15, ARMAZEM)
    fato = montar_fato(IPCA15, ARMAZEM, dim)
    return dim, fato, ler_mapa(IPCA15)


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [
        ("Livro", "Livro didático", 1.0),
        ("Feijão - carioca (rajado))", "Feijão - carioca (rajado)", 1.0),
        ("Melão", "Telha", 0.0),
        ("Peixe - cavalinha", "Peixe - linguado", 0.0),  # só a palavra genérica em comum
    ],
)
def test_parentesco_de_nomes(a, b, esperado):
    assert parentesco(a, b) == esperado


def test_mapa_do_repositorio_esta_completo_e_coerente(base):
    dim, _, mapa = base
    assert conferir_mapa(mapa, dim, IPCA15) == []


def test_mapa_do_repositorio_esta_em_dia_com_a_proposta(base):
    # Regerar o mapa a partir dos dados não pode mudar o arquivo (revisões são preservadas):
    #   uv run python -m macroaf.transform.harmonizacao
    dim, fato, mapa = base
    regerado = atualizar_mapa(propor_mapa(IPCA15, dim, fato), mapa)
    ordenar = lambda df: df.sort_values(CHAVE).reset_index(drop=True)  # noqa: E731
    pd.testing.assert_frame_equal(ordenar(regerado), ordenar(mapa), check_dtype=False)


def test_mesmo_codigo_com_id_novo_nunca_emenda_sem_revisao(base):
    # A-012: id novo é definição nova; só a grafia igual vira automático.
    _, _, mapa = base
    mesmo_codigo = mapa[
        (mapa.codigo_ibge_origem == mapa.codigo_ibge_destino)
        & (mapa.codigo_sidra_origem != mapa.codigo_sidra_destino)
    ]
    automaticos = mesmo_codigo[mesmo_codigo.situacao == "automatico"]
    assert set(automaticos.criterio) <= {"mesmo código; id novo; só grafia mudou"}
    assert len(automaticos) == 1  # "Feijão - carioca (rajado))" -> "(rajado)"
    assert (mesmo_codigo.situacao == "proposto").sum() == 79


def test_leite_pasteurizado_nao_emenda_no_longa_vida(base):
    dim, fato, mapa = base
    longa = montar_serie_longa(fato, dim, mapa)
    leite = longa[longa.codigo_ibge == "1111004"].groupby("serie_id").nome.unique().map(list)
    assert leite.to_dict() == {
        "1111004@1995-96": ["Leite pasteurizado"],
        "1111004@2008-09": ["Leite longa vida"],
    }
    antiga = longa[longa.serie_id == "1111004@1995-96"].iloc[0]
    assert antiga.saida == "renomeado (proposta não revisada)"


def test_revisao_humana_e_preservada_e_emenda_a_serie(base):
    dim, fato, mapa = base
    revisado = mapa.copy()
    linha = (revisado.codigo_ibge_origem == "1111004") & (revisado.tabela_origem == 1387)
    revisado.loc[linha, ["situacao", "revisor"]] = ["revisado", "teste"]
    regerado = atualizar_mapa(propor_mapa(IPCA15, dim, fato), revisado)
    assert (
        regerado[
            (regerado.codigo_ibge_origem == "1111004") & (regerado.tabela_origem == 1387)
        ].situacao
        == "revisado"
    ).all()
    longa = montar_serie_longa(fato, dim, regerado)
    assert longa[longa.codigo_ibge == "1111004"].serie_id.nunique() == 1


def test_revisao_sem_revisor_e_rejeitada(base):
    dim, _, mapa = base
    sem_revisor = mapa.copy()
    sem_revisor.loc[sem_revisor.index[0], "situacao"] = "revisado"
    assert any("sem revisor" in p for p in conferir_mapa(sem_revisor, dim, IPCA15))


def test_serie_longa_respeita_os_invariantes(base):
    dim, fato, mapa = base
    longa = montar_serie_longa(fato, dim, mapa)
    assert conferir_serie_longa(longa, fato) == []
    completas = longa[(longa.inicio_serie == fato.mes.min()) & (longa.fim_serie == fato.mes.max())]
    por_nivel = completas.drop_duplicates("serie_id").nivel_hierarquico.value_counts()
    assert por_nivel["geral"] == 1 and por_nivel["grupo"] == 9
    assert por_nivel["subitem"] >= 200
