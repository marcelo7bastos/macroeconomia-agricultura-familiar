import pandas as pd
import pytest

from macroaf.catalogo import carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.indicators.difusao import montar_difusao
from macroaf.indicators.indice import marcar_cesta_variavel, montar_indice
from macroaf.indicators.sazonalidade import ANOS, montar_sazonalidade
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.harmonizacao import ler_mapa, montar_serie_longa
from macroaf.transform.ipca15 import montar_fato
from macroaf.validate.ipca15 import carregar_excecoes

IPCA15 = carregar_catalogo().indices["ipca15"]
ARMAZEM = ArmazemRaw(IPCA15.fonte)


def test_difusao_simples_e_ponderada():
    longa = pd.DataFrame(
        {
            "mes": ["2020-01"] * 5,
            "tabela_sidra": [1] * 5,
            "versao_pof": ["x"] * 5,
            "codigo_ibge": ["0", "1101001", "1101002", "1101003", "2101001"],
            "nivel_hierarquico": ["geral", "subitem", "subitem", "subitem", "subitem"],
            "variacao_mensal": [0.1, 1.0, 0.0, 0.0, -1.0],
            "peso": [100.0, 30.0, 20.0, 0.0, 50.0],  # 1101003 fora de coleta (A-026)
        }
    )
    difusao = montar_difusao(longa).set_index("codigo_ibge")
    assert difusao.loc["0", "difusao_simples"] == pytest.approx(100 / 3)
    assert difusao.loc["0", "difusao_ponderada"] == pytest.approx(30.0)
    assert difusao.loc["0", "subitens_peso_zero"] == 1
    assert difusao.loc["1", "difusao_simples"] == pytest.approx(50.0)
    assert difusao.loc["2", "difusao_ponderada"] == pytest.approx(0.0)


def _indice(anos_por_serie: dict[str, list[int]]) -> pd.DataFrame:
    linhas = [
        {
            "serie_id": serie,
            "mes": f"{ano}-01",
            "codigo_ibge": "0",
            "nivel_hierarquico": "geral",
            "variacao_mensal": float(ano % 10),
            "cesta_variavel": False,
        }
        for serie, anos in anos_por_serie.items()
        for ano in anos
    ]
    return pd.DataFrame(linhas)


def test_sazonalidade_em_janela_movel():
    resultado = montar_sazonalidade(_indice({"a": [2001, 2002, 2003, 2004]}), anos=3)
    assert resultado.ano_final.tolist() == [2003, 2004]
    assert resultado.media.tolist() == pytest.approx([2.0, 3.0])
    assert resultado.mediana.tolist() == pytest.approx([2.0, 3.0])


def test_sazonalidade_nao_pula_ano_que_falta():
    resultado = montar_sazonalidade(_indice({"a": [2001, 2002, 2004, 2005]}), anos=3)
    assert resultado.empty


@pytest.fixture(scope="module")
def base():
    dim = montar_dim_classificacao(IPCA15, ARMAZEM)
    fato = montar_fato(IPCA15, ARMAZEM, dim)
    longa = montar_serie_longa(fato, dim, ler_mapa(IPCA15))
    indice = montar_indice(longa, marcar_cesta_variavel(longa, carregar_excecoes(IPCA15)))
    return longa, indice


def test_difusao_real_entre_0_e_100_e_um_valor_por_mes(base):
    longa, _ = base
    difusao = montar_difusao(longa)
    for coluna in ["difusao_simples", "difusao_ponderada"]:
        assert difusao[coluna].between(0, 100).all()
    geral = difusao[difusao.codigo_ibge == "0"]
    assert geral.mes.is_unique
    assert set(geral.mes) == set(longa.mes)
    assert set(geral[geral.cesta_nova].mes) == {"2006-08", "2012-02", "2020-02"}
    assert geral.subitens_peso_zero.sum() == 93  # os 93 zeros da 1646 (A-013)


def test_soma_dos_pesos_dos_subitens_e_o_peso_publicado(base):
    # Os subitens do recorte somam o peso do geral e de cada grupo, salvo arredondamento.
    longa, _ = base
    difusao = montar_difusao(longa).set_index(["mes", "codigo_ibge"])
    publicado = longa[longa.nivel_hierarquico.isin(["geral", "grupo"])].set_index(
        ["mes", "codigo_ibge"]
    )
    diferenca = (difusao.peso - publicado.peso.reindex(difusao.index)).abs()
    # A-015: em 2010-07/08 (1387) a árvore toda foi multiplicada por 1,000999 e o geral fica 100.
    erro_da_fonte = [("2010-07", "0"), ("2010-08", "0")]
    assert diferenca.drop(erro_da_fonte).max() < 0.01
    assert diferenca.loc[erro_da_fonte].round(2).tolist() == [0.1, 0.1]


def test_cesta_variavel_marca_so_janelas_com_mes_marcado():
    indice = _indice({"a": [2001, 2002, 2003, 2004, 2005]})
    indice["cesta_variavel"] = [False, True, False, False, False]
    marcas = montar_sazonalidade(indice, anos=2).set_index("ano_final").cesta_variavel
    assert marcas.to_dict() == {2002: True, 2003: True, 2004: False, 2005: False}


def test_sazonalidade_real_bate_com_a_conta_direta(base):
    _, indice = base
    sazonalidade = montar_sazonalidade(indice).set_index(["serie_id", "mes_do_ano", "ano_final"])
    geral = indice[indice.codigo_ibge == "0"]
    dezembros = geral[geral.mes.str[5:] == "12"]
    dezembros = dezembros.set_index(dezembros.mes.str[:4].astype(int))
    esperado = dezembros.variacao_mensal.loc[2025 - ANOS + 1 : 2025]
    linha = sazonalidade.loc[("0@1995-96", "12", 2025)]
    assert linha.media == pytest.approx(esperado.mean())
    assert linha.mediana == pytest.approx(esperado.median())


def test_sazonalidade_fica_dentro_da_serie(base):
    _, indice = base
    sazonalidade = montar_sazonalidade(indice)
    inicio = indice.groupby("serie_id").mes.min().str[:4].astype(int)
    assert (sazonalidade.ano_final - ANOS + 1 >= sazonalidade.serie_id.map(inicio)).all()
