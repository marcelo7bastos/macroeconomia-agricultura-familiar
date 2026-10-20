import json

import pandas as pd
import pytest

from macroaf.catalogo import RAIZ, carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.indicators.calcular import calcular_indicadores
from macroaf.marts.publicar import (
    DICIONARIO,
    atualizar_historico,
    conferir,
    montar_marts,
    publicar,
)
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.harmonizacao import ler_mapa, montar_serie_longa
from macroaf.transform.ipca15 import montar_fato, montar_referencia

IPCA15 = carregar_catalogo().indices["ipca15"]
ARMAZEM = ArmazemRaw(IPCA15.fonte)


@pytest.fixture(scope="module")
def base():
    dim = montar_dim_classificacao(IPCA15, ARMAZEM)
    fato = montar_fato(IPCA15, ARMAZEM, dim)
    referencia = montar_referencia(IPCA15, ARMAZEM)
    longa = montar_serie_longa(fato, dim, ler_mapa(IPCA15))
    ind = calcular_indicadores(IPCA15, longa, referencia)
    return montar_marts(dim, longa, ind), longa, ind, referencia


@pytest.fixture(scope="module")
def publicado(tmp_path_factory):
    destino = tmp_path_factory.mktemp("publicacao")
    (destino / "reference").mkdir()
    assert publicar(IPCA15, destino) == []
    return destino


def test_colunas_e_chaves_seguem_o_dicionario(base):
    marts, _, _, _ = base
    assert set(marts) == set(DICIONARIO)
    for nome, tabela in marts.items():
        assert list(tabela.columns) == list(DICIONARIO[nome]["colunas"]), nome
        assert not tabela.duplicated(DICIONARIO[nome]["chave"]).any(), nome
    categorias = set(marts["categorias"].chave_categoria)
    for nome in ["mensal", "acumulados", "contribuicoes"]:
        assert set(marts[nome].chave_categoria) <= categorias, nome


def test_uma_linha_do_mensal_por_linha_do_fato(base):
    marts, longa, _, _ = base
    assert len(marts["mensal"]) == len(longa)
    assert marts["categorias"].serie_id.notna().all()


def test_valores_oficiais_passam_sem_mudanca(base):
    marts, longa, _, _ = base
    mensal = marts["mensal"].set_index(["mes", "chave_categoria"])
    origem = longa.assign(
        chave_categoria=longa.tabela_sidra.astype(str) + "." + longa.codigo_sidra.astype(str)
    ).set_index(["mes", "chave_categoria"])
    for coluna, publicada in [
        ("variacao_mensal", "variacao_mensal"),
        ("peso", "peso"),
        ("variacao_acum_ano_publicada", "variacao_acum_ano"),
        ("variacao_acum_12m_publicada", "variacao_acum_12m"),
    ]:
        pd.testing.assert_series_equal(
            mensal[coluna].sort_index(), origem[publicada].sort_index(), check_names=False
        )


def test_acumulado_do_geral_e_o_da_3065(base):
    marts, _, _, referencia = base
    acumulados = marts["acumulados"]
    geral = acumulados[acumulados.chave_categoria.str.endswith(".7169")].set_index("mes")
    oficial = referencia.set_index("mes")
    oficiais = geral[geral.origem_12m == "oficial"]
    assert len(oficiais) > 300
    assert (oficiais.acum_12m == oficial.variacao_acum_12m.reindex(oficiais.index)).all()


def test_conferencia_bloqueia_chave_repetida(base):
    marts, longa, ind, referencia = base
    assert conferir(marts, longa, ind, referencia) == []
    estragado = dict(marts, difusao=pd.concat([marts["difusao"], marts["difusao"].head(1)]))
    assert any("repetida" in p for p in conferir(estragado, longa, ind, referencia))


def test_historico_registra_mudanca_de_serie():
    atual = pd.DataFrame({"chave_categoria": ["1.10", "2.20"], "serie_id": ["a@x", "a@x"]})
    anterior = pd.DataFrame(
        {
            "chave_categoria": ["1.10", "2.20"],
            "serie_id": ["a@x", "b@y"],
            "serie_inicio": ["2000-01", "2010-01"],
        }
    )
    mapa = pd.DataFrame(
        {
            "tabela_origem": [1.0],
            "codigo_sidra_origem": [10.0],
            "tabela_destino": [2.0],
            "codigo_sidra_destino": [20.0],
        }
    )
    historico = atualizar_historico(anterior, atual, mapa, "2026-10")
    assert historico.to_dict("records") == [
        {
            "registrado_em": "2026-10",
            "serie_id_antigo": "b@y",
            "serie_id_novo": "a@x",
            "categorias": 1,
            "ligacao": "L-1.10-2.20",
        }
    ]
    assert atualizar_historico(None, atual, mapa, "2026-10").empty


def test_publicacao_e_deterministica_e_o_repositorio_esta_em_dia(publicado, tmp_path):
    # Os marts versionados saem do raw; se o pipeline mudou, publique no mesmo PR:
    #   uv run python -m macroaf.marts.publicar --indice ipca15
    for arquivo in sorted((publicado / "data" / "marts").iterdir()):
        no_repositorio = RAIZ / "data" / "marts" / arquivo.name
        assert no_repositorio.read_bytes() == arquivo.read_bytes(), arquivo.name
    gerado = json.loads((publicado / "data" / "metadata.json").read_text())
    versionado = json.loads((RAIZ / "data" / "metadata.json").read_text())
    assert gerado["ipca15"] == versionado["ipca15"]
    assert (publicado / "reference" / "historico_series_ipca15.csv").read_text() == (
        RAIZ / "reference" / "historico_series_ipca15.csv"
    ).read_text()


def test_readme_documenta_todas_as_colunas(publicado):
    readme = (publicado / "data" / "marts" / "README.md").read_text()
    for nome, especificacao in DICIONARIO.items():
        assert f"ipca15_{nome}.csv" in readme
        for coluna in especificacao["colunas"]:
            assert f"`{coluna}`" in readme
