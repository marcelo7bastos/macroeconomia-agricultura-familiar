import shutil

import pandas as pd
import pytest
from comparar_publicacao import comparar_csvs, comparar_exatos, comparar_metadados

from macroaf.catalogo import RAIZ, carregar_catalogo
from macroaf.indicators.calcular import calcular_indicadores
from macroaf.marts import publicar as publicar_mod
from macroaf.marts.publicar import (
    DICIONARIO,
    VALORES,
    atualizar_historico,
    conferir,
    montar_marts,
    publicar,
)

IPCA15 = carregar_catalogo().indices["ipca15"]


@pytest.fixture(scope="module")
def base(dados_dim, dados_referencia, dados_longa):
    dim = dados_dim
    referencia = dados_referencia
    longa = dados_longa
    ind = calcular_indicadores(IPCA15, longa, referencia)
    return montar_marts(dim, longa, ind), longa, ind, referencia


@pytest.fixture(scope="module")
def publicado(tmp_path_factory):
    # Parte do estado versionado: o histórico de séries depende da publicação anterior (0006).
    destino = tmp_path_factory.mktemp("publicacao")
    (destino / "reference").mkdir()
    (destino / "data" / "marts").mkdir(parents=True)
    for relativo in [
        "data/marts/ipca15_categorias.csv",
        "reference/historico_series_ipca15.csv",
        "data/metadata.json",
    ]:
        shutil.copy(RAIZ / relativo, destino / relativo)
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


def test_historico_registra_fusao_e_divisao():
    mapa = pd.DataFrame(
        {
            "tabela_origem": [1.0],
            "codigo_sidra_origem": [10.0],
            "tabela_destino": [2.0],
            "codigo_sidra_destino": [20.0],
            "situacao": ["revisado"],
        }
    )
    separadas = pd.DataFrame(
        {
            "chave_categoria": ["1.10", "2.20"],
            "serie_id": ["a@x", "b@y"],
            "versao_pof": ["1995-96", "2002-03"],
        }
    )
    juntas = separadas.assign(serie_id="a@x")
    fusao = atualizar_historico(separadas, juntas, mapa, "2026-10-20")
    assert fusao.to_dict("records") == [
        {
            "registrado_em": "2026-10-20",
            "serie_id_antigo": "b@y",
            "serie_id_novo": "a@x",
            "categorias": 1,
            "ligacao": "L-1.10-2.20",
            "situacao": "revisado",
        }
    ]
    divisao = atualizar_historico(
        juntas, separadas, mapa.assign(situacao="rejeitado"), "2026-11-20"
    )
    assert divisao[["serie_id_antigo", "serie_id_novo", "ligacao", "situacao"]].values.tolist() == [
        ["a@x", "b@y", "L-1.10-2.20", "rejeitado"]
    ]
    assert atualizar_historico(None, juntas, mapa, "2026-10-20").empty
    assert atualizar_historico(juntas, juntas, mapa, "2026-10-20").empty


def test_publicacao_bloqueada_nao_grava_nada(tmp_path, monkeypatch):
    monkeypatch.setattr(publicar_mod, "conferir", lambda *args: ["problema simulado"])
    assert publicar_mod.publicar(IPCA15, tmp_path) == ["problema simulado"]
    assert list(tmp_path.rglob("*")) == []


def test_valores_das_colunas_categoricas_estao_no_dicionario(base):
    marts, _, _, _ = base
    for nome, tabela in marts.items():
        for coluna in tabela.columns:
            if coluna in VALORES:
                assert set(tabela[coluna].dropna()) <= set(VALORES[coluna]), (nome, coluna)


def test_marca_de_cesta_variavel_da_sazonalidade_chega_ao_mart(base):
    marts, _, ind, _ = base
    mensal = marts["mensal"]
    assert mensal.sazonalidade_cesta_variavel.sum() == ind["sazonalidade"].cesta_variavel.sum()
    # A janela de 5 anos pode ter cesta variável mesmo num mês sem ela.
    assert ((mensal.sazonalidade_cesta_variavel == 1) & (mensal.cesta_variavel == 0)).any()


def test_publicacao_e_deterministica_e_o_repositorio_esta_em_dia(publicado):
    # O que é oficial e a estrutura continuam exatos; calculados seguem a regra A-031.
    pasta_esperada = RAIZ / "data" / "marts"
    pasta_obtida = publicado / "data" / "marts"
    nomes = sorted(p.name for p in pasta_obtida.iterdir())
    comparar_exatos(
        sorted(
            p.name
            for p in pasta_esperada.iterdir()
            if p.name == "README.md" or p.name.startswith(f"{IPCA15.codigo}_")
        ),
        nomes,
        "data/marts: arquivos",
    )
    for nome in nomes:
        esperado, obtido = pasta_esperada / nome, pasta_obtida / nome
        if esperado.suffix == ".csv":
            comparar_csvs(esperado, obtido, IPCA15.codigo)
        else:
            comparar_exatos(esperado.read_bytes(), obtido.read_bytes(), nome)
    comparar_metadados(RAIZ / "data/metadata.json", publicado / "data/metadata.json", IPCA15.codigo)
    relativo = "reference/historico_series_ipca15.csv"
    comparar_exatos((RAIZ / relativo).read_bytes(), (publicado / relativo).read_bytes(), relativo)


def test_readme_documenta_todas_as_colunas(publicado):
    readme = (publicado / "data" / "marts" / "README.md").read_text()
    for nome, especificacao in DICIONARIO.items():
        assert f"ipca15_{nome}.csv" in readme
        for coluna in especificacao["colunas"]:
            assert f"`{coluna}`" in readme
