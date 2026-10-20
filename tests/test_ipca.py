"""IPCA cheio: contratos reais, referências e regressões do pipeline compartilhado."""

import json
import shutil
from dataclasses import replace

import pandas as pd
import pytest
from comparar_publicacao import comparar_csvs, comparar_exatos, comparar_metadados

from macroaf.catalogo import RAIZ, carregar_catalogo
from macroaf.extract.raw import ArmazemRaw
from macroaf.marts.publicar import publicar
from macroaf.relatorios.transformacoes import caminho_pagina, gerar
from macroaf.transform.classificacao import montar_dim_classificacao
from macroaf.transform.harmonizacao import ler_mapa, montar_serie_longa
from macroaf.transform.ipca15 import montar_fato, montar_referencia
from macroaf.validate.ipca15 import carregar_configuracao, validar, validar_continuidade

IPCA = carregar_catalogo().indices["ipca"]
RAW = ArmazemRaw(IPCA.fonte)


@pytest.fixture(scope="module")
def dados():
    dim = montar_dim_classificacao(IPCA, RAW)
    fato = montar_fato(IPCA, RAW, dim)
    referencia = montar_referencia(IPCA, RAW)
    return dim, fato, referencia


def test_catalogo_ipca_cobre_tres_pofs_sem_confundir_os_codigos():
    assert [(t.tabela, t.inicio, t.fim) for t in IPCA.tabelas_dados] == [
        (2938, "2006-07", "2011-12"),
        (1419, "2012-01", "2019-12"),
        (7060, "2020-01", None),
    ]
    assert IPCA.tabelas_referencia[0].inicio == "1979-12"
    assert IPCA.variaveis[63].nome == "variacao_mensal"
    assert IPCA.variaveis[2266].nome == "numero_indice"


def test_classificacao_propria_e_fato_sem_lacunas(dados):
    dim, fato, referencia = dados
    atual = dim[dim.tabela_sidra == 7060]
    assert len(atual) == 457
    assert (atual.nivel_hierarquico == "subitem").sum() == 377
    geral = fato[fato.codigo_ibge == "0"].sort_values("mes")
    assert geral.mes.tolist() == referencia.mes.tolist()
    assert geral.mes.iloc[0] == "2006-07"
    assert geral.mes.iloc[-1] == max(RAW.periodos(7060))
    assert not fato.duplicated(["mes", "tabela_sidra", "codigo_sidra"]).any()
    for codigo in ["1", "11", "12"]:
        assert len(fato[fato.codigo_ibge == codigo]) == len(referencia)


def test_referencia_preserva_cobertura_original_no_raw_e_recorta_no_staging(dados):
    assert RAW.periodos(1737)[0] == "1979-12"
    assert dados[2].mes.min() == "2006-07"
    recente = replace(IPCA, tabelas=tuple(t for t in IPCA.tabelas if t.tabela in {7060, 1737}))
    assert montar_referencia(recente, RAW).mes.min() == "2020-01"


def test_ausencia_dos_doze_meses_e_especifica_do_ipca(dados):
    fato = dados[1]
    for tabela, inicio, primeiro in [(1419, "2012-01", "2012-12"), (7060, "2020-01", "2020-12")]:
        arroz = fato[(fato.tabela_sidra == tabela) & (fato.codigo_ibge == "1101002")]
        assert (
            arroz[arroz.mes.between(inicio, primeiro, inclusive="left")]
            .variacao_acum_12m.isna()
            .all()
        )
        assert arroz[arroz.mes == primeiro].variacao_acum_12m.notna().all()


def test_validacoes_reais_e_erro_injetado(dados):
    dim, fato, referencia = dados
    configuracao = carregar_configuracao(IPCA, RAW, dim)
    resultados, sentinelas = validar(fato, referencia, configuracao)
    assert {r.validacao: r.exemplos for r in resultados if not r.ok} == {}
    assert sentinelas.empty
    alterado = fato.copy()
    ultimo = fato.mes.max()
    alterado.loc[(alterado.mes == ultimo) & (alterado.codigo_ibge == "1"), "peso"] += 1
    ruins, _ = validar(alterado, referencia, configuracao)
    assert any(not r.ok for r in ruins)


def test_harmonizacao_nao_emenda_propostas(dados):
    dim, fato, _ = dados
    mapa = ler_mapa(IPCA)
    longa = montar_serie_longa(fato, dim, mapa)
    assert len(longa) == len(fato)
    for r in mapa[mapa.situacao == "proposto"].itertuples():
        if pd.notna(r.codigo_sidra_origem) and pd.notna(r.codigo_sidra_destino):
            origem = longa[
                (longa.tabela_sidra == r.tabela_origem)
                & (longa.codigo_sidra == r.codigo_sidra_origem)
            ]
            destino = longa[
                (longa.tabela_sidra == r.tabela_destino)
                & (longa.codigo_sidra == r.codigo_sidra_destino)
            ]
            assert origem.serie_id.iloc[0] != destino.serie_id.iloc[0]


def test_publicacao_ipca_em_dia_e_isolada_do_ipca15(tmp_path):
    (tmp_path / "data/marts").mkdir(parents=True)
    (tmp_path / "reference").mkdir()
    for relativo in [
        "data/metadata.json",
        "data/marts/ipca_categorias.csv",
        "reference/historico_series_ipca.csv",
    ]:
        shutil.copy(RAIZ / relativo, tmp_path / relativo)
    assert publicar(IPCA, tmp_path) == []
    for arquivo in (tmp_path / "data/marts").glob("*.csv"):
        comparar_csvs(RAIZ / "data/marts" / arquivo.name, arquivo, IPCA.codigo)
    comparar_metadados(RAIZ / "data/metadata.json", tmp_path / "data/metadata.json", IPCA.codigo)
    comparar_exatos(
        (RAIZ / "data/marts/ipca_README.md").read_bytes(),
        (tmp_path / "data/marts/ipca_README.md").read_bytes(),
        "dicionário",
    )
    meta = json.loads((tmp_path / "data/metadata.json").read_text())
    anterior = json.loads((RAIZ / "data/metadata.json").read_text())
    assert meta["ipca15"] == anterior["ipca15"]
    assert set(meta["ipca"]["tabelas"]) == {str(t.tabela) for t in IPCA.tabelas}


def test_relatorio_ipca_usa_sua_propria_referencia():
    html = gerar("ipca")
    comparar_exatos(caminho_pagina("ipca").read_text(), html, "relatório do IPCA")
    assert "Transformações do IPCA" in html
    assert "1737" in html
    assert "3065" not in html


def test_indisponiveis_sao_aferidos_no_raw_e_perda_de_linha_ativa_falha(dados):
    dim, fato, _ = dados
    configuracao = carregar_configuracao(IPCA, RAW, dim)
    assert len(configuracao.indisponiveis) == 952
    assert not validar_continuidade(fato.iloc[1:], configuracao).ok
    bruto = montar_fato(IPCA, RAW, dim, incluir_indisponiveis=True)
    sem_coleta = bruto[bruto[["variacao_mensal", "variacao_acum_ano", "peso"]].isna().all(axis=1)]
    assert len(bruto) - len(fato) == len(sem_coleta) == 952
    falso_zero = sem_coleta.head(1).copy()
    falso_zero[["variacao_mensal", "variacao_acum_ano", "peso"]] = 0.0
    assert not validar_continuidade(pd.concat([fato, falso_zero]), configuracao).ok


def test_ausencia_de_coleta_nao_cria_emenda_entre_pofs(dados):
    dim, fato, _ = dados
    longa = montar_serie_longa(fato, dim, ler_mapa(IPCA))
    for codigo in ["1107097", "1108009", "1108011", "8104005"]:
        categoria = longa[longa.codigo_ibge == codigo]
        antes = categoria[categoria.tabela_sidra == 2938].serie_id.iloc[-1]
        depois = categoria[categoria.tabela_sidra == 1419].serie_id.iloc[0]
        assert antes != depois


def test_anuais_divergentes_da_fonte_tem_lista_independente_e_contada(dados):
    fato = dados[1].sort_values(["tabela_sidra", "codigo_sidra", "mes"])
    chaves = [fato.tabela_sidra, fato.codigo_sidra, fato.mes.str[:4]]
    fator = 1 + fato.variacao_mensal / 100
    calculado = (fator.groupby(chaves).cumprod() - 1) * 100
    inversos = (1 / fator).groupby(chaves).cumsum()
    tem_janeiro = fato.groupby(chaves).mes.transform("min").str.endswith("-01")
    limite = 0.005 * (1 + calculado.abs() / 100) * inversos + 0.005
    fora = tem_janeiro & ((calculado - fato.variacao_acum_ano).abs() > limite + 1e-9)
    colunas = ["tabela_sidra", "codigo_ibge", "mes"]
    esperados = pd.read_csv(
        RAIZ / "reference/diagnostico_acumulado_ano_ipca.csv", dtype={"codigo_ibge": str}
    )
    assert len(esperados) == int(fora.sum()) == 239
    assert set(map(tuple, fato.loc[fora, colunas].values)) == set(
        map(tuple, esperados[colunas].values)
    )


def test_zero_publicado_inconsistente_nao_vira_oficial_no_mart():
    categorias = pd.read_csv(RAIZ / "data/marts/ipca_categorias.csv", dtype=str)
    chave = categorias[
        (categorias.tabela_sidra == "1419") & (categorias.codigo_ibge == "7101014")
    ].chave_categoria.iloc[0]
    mart = pd.read_csv(
        RAIZ / "data/marts/ipca_acumulados.csv", dtype={"chave_categoria": str}, low_memory=False
    )
    caso = mart[(mart.chave_categoria == chave) & (mart.mes == "2013-06")].iloc[0]
    assert caso.origem_12m == "calculado"
    assert caso.acum_12m == pytest.approx(17.5482, abs=0.0001)


def test_dicionario_ipca_nao_usa_variaveis_ou_cesta_do_piloto():
    texto = (RAIZ / "data/marts/ipca_README.md").read_text()
    assert "variável 63" in texto
    assert "variável 66" in texto
    assert "(69)" in texto and "(2265)" in texto
    assert "1737" in texto
    for indevido in ["355", "357", "356", "1120", "3065", "1646", "1995-96"]:
        assert indevido not in texto
